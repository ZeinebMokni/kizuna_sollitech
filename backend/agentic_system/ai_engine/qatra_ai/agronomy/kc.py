"""Single crop coefficient curve, growth stage and root depth (FAO-56 chapters 6 and 8)."""

from __future__ import annotations

import numpy as np

from qatra_ai.agronomy.crops import CropProfile, StageName


def stage_for_day(crop: CropProfile, day: int) -> StageName | None:
    """Growth stage on `day` (0 = first day of the season / cycle). None if outside the season."""
    if day < 0 or day >= crop.season_length_days:
        return None
    s = crop.stage_lengths_days
    if day < s.initial:
        return "initial"
    if day < s.initial + s.development:
        return "development"
    if day < s.initial + s.development + s.mid:
        return "mid"
    return "late"


def adjust_kc_for_climate(
    kc_table: float, u2_mean: float, rhmin_mean: float, height_m: float
) -> float:
    """Eq. 62 / 65: adjust Kc_mid or Kc_end for climates other than RHmin = 45 %, u2 = 2 m/s.

    Applies only when the table value is >= 0.45 (FAO-56). Inputs are clipped to the
    validity ranges given by FAO-56 (1 <= u2 <= 6 m/s, 20 <= RHmin <= 80 %, 0.1 <= h <= 10 m).
    """
    if kc_table < 0.45:
        return kc_table
    u2 = float(np.clip(u2_mean, 1.0, 6.0))
    rh = float(np.clip(rhmin_mean, 20.0, 80.0))
    h = float(np.clip(height_m, 0.1, 10.0))
    return kc_table + (0.04 * (u2 - 2.0) - 0.004 * (rh - 45.0)) * (h / 3.0) ** 0.3


def kc_for_day(
    crop: CropProfile, day: int, kc_mid: float | None = None, kc_end: float | None = None
) -> float | None:
    """Kc on `day` from the FAO-56 piecewise-linear curve (Fig. 25, Eq. 66).

    `kc_mid`/`kc_end` override the table values (e.g. climate-adjusted values).
    """
    stage = stage_for_day(crop, day)
    if stage is None:
        return None
    s = crop.stage_lengths_days
    k_ini = crop.kc.ini
    k_mid = crop.kc.mid if kc_mid is None else kc_mid
    k_end = crop.kc.end if kc_end is None else kc_end
    if stage == "initial":
        return k_ini
    if stage == "development":
        frac = (day - s.initial + 1) / s.development
        return k_ini + frac * (k_mid - k_ini)
    if stage == "mid":
        return k_mid
    start_late = s.initial + s.development + s.mid
    frac = (day - start_late + 1) / s.late
    return k_mid + frac * (k_end - k_mid)


def root_depth_for_day(crop: CropProfile, day: int, soil_depth_m: float | None = None) -> float:
    """Effective root depth Zr [m].

    Annual crops: linear growth from the initial depth to the maximum, reached at the start
    of the mid-season stage (FAO-56 section 8, simplified). Perennials: constant.
    Limited by soil depth when given.
    """
    r = crop.root_depth
    if crop.perennial:
        zr = r.max_m
    else:
        s = crop.stage_lengths_days
        t_full = s.initial + s.development
        frac = min(max(day, 0) / t_full, 1.0)
        zr = r.initial_m + frac * (r.max_m - r.initial_m)
    if soil_depth_m is not None:
        zr = min(zr, soil_depth_m)
    return zr


def adjusted_depletion_fraction(p_table: float, etc_mm: float) -> float:
    """FAO-56 Table 22 footnote: p = p_table + 0.04 (5 - ETc), limited to 0.1 <= p <= 0.8."""
    return float(np.clip(p_table + 0.04 * (5.0 - etc_mm), 0.1, 0.8))
