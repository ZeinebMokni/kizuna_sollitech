"""Reference evapotranspiration (ET0) following FAO Irrigation and Drainage Paper 56.

Allen, R.G., Pereira, L.S., Raes, D., Smith, M. (1998). Crop evapotranspiration:
Guidelines for computing crop water requirements. FAO-56, Rome.

Equation numbers in docstrings refer to FAO-56. All functions accept scalars or
numpy arrays (and therefore pandas Series) and are vectorised.

Units: temperature degC, pressure kPa, radiation MJ m-2 day-1, wind m s-1,
elevation m, latitude decimal degrees (north positive), ET0 mm day-1.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

ArrayLike = float | npt.NDArray[np.float64]

SOLAR_CONSTANT = 0.0820  # MJ m-2 min-1
STEFAN_BOLTZMANN = 4.903e-9  # MJ K-4 m-2 day-1
ALBEDO_GRASS = 0.23


# --- Atmospheric parameters --------------------------------------------------------------


def atmospheric_pressure(elevation_m: ArrayLike) -> ArrayLike:
    """Eq. 7: P [kPa] from elevation."""
    return 101.3 * ((293.0 - 0.0065 * np.asarray(elevation_m)) / 293.0) ** 5.26


def psychrometric_constant(pressure_kpa: ArrayLike) -> ArrayLike:
    """Eq. 8: gamma [kPa degC-1]."""
    return 0.665e-3 * np.asarray(pressure_kpa)


def saturation_vapour_pressure(t: ArrayLike) -> ArrayLike:
    """Eq. 11: e°(T) [kPa]."""
    t = np.asarray(t, dtype=float)
    return 0.6108 * np.exp(17.27 * t / (t + 237.3))


def mean_saturation_vapour_pressure(tmin: ArrayLike, tmax: ArrayLike) -> ArrayLike:
    """Eq. 12: es [kPa], the mean of e° at Tmax and Tmin (not e° at Tmean)."""
    return (saturation_vapour_pressure(tmax) + saturation_vapour_pressure(tmin)) / 2.0


def slope_vapour_pressure_curve(t: ArrayLike) -> ArrayLike:
    """Eq. 13: Delta [kPa degC-1] at air temperature t."""
    t = np.asarray(t, dtype=float)
    return 4098.0 * saturation_vapour_pressure(t) / (t + 237.3) ** 2


def actual_vapour_pressure_from_tdew(tdew: ArrayLike) -> ArrayLike:
    """Eq. 14: ea [kPa] from dew-point temperature (preferred method)."""
    return saturation_vapour_pressure(tdew)


def actual_vapour_pressure_from_rh(
    tmin: ArrayLike, tmax: ArrayLike, rhmin: ArrayLike, rhmax: ArrayLike
) -> ArrayLike:
    """Eq. 17: ea [kPa] from daily RHmax and RHmin [%]."""
    return (
        saturation_vapour_pressure(tmin) * np.asarray(rhmax) / 100.0
        + saturation_vapour_pressure(tmax) * np.asarray(rhmin) / 100.0
    ) / 2.0


def wind_speed_at_2m(wind_speed: ArrayLike, measurement_height_m: float) -> ArrayLike:
    """Eq. 47: convert wind speed measured at height z to 2 m."""
    return np.asarray(wind_speed) * 4.87 / np.log(67.8 * measurement_height_m - 5.42)


# --- Radiation ---------------------------------------------------------------------------


def inverse_relative_distance(day_of_year: ArrayLike) -> ArrayLike:
    """Eq. 23: dr, inverse relative Earth-Sun distance."""
    return 1.0 + 0.033 * np.cos(2.0 * np.pi * np.asarray(day_of_year) / 365.0)


def solar_declination(day_of_year: ArrayLike) -> ArrayLike:
    """Eq. 24: delta [rad]."""
    return 0.409 * np.sin(2.0 * np.pi * np.asarray(day_of_year) / 365.0 - 1.39)


def sunset_hour_angle(latitude_rad: ArrayLike, declination_rad: ArrayLike) -> ArrayLike:
    """Eq. 25: omega_s [rad]. Clipped so polar day/night do not produce NaN."""
    x = -np.tan(latitude_rad) * np.tan(declination_rad)
    return np.arccos(np.clip(x, -1.0, 1.0))


def extraterrestrial_radiation(latitude_deg: ArrayLike, day_of_year: ArrayLike) -> ArrayLike:
    """Eq. 21: Ra [MJ m-2 day-1]."""
    phi = np.radians(latitude_deg)
    dr = inverse_relative_distance(day_of_year)
    delta = solar_declination(day_of_year)
    ws = sunset_hour_angle(phi, delta)
    return (
        (24.0 * 60.0 / np.pi)
        * SOLAR_CONSTANT
        * dr
        * (ws * np.sin(phi) * np.sin(delta) + np.cos(phi) * np.cos(delta) * np.sin(ws))
    )


def daylight_hours(latitude_deg: ArrayLike, day_of_year: ArrayLike) -> ArrayLike:
    """Eq. 34: N [h]."""
    ws = sunset_hour_angle(np.radians(latitude_deg), solar_declination(day_of_year))
    return 24.0 / np.pi * ws


def solar_radiation_from_sunshine(
    sunshine_hours: ArrayLike,
    daylight_hours_: ArrayLike,
    ra: ArrayLike,
    a_s: float = 0.25,
    b_s: float = 0.50,
) -> ArrayLike:
    """Eq. 35 (Angstrom): Rs [MJ m-2 day-1] from actual sunshine duration n."""
    return (a_s + b_s * np.asarray(sunshine_hours) / np.asarray(daylight_hours_)) * ra


def clear_sky_radiation(ra: ArrayLike, elevation_m: ArrayLike) -> ArrayLike:
    """Eq. 37: Rso [MJ m-2 day-1]."""
    return (0.75 + 2e-5 * np.asarray(elevation_m)) * ra


def net_shortwave_radiation(rs: ArrayLike, albedo: float = ALBEDO_GRASS) -> ArrayLike:
    """Eq. 38: Rns [MJ m-2 day-1]."""
    return (1.0 - albedo) * np.asarray(rs)


def net_longwave_radiation(
    tmin: ArrayLike, tmax: ArrayLike, ea: ArrayLike, rs: ArrayLike, rso: ArrayLike
) -> ArrayLike:
    """Eq. 39: Rnl [MJ m-2 day-1]. Rs/Rso is limited to <= 1.0 as FAO-56 requires."""
    tmax_k4 = (np.asarray(tmax) + 273.16) ** 4
    tmin_k4 = (np.asarray(tmin) + 273.16) ** 4
    ratio = np.clip(np.asarray(rs) / np.asarray(rso), 0.0, 1.0)
    return (
        STEFAN_BOLTZMANN
        * (tmax_k4 + tmin_k4)
        / 2.0
        * (0.34 - 0.14 * np.sqrt(ea))
        * (1.35 * ratio - 0.35)
    )


# --- ET0 equations -----------------------------------------------------------------------


def et0_penman_monteith(
    *,
    tmin: ArrayLike,
    tmax: ArrayLike,
    ea: ArrayLike,
    rs: ArrayLike,
    u2: ArrayLike,
    latitude_deg: ArrayLike,
    elevation_m: ArrayLike,
    day_of_year: ArrayLike,
    soil_heat_flux: ArrayLike = 0.0,
) -> ArrayLike:
    """Eq. 6: FAO-56 Penman-Monteith reference ET0 [mm day-1] on a daily time step.

    G is ~0 for daily steps (Eq. 42). Mean temperature is (Tmax + Tmin) / 2 (Eq. 9).
    """
    tmean = (np.asarray(tmin) + np.asarray(tmax)) / 2.0
    delta = slope_vapour_pressure_curve(tmean)
    gamma = psychrometric_constant(atmospheric_pressure(elevation_m))
    es = mean_saturation_vapour_pressure(tmin, tmax)
    ra = extraterrestrial_radiation(latitude_deg, day_of_year)
    rso = clear_sky_radiation(ra, elevation_m)
    rn = net_shortwave_radiation(rs) - net_longwave_radiation(tmin, tmax, ea, rs, rso)

    numerator = 0.408 * delta * (rn - soil_heat_flux) + gamma * (900.0 / (tmean + 273.0)) * u2 * (
        es - ea
    )
    denominator = delta + gamma * (1.0 + 0.34 * np.asarray(u2))
    return np.maximum(numerator / denominator, 0.0)


def et0_hargreaves(
    *, tmin: ArrayLike, tmax: ArrayLike, latitude_deg: ArrayLike, day_of_year: ArrayLike
) -> ArrayLike:
    """Eq. 52: Hargreaves-Samani ET0 [mm day-1]. Temperature-only fallback.

    FAO-56 recommends it only when radiation, humidity and wind data are unavailable.
    Expect larger errors, especially in windy or humid coastal conditions.
    """
    tmean = (np.asarray(tmin) + np.asarray(tmax)) / 2.0
    ra = extraterrestrial_radiation(latitude_deg, day_of_year)
    trange = np.maximum(np.asarray(tmax) - np.asarray(tmin), 0.0)
    return np.maximum(0.0023 * (tmean + 17.8) * np.sqrt(trange) * 0.408 * ra, 0.0)
