"""Climate scenarios by the delta-change method, and their agricultural impacts.

Scenario kinds (never mixed, always labelled):
  historical    the observed/reanalysis baseline as is
  projected     baseline perturbed by one climate model's monthly change signal
                (future window vs that model's own historical window). An ensemble of models
                is summarised by its spread, never presented as one forecast.
  hypothetical  baseline perturbed by user-chosen deltas (stress test, not a projection)

Delta-change (per calendar month m):
  tmax' = tmax + dTx[m]        tmin' = tmin + dTn[m]          (additive, degC)
  precip' = precip * rP[m]     rs' = rs * rR[m]               (multiplicative ratios)
  Humidity: relative humidity is held constant, so actual vapour pressure scales with the
  saturation vapour pressure of the new mean temperature (dew point rises with warming).
  Wind is unchanged.
Known limitations (returned with results): the method preserves the baseline's day-to-day
sequence, so changes in variability, drought spell length and extremes are not represented
beyond the shift of the whole distribution; precipitation ratios are capped to [0.2, 3].
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

from qatra_ai.agronomy import et0 as fao
from qatra_ai.agronomy.daily_et0 import compute_daily_et0
from qatra_ai.suitability.engine import SiteConditions, assess_crops

ScenarioKind = Literal["historical", "projected", "hypothetical"]
PRECIP_RATIO_BOUNDS = (0.2, 3.0)
LIMITATIONS = [
    "Delta-change keeps the baseline's daily sequence: changes in variability, dry-spell "
    "length and extremes beyond a shift of the distribution are not represented.",
    "Relative humidity and wind are held at baseline values.",
    "Crop calendars, varieties and CO2 effects on crop water use are not adapted.",
    "Crop parameters are literature values (needs_review); heat/frost thresholds are "
    "unverified placeholders.",
]


@dataclass(frozen=True)
class MonthlyDeltas:
    """Index 1..12. dtmax/dtmin in degC; precip_ratio/rs_ratio dimensionless."""

    dtmax: pd.Series
    dtmin: pd.Series
    precip_ratio: pd.Series
    rs_ratio: pd.Series

    @classmethod
    def uniform(
        cls, dt: float = 0.0, precip_pct: float = 0.0, rs_pct: float = 0.0
    ) -> MonthlyDeltas:
        m = range(1, 13)
        return cls(
            pd.Series(dt, index=m),
            pd.Series(dt, index=m),
            pd.Series(1 + precip_pct / 100, index=m),
            pd.Series(1 + rs_pct / 100, index=m),
        )

    def annual_summary(self) -> dict[str, float]:
        return {
            "dtmax_mean_c": round(float(self.dtmax.mean()), 2),
            "dtmin_mean_c": round(float(self.dtmin.mean()), 2),
            "precip_ratio_mean": round(float(self.precip_ratio.mean()), 3),
            "rs_ratio_mean": round(float(self.rs_ratio.mean()), 3),
        }


@dataclass(frozen=True)
class Scenario:
    name: str
    kind: ScenarioKind
    deltas: MonthlyDeltas | None = None
    ssp: str | None = None
    model: str | None = None
    window: str | None = None
    source: str | None = None


def monthly_deltas(model_hist: pd.DataFrame, model_future: pd.DataFrame) -> MonthlyDeltas:
    """Change signal of one model: future-window vs historical-window monthly climatology."""
    for need in ("tmax", "tmin", "precip"):
        if need not in model_hist or need not in model_future:
            raise ValueError(f"model data missing column {need}")

    def clim(df: pd.DataFrame, col: str, how: str) -> pd.Series:
        g = df[col].groupby(df.index.month)
        if how == "mean":
            return g.mean()
        # monthly totals averaged over years (robust ratio for precipitation)
        per = df[col].groupby([df.index.year, df.index.month]).sum()
        return per.groupby(level=1).mean()

    ptot_h, ptot_f = clim(model_hist, "precip", "total"), clim(model_future, "precip", "total")
    pr = (ptot_f / ptot_h.replace(0, np.nan)).fillna(1.0).clip(*PRECIP_RATIO_BOUNDS)
    if "rs" in model_hist and "rs" in model_future:
        rr = (clim(model_future, "rs", "mean") / clim(model_hist, "rs", "mean")).fillna(1.0)
    else:
        rr = pd.Series(1.0, index=range(1, 13))
    return MonthlyDeltas(
        dtmax=clim(model_future, "tmax", "mean") - clim(model_hist, "tmax", "mean"),
        dtmin=clim(model_future, "tmin", "mean") - clim(model_hist, "tmin", "mean"),
        precip_ratio=pr,
        rs_ratio=rr,
    )


def _dewpoint_from_ea(ea: np.ndarray) -> np.ndarray:
    x = np.log(np.maximum(ea, 1e-6) / 0.6108)
    return 237.3 * x / (17.27 - x)


def apply_deltas(baseline: pd.DataFrame, d: MonthlyDeltas) -> pd.DataFrame:
    """Perturb a daily baseline (tmax, tmin, precip, rs, and tdew if present)."""
    out = baseline.copy()
    m = out.index.month
    tmean0 = (out["tmax"] + out["tmin"]) / 2
    out["tmax"] = out["tmax"] + d.dtmax.reindex(m).to_numpy()
    out["tmin"] = out["tmin"] + d.dtmin.reindex(m).to_numpy()
    out["precip"] = out["precip"] * d.precip_ratio.reindex(m).to_numpy()
    if "rs" in out:
        out["rs"] = out["rs"] * d.rs_ratio.reindex(m).to_numpy()
    if "tdew" in out:
        tmean1 = (out["tmax"] + out["tmin"]) / 2
        ea0 = fao.saturation_vapour_pressure(out["tdew"].to_numpy())
        scale = fao.saturation_vapour_pressure(tmean1.to_numpy()) / fao.saturation_vapour_pressure(
            tmean0.to_numpy()
        )
        out["tdew"] = _dewpoint_from_ea(ea0 * scale)
    for c in ("et0", "et0_method", "u2", "rhmin", "rhmin_derived"):
        out = out.drop(columns=c, errors="ignore")
    return out


@dataclass
class ScenarioImpacts:
    table: pd.DataFrame  # one row per scenario x crop
    ensemble: pd.DataFrame  # projected scenarios summarised per SSP x crop (min/median/max)
    limitations: list[str] = field(default_factory=lambda: list(LIMITATIONS))


def run_impacts(
    baseline: pd.DataFrame,
    scenarios: list[Scenario],
    crops: dict[str, tuple[int, int]],
    site: SiteConditions,
    *,
    latitude: float,
    elevation_m: float,
    wind_height_m: float = 2.0,
) -> ScenarioImpacts:
    rows = []
    for sc in scenarios:
        w = (
            baseline
            if sc.kind == "historical" or sc.deltas is None
            else apply_deltas(baseline, sc.deltas)
        )
        w = compute_daily_et0(
            w, latitude_deg=latitude, elevation_m=elevation_m, wind_height_m=wind_height_m
        )
        for r in assess_crops(crops, site, w):
            ind = r.indicators
            rows.append(
                {
                    "scenario": sc.name,
                    "kind": sc.kind,
                    "ssp": sc.ssp,
                    "model": sc.model,
                    "crop": r.crop,
                    "overall": r.overall,
                    "et0_annual_mm": round(float(w["et0"].groupby(w.index.year).sum().mean())),
                    "etc_median_mm": ind.get("etc_median_mm"),
                    "irrigation_p50_m3_ha": ind.get("gross_irrigation_median_m3_per_ha"),
                    "irrigation_p80_m3_ha": ind.get("gross_irrigation_p80_m3_per_ha"),
                    "expected_relative_yield": ind.get("expected_relative_yield"),
                    "heat_days": ind.get("mean_heat_days"),
                    "provisional_warnings": len(r.provisional_warnings),
                    **(sc.deltas.annual_summary() if sc.deltas else {}),
                }
            )
    table = pd.DataFrame(rows)
    base = table[table["kind"] == "historical"].set_index("crop")
    if not base.empty:
        for col in ("irrigation_p50_m3_ha", "irrigation_p80_m3_ha", "etc_median_mm"):
            table[f"{col}_change_pct"] = table.apply(
                lambda r, c=col: (
                    round(100 * (r[c] / base.loc[r["crop"], c] - 1), 1)
                    if r["crop"] in base.index and base.loc[r["crop"], c]
                    else None
                ),
                axis=1,
            )
    proj = table[table["kind"] == "projected"]
    if proj.empty:
        ens = pd.DataFrame()
    else:
        agg_cols = [
            c
            for c in (
                "irrigation_p80_m3_ha_change_pct",
                "irrigation_p50_m3_ha_change_pct",
                "heat_days",
                "expected_relative_yield",
            )
            if c in proj
        ]
        ens = proj.groupby(["ssp", "crop"])[agg_cols].agg(["min", "median", "max"]).round(1)
        ens["models"] = proj.groupby(["ssp", "crop"])["model"].nunique()
    return ScenarioImpacts(table, ens)
