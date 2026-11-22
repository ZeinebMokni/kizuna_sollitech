"""Build scheduler inputs from the agronomy engine's outputs and daily forecasts.

Disaggregation assumptions (returned to callers via DISAGGREGATION_ASSUMPTIONS):
- Daily ETc is spread over local hours 06:00-18:00 with a half-sine profile.
- Daily effective rain is spread evenly over 24 h (timing of showers is not forecast reliably).
- Hourly PV energy follows the same half-sine profile applied to daily horizontal radiation;
  horizontal irradiance is used as a proxy for plane-of-array (underestimates tilted arrays).
- `conservative_factor` derates PV to hedge forecast error. It is a chosen safety factor,
  NOT a statistical P10.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import pandas as pd

from qatra_ai.agronomy.kc import adjusted_depletion_fraction, kc_for_day, root_depth_for_day
from qatra_ai.agronomy.kc import stage_for_day as _stage
from qatra_ai.agronomy.water_balance import LIGHT_RAIN_FACTOR, ZoneSetup
from qatra_ai.optimization.schedule_models import SchedulingZone

DISAGGREGATION_ASSUMPTIONS = [
    "Daily ETc spread over 06:00-18:00 local time with a half-sine profile.",
    "Daily effective rain spread evenly over 24 h.",
    "Hourly PV from daily horizontal radiation with a half-sine 06:00-18:00 profile.",
    "PV derated by a conservative factor (a chosen hedge, not a statistical P10).",
]


def _daytime_weights() -> list[float]:
    w = [
        max(0.0, math.sin(math.pi * (h + 0.5 - 6) / 12)) if 6 <= h < 18 else 0.0 for h in range(24)
    ]
    total = sum(w)
    return [v / total for v in w]


DAYTIME = _daytime_weights()


def _slot_hours(start: datetime, n_slots: int) -> list[datetime]:
    return [start + timedelta(hours=t) for t in range(n_slots)]


def zone_from_forecast(
    zone_id: str,
    setup: ZoneSetup,
    *,
    current_depletion_mm: float,
    forecast_daily: pd.DataFrame,
    start: datetime,
    n_slots: int,
    design_flow_m3h: float,
    max_hours_per_day: float | None = None,
) -> SchedulingZone:
    """Hourly scheduling inputs for one zone.

    forecast_daily: DatetimeIndex of local dates, columns et0 [mm], precip [mm].
    """
    crop, soil = setup.crop, setup.soil
    etc, peff, ky = [], [], []
    ky_assumed = False
    taw = raw = None
    for ts in _slot_hours(start, n_slots):
        day = pd.Timestamp(ts.date())
        if day not in forecast_daily.index:
            raise ValueError(f"forecast missing for {day.date()}")
        row = forecast_daily.loc[day]
        sd = (ts.date() - setup.season_start).days
        sd = sd % 365 if crop.perennial else sd
        kc = kc_for_day(crop, sd)
        stage = _stage(crop, sd)
        if kc is None or stage is None:
            raise ValueError(f"{zone_id}: {ts.date()} is outside the crop season")
        etc_day = kc * float(row["et0"])
        p_day = float(row["precip"])
        peff_day = 0.0 if p_day < LIGHT_RAIN_FACTOR * float(row["et0"]) else p_day
        etc.append(etc_day * DAYTIME[ts.hour])
        peff.append(peff_day / 24.0)
        k = getattr(crop.ky_stage, stage)
        if k is None:
            k = crop.ky_total
        if k is None:
            ky_assumed = True
            k = 0.0  # scheduler substitutes policy.default_ky and flags it
        ky.append(k)
        if taw is None:  # TAW/RAW fixed at the start of the horizon
            zr = root_depth_for_day(crop, sd, soil.soil_depth_m)
            taw = soil.taw_mm(zr)
            raw = adjusted_depletion_fraction(crop.depletion_fraction_p, etc_day) * taw
    assert taw is not None and raw is not None
    return SchedulingZone(
        zone_id=zone_id,
        area_ha=setup.area_ha,
        design_flow_m3h=design_flow_m3h,
        application_efficiency=setup.application_efficiency,
        initial_depletion_mm=min(current_depletion_mm, taw),
        taw_mm=taw,
        raw_mm=raw,
        etc_mm=etc,
        peff_mm=peff,
        ky=ky,
        ky_assumed=ky_assumed,
        perennial=crop.perennial,
        max_hours_per_day=max_hours_per_day,
    )


def pv_slots_from_daily_radiation(
    rs_mj_daily: pd.Series,
    *,
    start: datetime,
    n_slots: int,
    p_rated_kw: float,
    system_efficiency: float = 0.86,
    conservative_factor: float = 0.8,
) -> list[float]:
    """kWh of PV energy per hourly slot from daily horizontal radiation [MJ m-2 day-1]."""
    if not 0 < conservative_factor <= 1:
        raise ValueError("conservative_factor must be in (0, 1]")
    out = []
    for ts in _slot_hours(start, n_slots):
        day = pd.Timestamp(ts.date())
        if day not in rs_mj_daily.index:
            raise ValueError(f"radiation missing for {day.date()}")
        kwh_m2 = float(rs_mj_daily.loc[day]) / 3.6 * DAYTIME[ts.hour]
        out.append(p_rated_kw * kwh_m2 * system_efficiency * conservative_factor)
    return out
