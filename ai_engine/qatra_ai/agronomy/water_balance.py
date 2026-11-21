"""Daily root-zone soil water balance (FAO-56 chapter 8) with optional sensor assimilation.

    Dr,i = Dr,i-1 - Peff,i - Inet,i + ETc_adj,i + DPi                    (Eq. 85, RO = CR = 0)
    Ks   = (TAW - Dr) / ((1 - p) TAW)   if Dr > RAW, else 1              (Eq. 84)
    ETc_adj = Ks * Kc * ET0                                              (Eq. 81)

Documented assumptions (also returned as limitations):
- Runoff RO = 0; water above field capacity leaves as deep percolation DP the same day.
- Capillary rise CR = 0 (no shallow water table).
- Rain below 0.2 * ET0 is fully evaporated (FAO-56, chapter 8 guidance); otherwise Peff = P.
- Ks is evaluated from the depletion at the start of the day.
- Net irrigation = gross applied depth * application efficiency.
- If the initial depletion is unknown, the soil is assumed at field capacity (Dr = 0).

Sensor assimilation (optional): a scalar Kalman update pulls the modelled depletion
towards the depletion implied by a *calibrated* soil-moisture sensor. Uncalibrated
readings are recorded but never assimilated.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from qatra_ai.agronomy.crops import CropProfile
from qatra_ai.agronomy.kc import (
    adjust_kc_for_climate,
    adjusted_depletion_fraction,
    kc_for_day,
    root_depth_for_day,
    stage_for_day,
)
from qatra_ai.agronomy.soil import SoilWaterProperties

ET0_GAP_FILL_WINDOW = 7  # days of trailing mean used to fill isolated ET0 gaps
LIGHT_RAIN_FACTOR = 0.2  # rain < 0.2 * ET0 is considered fully evaporated


class ZoneSetup(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    crop: CropProfile
    season_start: date = Field(description="Planting date (annuals) or cycle start (perennials)")
    soil: SoilWaterProperties
    area_ha: float = Field(gt=0)
    application_efficiency: float = Field(gt=0, le=1)
    initial_depletion_mm: float | None = Field(default=None, ge=0)
    climate_adjust_kc: bool = True


class AssimilationSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    process_noise_mm_per_day: float = Field(default=2.0, gt=0)
    initial_std_known_mm: float = Field(default=5.0, gt=0)
    initial_std_unknown_fraction_of_taw: float = Field(default=0.5, gt=0)


def _season_day(setup: ZoneSetup, d: pd.Timestamp) -> int | None:
    day = (d.date() - setup.season_start).days
    if setup.crop.perennial:
        return day % 365
    if 0 <= day < setup.crop.season_length_days:
        return day
    return None


def _climate_adjusted_kc(setup: ZoneSetup, weather: pd.DataFrame) -> tuple[float, float, list[str]]:
    crop = setup.crop
    notes: list[str] = []
    if not setup.climate_adjust_kc:
        return crop.kc.mid, crop.kc.end, ["Kc not climate-adjusted (disabled)"]
    if "u2" not in weather or "rhmin" not in weather:
        return crop.kc.mid, crop.kc.end, ["Kc not climate-adjusted (u2 or RHmin unavailable)"]

    stages = pd.Series(
        [
            stage_for_day(crop, sd) if (sd := _season_day(setup, d)) is not None else None
            for d in weather.index
        ],
        index=weather.index,
    )

    def stage_means(name: str) -> tuple[float, float] | None:
        rows = weather[stages == name]
        u2, rh = rows["u2"].mean(), rows["rhmin"].mean()
        if rows.empty or not np.isfinite(u2) or not np.isfinite(rh):
            return None
        return float(u2), float(rh)

    k_mid, k_end = crop.kc.mid, crop.kc.end
    if (m := stage_means("mid")) is not None:
        k_mid = adjust_kc_for_climate(crop.kc.mid, m[0], m[1], crop.max_height_m)
    else:
        notes.append("Kc_mid not climate-adjusted (no mid-season weather in range)")
    if (e := stage_means("late")) is not None:
        k_end = adjust_kc_for_climate(crop.kc.end, e[0], e[1], crop.max_height_m)
    else:
        notes.append("Kc_end not climate-adjusted (no late-season weather in range)")
    return k_mid, k_end, notes


def simulate_water_balance(
    setup: ZoneSetup,
    weather: pd.DataFrame,
    irrigation_gross_mm: pd.Series | None = None,
    soil_moisture_obs: pd.DataFrame | None = None,
    assimilation: AssimilationSettings | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Run the daily balance. Returns (daily table, notes).

    weather: DatetimeIndex (daily, continuous), columns `et0` [mm], `precip` [mm],
             optional `u2` [m/s] and `rhmin` [%] for Kc climate adjustment.
    irrigation_gross_mm: gross applied depth per day [mm] (index = dates).
    soil_moisture_obs: columns `theta` [m3/m3], `std` [m3/m3], `calibrated` [bool],
             one representative root-zone reading per day.
    """
    assim = assimilation or AssimilationSettings()
    if not isinstance(weather.index, pd.DatetimeIndex):
        raise TypeError("weather must have a DatetimeIndex")
    weather = weather.sort_index()
    if (
        len(weather) > 1
        and (weather.index.to_series().diff().dropna() != pd.Timedelta(days=1)).any()
    ):
        raise ValueError(
            "weather index must be continuous daily dates (fill gaps explicitly first)"
        )
    for required in ("et0", "precip"):
        if required not in weather:
            raise ValueError(f"weather is missing column '{required}'")

    notes: list[str] = []
    et0 = weather["et0"].astype(float)
    et0_filled = et0.fillna(et0.rolling(ET0_GAP_FILL_WINDOW, min_periods=3).mean().shift(1))
    gap_filled_mask = et0.isna() & et0_filled.notna()
    if et0_filled.isna().any():
        first_bad = et0_filled[et0_filled.isna()].index[0].date()
        raise ValueError(f"ET0 missing on {first_bad} with no prior data to bridge the gap")

    precip = weather["precip"].astype(float)
    if precip.isna().any():
        raise ValueError("precipitation has missing values; supply 0 only if truly no rain")

    k_mid, k_end, kc_notes = _climate_adjusted_kc(setup, weather)
    notes.extend(kc_notes)

    irr = irrigation_gross_mm if irrigation_gross_mm is not None else pd.Series(dtype=float)
    irr = irr.reindex(weather.index).fillna(0.0)
    if (irr < 0).any():
        raise ValueError("irrigation depths must be >= 0")

    obs = soil_moisture_obs.reindex(weather.index) if soil_moisture_obs is not None else None

    soil, crop = setup.soil, setup.crop
    rows: list[dict] = []
    dr: float | None = None
    var: float = 0.0

    for d in weather.index:
        sd = _season_day(setup, d)
        if sd is None:
            continue
        stage = stage_for_day(crop, sd)
        kc = kc_for_day(crop, sd, k_mid, k_end)
        assert kc is not None and stage is not None
        zr = root_depth_for_day(crop, sd, soil.soil_depth_m)
        taw = soil.taw_mm(zr)

        if dr is None:  # first simulated day
            if setup.initial_depletion_mm is None:
                dr = 0.0
                var = (assim.initial_std_unknown_fraction_of_taw * taw) ** 2
                notes.append("Initial depletion unknown: soil assumed at field capacity")
            else:
                dr = min(setup.initial_depletion_mm, taw)
                var = assim.initial_std_known_mm**2

        flags: list[str] = []
        e0 = float(et0_filled[d])
        if gap_filled_mask[d]:
            flags.append("et0_gap_filled")
        etc = kc * e0
        p = adjusted_depletion_fraction(crop.depletion_fraction_p, etc)
        raw = p * taw

        dr_start = min(dr, taw)
        ks = 1.0 if dr_start <= raw else float(np.clip((taw - dr_start) / ((1 - p) * taw), 0, 1))
        eta = ks * etc

        p_mm = float(precip[d])
        peff = 0.0 if p_mm < LIGHT_RAIN_FACTOR * e0 else p_mm
        i_gross = float(irr[d])
        i_net = i_gross * setup.application_efficiency

        dr_new = dr_start - peff - i_net + eta
        dp = 0.0
        if dr_new < 0:
            dp, dr_new = -dr_new, 0.0
        if dr_new > taw:  # ET cannot extract below wilting point
            eta -= dr_new - taw
            dr_new = taw
            flags.append("et_limited_at_wilting_point")

        var += assim.process_noise_mm_per_day**2
        innovation = gain = np.nan
        adj = 0.0
        if obs is not None and np.isfinite(obs.at[d, "theta"]):
            if bool(obs.at[d, "calibrated"]):
                dr_obs = float(np.clip(1000.0 * (soil.theta_fc - obs.at[d, "theta"]) * zr, 0, taw))
                sigma_o = 1000.0 * float(obs.at[d, "std"]) * zr
                gain = var / (var + sigma_o**2)
                innovation = dr_obs - dr_new
                adj = gain * innovation
                dr_new += adj
                var *= 1 - gain
                flags.append("assimilated")
            else:
                flags.append("obs_uncalibrated_not_assimilated")

        rows.append(
            {
                "date": d,
                "season_day": sd,
                "stage": stage,
                "kc": kc,
                "zr_m": zr,
                "taw_mm": taw,
                "p": p,
                "raw_mm": raw,
                "dr_start_mm": dr_start,
                "ks": ks,
                "et0_mm": e0,
                "etc_mm": etc,
                "eta_mm": eta,
                "precip_mm": p_mm,
                "peff_mm": peff,
                "irrigation_gross_mm": i_gross,
                "irrigation_net_mm": i_net,
                "deep_percolation_mm": dp,
                "assimilation_adjustment_mm": adj,
                "innovation_mm": innovation,
                "kalman_gain": gain,
                "dr_end_mm": dr_new,
                "depletion_std_mm": float(np.sqrt(var)),
                "stressed": dr_start > raw,
                "flags": ",".join(flags),
            }
        )
        dr = dr_new

    if not rows:
        raise ValueError("no weather dates fall inside the crop season")
    return pd.DataFrame(rows).set_index("date"), notes


def days_to_stress(
    setup: ZoneSetup,
    current_depletion_mm: float,
    forecast: pd.DataFrame,
    planned_irrigation_gross_mm: pd.Series | None = None,
) -> tuple[int | None, pd.DataFrame]:
    """Project depletion through a forecast; return days until Dr first exceeds RAW (or None).

    0 means the zone is already beyond RAW at the start of the forecast.
    """
    projected_setup = setup.model_copy(update={"initial_depletion_mm": current_depletion_mm})
    table, _ = simulate_water_balance(projected_setup, forecast, planned_irrigation_gross_mm)
    beyond = table["dr_start_mm"] > table["raw_mm"]
    if not beyond.any():
        return None, table
    first = beyond.idxmax()
    return int((first - table.index[0]).days), table
