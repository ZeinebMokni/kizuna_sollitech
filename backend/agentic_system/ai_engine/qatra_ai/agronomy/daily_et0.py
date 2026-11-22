"""Compute daily ET0 for a weather table, choosing the best method each row allows.

Input DataFrame (DatetimeIndex, one row per local calendar day). Recognised columns:
    tmin, tmax           degC                    (required)
    tdew                 degC                    (preferred humidity input)
    rhmin, rhmax         %                       (humidity fallback)
    rs                   MJ m-2 day-1            (incoming shortwave)
    wind                 m s-1 at `wind_height_m`

Method per row:
    penman_monteith  if temperature, humidity, radiation and wind are all present;
    hargreaves       if only temperature is present (lower confidence; flagged);
    missing          otherwise (ET0 = NaN; never silently filled).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from qatra_ai.agronomy import et0 as fao

METHOD_PM = "penman_monteith"
METHOD_HS = "hargreaves"
METHOD_MISSING = "missing"


def compute_daily_et0(
    weather: pd.DataFrame,
    *,
    latitude_deg: float,
    elevation_m: float,
    wind_height_m: float = 10.0,
) -> pd.DataFrame:
    if not isinstance(weather.index, pd.DatetimeIndex):
        raise TypeError("weather must have a DatetimeIndex")
    df = weather.copy()
    doy = df.index.day_of_year.to_numpy()

    def col(name: str) -> pd.Series:
        return df[name] if name in df else pd.Series(np.nan, index=df.index)

    tmin, tmax = col("tmin"), col("tmax")
    if ((tmax < tmin) & tmax.notna() & tmin.notna()).any():
        raise ValueError("tmax < tmin in some rows; run data QC before computing ET0")

    ea_dew = fao.actual_vapour_pressure_from_tdew(col("tdew").to_numpy())
    ea_rh = fao.actual_vapour_pressure_from_rh(
        tmin.to_numpy(), tmax.to_numpy(), col("rhmin").to_numpy(), col("rhmax").to_numpy()
    )
    ea = np.where(np.isfinite(ea_dew), ea_dew, ea_rh)
    u2 = fao.wind_speed_at_2m(col("wind").to_numpy(), wind_height_m)
    rs = col("rs").to_numpy()

    pm = fao.et0_penman_monteith(
        tmin=tmin.to_numpy(),
        tmax=tmax.to_numpy(),
        ea=ea,
        rs=rs,
        u2=u2,
        latitude_deg=latitude_deg,
        elevation_m=elevation_m,
        day_of_year=doy,
    )
    hs = fao.et0_hargreaves(
        tmin=tmin.to_numpy(), tmax=tmax.to_numpy(), latitude_deg=latitude_deg, day_of_year=doy
    )

    has_temp = np.isfinite(tmin.to_numpy()) & np.isfinite(tmax.to_numpy())
    has_pm = has_temp & np.isfinite(ea) & np.isfinite(u2) & np.isfinite(rs)

    df["u2"] = u2
    # RHmin is needed for the FAO-56 Kc climate adjustment. When only dew point is available,
    # estimate it as 100 * e°(Tdew) / e°(Tmax); the derivation is flagged in `rhmin_derived`.
    if "rhmin" not in df or df["rhmin"].isna().all():
        derived = 100.0 * ea / fao.saturation_vapour_pressure(tmax.to_numpy())
        df["rhmin"] = np.clip(derived, 0.0, 100.0)
        df["rhmin_derived"] = np.isfinite(df["rhmin"])
    df["et0"] = np.where(has_pm, pm, np.where(has_temp, hs, np.nan))
    df["et0_method"] = np.where(has_pm, METHOD_PM, np.where(has_temp, METHOD_HS, METHOD_MISSING))
    return df
