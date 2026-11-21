"""Crop suitability: FAO limiting-factor classification plus Pareto trade-offs.

Deliberately NOT a single weighted score (AI_ENGINE_BLUEPRINT section 2.6).

1. Each factor is classified S1 (highly), S2 (moderately), S3 (marginally) suitable,
   N (not suitable) or U (undetermined: data missing). The overall class is the most limiting
   determined factor (FAO Framework for Land Evaluation: maximum-limitation method).
   If a CRITICAL factor is U and no factor is N, the overall class is U.
2. Among crops that are not N or U, the Pareto set (non-dominated on water requirement,
   expected yield, energy, heat days, frost risk) is reported. No ranking is imposed.

Factors:
  water     dry-year (P80 over seasons) gross irrigation requirement vs available water,
            converted to expected relative yield with FAO-33 Ky
  salinity  FAO-29 relative yield from soil ECe (or ECe ~ 1.5 x ECw for irrigation water)
  heat      mean days with Tmax above the crop's heat threshold in heat-sensitive stages
  frost     share of seasons with Tmin below the crop's frost threshold in sensitive stages
  energy    dry-year pumping energy vs available energy
  soil_depth  soil depth vs crop maximum rooting depth
  market    always U until market data is integrated

Classification thresholds are QATRA rules (documented below), not published standards.
Crop temperature thresholds are placeholders (`TemperatureLimits.verified == False`).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from qatra_ai.agronomy.crops import CropProfile, get_crop
from qatra_ai.agronomy.kc import (
    adjusted_depletion_fraction,
    kc_for_day,
    root_depth_for_day,
    stage_for_day,
)
from qatra_ai.agronomy.soil import SoilWaterProperties
from qatra_ai.agronomy.water_balance import LIGHT_RAIN_FACTOR
from qatra_ai.agronomy.yield_response import relative_yield_salinity
from qatra_ai.contracts import DataClass
from qatra_ai.energy import pump_energy_kwh

SuitClass = Literal["S1", "S2", "S3", "N", "U"]
ORDER: list[SuitClass] = ["S1", "S2", "S3", "N"]
CRITICAL = ("water", "salinity")

# QATRA classification rules (documented, adjustable; not published standards)
YIELD_CLASSES = ((0.9, "S1"), (0.75, "S2"), (0.5, "S3"))  # relative yield >= threshold
RATIO_CLASSES = ((1.0, "S1"), (0.8, "S2"), (0.6, "S3"))  # available / required
HEAT_DAY_CLASSES = ((2, "S1"), (7, "S2"), (15, "S3"))  # mean hot days <= threshold
FROST_SHARE_CLASSES = ((0.0, "S1"), (0.1, "S2"), (0.3, "S3"))  # share of seasons <= threshold
DEPTH_CLASSES = ((1.0, "S1"), (0.7, "S2"), (0.5, "S3"))  # soil depth / root depth >= threshold
ECE_FROM_ECW = 1.5  # FAO-29 approximation for ~15-20 % leaching fraction


class SiteConditions(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    latitude: float
    soil: SoilWaterProperties
    soil_ece_ds_m: float | None = Field(default=None, ge=0)
    irrigation_water_ec_ds_m: float | None = Field(default=None, ge=0)
    available_water_m3_per_ha: float | None = Field(default=None, ge=0)
    available_energy_kwh_per_ha: float | None = Field(default=None, ge=0)
    pumping_head_m: float = Field(default=50.0, gt=0)
    pump_efficiency: float = Field(default=0.55, gt=0, le=1)
    application_efficiency: float = Field(default=0.9, gt=0, le=1)
    weather_source: str
    weather_data_class: DataClass


class FactorResult(BaseModel):
    factor: str
    suitability: SuitClass
    value: float | None
    unit: str | None
    rule: str
    note: str | None = None
    provisional: bool = Field(
        default=False,
        description="Based on an unverified crop threshold: reported as a warning but excluded "
        "from the overall class",
    )


class CropSuitability(BaseModel):
    crop: str
    planting: str
    overall: SuitClass
    limiting_factors: list[str]
    undetermined_factors: list[str]
    provisional_warnings: list[str] = Field(default_factory=list)
    factors: list[FactorResult]
    indicators: dict[str, float | None]
    seasons_evaluated: int
    pareto_optimal: bool | None = None
    review_status: str
    placeholder_parameters: list[str]


def _classify_ge(x: float, classes) -> SuitClass:
    for thr, c in classes:
        if x >= thr - 1e-12:
            return c
    return "N"


def _classify_le(x: float, classes) -> SuitClass:
    for thr, c in classes:
        if x <= thr + 1e-12:
            return c
    return "N"


def _season_days(crop: CropProfile, start: date) -> list[tuple[date, int]]:
    return [(start + timedelta(days=i), i) for i in range(crop.season_length_days)]


def season_requirement(
    crop: CropProfile, start: date, weather: pd.DataFrame, soil: SoilWaterProperties
) -> dict[str, float] | None:
    """Full-irrigation season (refill to FC whenever Dr > RAW). Returns None if weather does not
    cover the season. Values in mm: etc, peff, net_irrigation; plus hot/frost day counts."""
    temp = crop.temperature
    dr = 0.0
    etc_sum = peff_sum = net = 0.0
    hot = frost = 0
    for d, sd in _season_days(crop, start):
        ts = pd.Timestamp(d)
        if ts not in weather.index:
            return None
        row = weather.loc[ts]
        et0, p = float(row["et0"]), float(row["precip"])
        if not (np.isfinite(et0) and np.isfinite(p)):
            return None
        kc = kc_for_day(crop, sd)
        stage = stage_for_day(crop, sd)
        etc = kc * et0
        taw = soil.taw_mm(root_depth_for_day(crop, sd, soil.soil_depth_m))
        raw = adjusted_depletion_fraction(crop.depletion_fraction_p, etc) * taw
        peff = 0.0 if p < LIGHT_RAIN_FACTOR * et0 else p
        dr = max(0.0, dr + etc - peff)
        if dr > raw:
            net += dr
            dr = 0.0
        etc_sum += etc
        peff_sum += peff
        if temp is not None:
            if (
                temp.heat_stress_tmax_c is not None
                and stage in temp.heat_sensitive_stages
                and float(row.get("tmax", np.nan)) > temp.heat_stress_tmax_c
            ):
                hot += 1
            if (
                temp.frost_damage_tmin_c is not None
                and stage in temp.frost_sensitive_stages
                and float(row.get("tmin", np.nan)) < temp.frost_damage_tmin_c
            ):
                frost += 1
    return {
        "etc_mm": etc_sum,
        "peff_mm": peff_sum,
        "net_mm": net,
        "hot_days": hot,
        "frost_days": frost,
    }


def assess_crop(
    crop_code: str,
    planting_month_day: tuple[int, int],
    site: SiteConditions,
    weather: pd.DataFrame,
) -> CropSuitability:
    crop = get_crop(crop_code)
    years = sorted(set(weather.index.year))
    seasons = []
    for y in years:
        r = season_requirement(crop, date(y, *planting_month_day), weather, site.soil)
        if r is not None:
            seasons.append(r)
    factors: list[FactorResult] = []
    placeholders: list[str] = []
    ind: dict[str, float | None] = {}
    ea = site.application_efficiency

    if not seasons:
        factors.append(
            FactorResult(
                factor="water",
                suitability="U",
                value=None,
                unit=None,
                rule="needs at least one full season of weather",
                note="weather does not cover a full season",
            )
        )
    else:
        df = pd.DataFrame(seasons)
        gross_p80 = float(np.percentile(df["net_mm"], 80)) / ea * 10  # m3/ha
        gross_med = float(df["net_mm"].median()) / ea * 10
        etc_med = float(df["etc_mm"].median())
        ind.update(
            {
                "gross_irrigation_p80_m3_per_ha": round(gross_p80),
                "gross_irrigation_median_m3_per_ha": round(gross_med),
                "etc_median_mm": round(etc_med),
                "season_days": crop.season_length_days,
            }
        )
        # Energy to deliver the water the crop would actually receive (cannot exceed the quota).
        delivered = (
            gross_p80
            if site.available_water_m3_per_ha is None
            else min(gross_p80, site.available_water_m3_per_ha)
        )
        energy = pump_energy_kwh(delivered, site.pumping_head_m, site.pump_efficiency)
        ind["pump_energy_p80_kwh_per_ha"] = round(energy)

        # --- water
        if site.available_water_m3_per_ha is None:
            factors.append(
                FactorResult(
                    factor="water",
                    suitability="U",
                    value=None,
                    unit=None,
                    rule="available water unknown",
                )
            )
            ind["expected_relative_yield"] = None
        else:
            avail_net_mm = site.available_water_m3_per_ha / 10 * ea
            deficit = max(0.0, float(np.percentile(df["net_mm"], 80)) - avail_net_mm)
            p80_etc = etc_med
            ky = crop.ky_total
            if ky is not None and p80_etc > 0:
                ry = max(0.0, 1 - ky * min(deficit / p80_etc, 1.0))
                cls = _classify_ge(ry, YIELD_CLASSES)
                factors.append(
                    FactorResult(
                        factor="water",
                        suitability=cls,
                        value=round(ry, 3),
                        unit="relative yield",
                        rule="FAO-33 seasonal Ky; S1>=0.9, S2>=0.75, S3>=0.5 (dry-year P80 demand)",
                        note=f"available {site.available_water_m3_per_ha:.0f} vs required "
                        f"{gross_p80:.0f} m3/ha (P80)",
                    )
                )
                ind["expected_relative_yield"] = round(ry, 3)
            else:
                ratio = site.available_water_m3_per_ha / gross_p80 if gross_p80 > 0 else 9.99
                factors.append(
                    FactorResult(
                        factor="water",
                        suitability="U",
                        value=round(ratio, 3),
                        unit="available/full requirement",
                        rule="no Ky for this crop: yield response to deficit unknown, so water "
                        "suitability cannot be judged",
                        note=f"full-irrigation requirement {gross_p80:.0f} m3/ha (P80) shown for "
                        "information; many such crops are grown rainfed or under deficit "
                        "irrigation",
                    )
                )
                ind["expected_relative_yield"] = None
                ind["water_supply_ratio"] = round(ratio, 3)

        # --- energy
        if site.available_energy_kwh_per_ha is None:
            factors.append(
                FactorResult(
                    factor="energy",
                    suitability="U",
                    value=None,
                    unit=None,
                    rule="available energy unknown",
                )
            )
        else:
            ratio = site.available_energy_kwh_per_ha / energy if energy > 0 else 9.99
            factors.append(
                FactorResult(
                    factor="energy",
                    suitability=_classify_ge(ratio, RATIO_CLASSES),
                    value=round(ratio, 3),
                    unit="available/required",
                    rule="S1>=1.0, S2>=0.8, S3>=0.6",
                    note=f"{energy:.0f} kWh/ha to pump {delivered:.0f} m3/ha (P80 need, capped at "
                    "the water available)",
                )
            )

        # --- heat & frost
        t = crop.temperature
        if t is None:
            factors.append(
                FactorResult(
                    factor="heat",
                    suitability="U",
                    value=None,
                    unit=None,
                    rule="no temperature limits in crop profile",
                )
            )
            factors.append(
                FactorResult(
                    factor="frost",
                    suitability="U",
                    value=None,
                    unit=None,
                    rule="no temperature limits in crop profile",
                )
            )
        else:
            has_t = "tmax" in weather and "tmin" in weather
            if not t.verified:
                placeholders.append("temperature limits")
            if t.heat_stress_tmax_c is None:
                factors.append(
                    FactorResult(
                        factor="heat",
                        suitability="S1",
                        value=0,
                        unit="days",
                        rule="no heat threshold defined for this crop",
                    )
                )
                ind["mean_heat_days"] = 0.0
            elif has_t:
                hot = float(df["hot_days"].mean())
                factors.append(
                    FactorResult(
                        factor="heat",
                        suitability=_classify_le(hot, HEAT_DAY_CLASSES),
                        value=round(hot, 1),
                        unit="days/season",
                        rule=f"Tmax > {t.heat_stress_tmax_c} C in {t.heat_sensitive_stages}; "
                        "S1<=2, S2<=7, S3<=15 days",
                        note=None if t.verified else "threshold is an unverified placeholder",
                        provisional=not t.verified,
                    )
                )
                ind["mean_heat_days"] = round(hot, 1)
            else:
                factors.append(
                    FactorResult(
                        factor="heat", suitability="U", value=None, unit=None, rule="no Tmax data"
                    )
                )
            if t.frost_damage_tmin_c is None:
                factors.append(
                    FactorResult(
                        factor="frost",
                        suitability="S1",
                        value=0,
                        unit="share",
                        rule="no frost threshold defined",
                    )
                )
                ind["frost_season_share"] = 0.0
            elif has_t:
                share = float((df["frost_days"] > 0).mean())
                factors.append(
                    FactorResult(
                        factor="frost",
                        suitability=_classify_le(share, FROST_SHARE_CLASSES),
                        value=round(share, 2),
                        unit="share of seasons",
                        rule=f"Tmin < {t.frost_damage_tmin_c} C in {t.frost_sensitive_stages}; "
                        "S1=0, S2<=0.1, S3<=0.3",
                        note=None if t.verified else "threshold is an unverified placeholder",
                        provisional=not t.verified,
                    )
                )
                ind["frost_season_share"] = round(share, 2)
            else:
                factors.append(
                    FactorResult(
                        factor="frost", suitability="U", value=None, unit=None, rule="no Tmin data"
                    )
                )

    # --- salinity
    ece = site.soil_ece_ds_m
    source = "soil ECe"
    if ece is None and site.irrigation_water_ec_ds_m is not None:
        ece, source = ECE_FROM_ECW * site.irrigation_water_ec_ds_m, "1.5 x irrigation-water ECw"
    if crop.salinity is None:
        factors.append(
            FactorResult(
                factor="salinity",
                suitability="U",
                value=None,
                unit=None,
                rule="crop salinity tolerance not in profile",
            )
        )
    elif ece is None:
        factors.append(
            FactorResult(
                factor="salinity",
                suitability="U",
                value=None,
                unit=None,
                rule="no soil ECe or irrigation-water EC supplied",
            )
        )
    else:
        ry = relative_yield_salinity(ece, crop.salinity)
        factors.append(
            FactorResult(
                factor="salinity",
                suitability=_classify_ge(ry, YIELD_CLASSES),
                value=round(ry, 3),
                unit="relative yield",
                rule="FAO-29; S1>=0.9, S2>=0.75, S3>=0.5",
                note=f"ECe {ece:.1f} dS/m from {source}",
            )
        )

    # --- soil depth
    if site.soil.soil_depth_m is None:
        factors.append(
            FactorResult(
                factor="soil_depth",
                suitability="U",
                value=None,
                unit=None,
                rule="soil depth unknown",
            )
        )
    else:
        ratio = site.soil.soil_depth_m / crop.root_depth.max_m
        factors.append(
            FactorResult(
                factor="soil_depth",
                suitability=_classify_ge(ratio, DEPTH_CLASSES),
                value=round(ratio, 2),
                unit="depth/root depth",
                rule="S1>=1.0, S2>=0.7, S3>=0.5",
            )
        )

    factors.append(
        FactorResult(
            factor="market",
            suitability="U",
            value=None,
            unit=None,
            rule="market data not yet integrated",
        )
    )

    determined = [f for f in factors if f.suitability != "U" and not f.provisional]
    warnings = [
        f"{f.factor}={f.suitability} (provisional: {f.note})"
        for f in factors
        if f.provisional and f.suitability in ("S2", "S3", "N")
    ]
    worst = max((ORDER.index(f.suitability) for f in determined), default=None)
    undetermined = [f.factor for f in factors if f.suitability == "U"]
    if worst is not None and ORDER[worst] == "N":
        overall: SuitClass = "N"
    elif any(c in undetermined for c in CRITICAL) or worst is None:
        overall = "U"
    else:
        overall = ORDER[worst]
    limiting = (
        [f.factor for f in determined if worst is not None and ORDER.index(f.suitability) == worst]
        if overall in ("S2", "S3", "N")
        else []
    )
    if crop.review_status != "reviewed":
        placeholders.append("crop parameters (needs_review)")
    return CropSuitability(
        crop=crop.code,
        planting=f"{planting_month_day[1]:02d}/{planting_month_day[0]:02d}",
        overall=overall,
        limiting_factors=limiting,
        undetermined_factors=undetermined,
        provisional_warnings=warnings,
        factors=factors,
        indicators=ind,
        seasons_evaluated=len(seasons),
        review_status=crop.review_status,
        placeholder_parameters=placeholders,
    )


PARETO_OBJECTIVES = (  # (indicator, direction) where +1 = higher is better
    ("gross_irrigation_p80_m3_per_ha", -1),
    ("expected_relative_yield", +1),
    ("pump_energy_p80_kwh_per_ha", -1),
    ("mean_heat_days", -1),
    ("frost_season_share", -1),
)


def mark_pareto(results: list[CropSuitability]) -> list[CropSuitability]:
    """Pareto-optimal among crops classed S1-S3, on objectives available for all of them.
    Indicators that rest on unverified placeholder thresholds (heat, frost) are excluded."""
    cand = [r for r in results if r.overall in ("S1", "S2", "S3")]
    provisional_ind = {"heat": "mean_heat_days", "frost": "frost_season_share"}
    excluded = {
        provisional_ind[f.factor]
        for r in cand
        for f in r.factors
        if f.provisional and f.factor in provisional_ind
    }
    objs = [
        k
        for k, _ in PARETO_OBJECTIVES
        if k not in excluded and all(r.indicators.get(k) is not None for r in cand)
    ]
    sign = dict(PARETO_OBJECTIVES)
    out = []
    for r in results:
        if r not in cand or not objs:
            out.append(r.model_copy(update={"pareto_optimal": None}))
            continue
        dominated = False
        for o in cand:
            if o is r:
                continue
            ge = all(sign[k] * o.indicators[k] >= sign[k] * r.indicators[k] for k in objs)
            gt = any(sign[k] * o.indicators[k] > sign[k] * r.indicators[k] for k in objs)
            if ge and gt:
                dominated = True
                break
        out.append(r.model_copy(update={"pareto_optimal": not dominated}))
    return out


def assess_crops(
    crops: dict[str, tuple[int, int]], site: SiteConditions, weather: pd.DataFrame
) -> list[CropSuitability]:
    """crops: crop code -> planting (month, day). weather: daily et0, precip, tmax, tmin."""
    return mark_pareto([assess_crop(c, md, site, weather) for c, md in crops.items()])
