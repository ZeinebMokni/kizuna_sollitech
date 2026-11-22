"""Yield response to water deficit (FAO-33) and to salinity (FAO-29).

FAO-33 (Doorenbos & Kassam, 1979):   1 - Ya/Ym = Ky (1 - ETa/ETm)
Stage-wise (multiplicative form):     Ya/Ym = prod_s [1 - Ky_s (1 - ETa_s/ETm_s)]
FAO-29 salinity:                      Y/Ym = 1 - b/100 (ECe - ECe_threshold), ECe > threshold

All results are *relative* yields in [0, 1]. Absolute yield needs a locally known Ym.
"""

from __future__ import annotations

import pandas as pd

from qatra_ai.agronomy.crops import STAGES, CropProfile, Salinity


def relative_yield_seasonal(ky: float, eta: float, etm: float) -> float:
    if etm <= 0:
        raise ValueError("ETm must be > 0")
    if eta < 0 or ky <= 0:
        raise ValueError("ETa must be >= 0 and Ky > 0")
    return max(0.0, min(1.0, 1.0 - ky * (1.0 - min(eta / etm, 1.0))))


def relative_yield_stagewise(
    crop: CropProfile, daily: pd.DataFrame
) -> tuple[float | None, list[str]]:
    """Stage-wise relative yield from a water-balance table (columns stage, eta_mm, etc_mm).

    Returns (None, reasons) if any stage lacks a Ky value or has no simulated days.
    """
    reasons: list[str] = []
    ratio = 1.0
    for stage in STAGES:
        ky = getattr(crop.ky_stage, stage)
        rows = daily[daily["stage"] == stage]
        if ky is None:
            reasons.append(f"no Ky for stage '{stage}'")
            continue
        if rows.empty:
            reasons.append(f"stage '{stage}' not simulated")
            continue
        etm = rows["etc_mm"].sum()
        if etm <= 0:
            continue
        ratio *= 1.0 - ky * (1.0 - min(rows["eta_mm"].sum() / etm, 1.0))
    if reasons:
        return None, reasons
    return max(0.0, ratio), []


def relative_yield_salinity(ece_ds_m: float, salinity: Salinity) -> float:
    excess = max(ece_ds_m - salinity.threshold_ece_ds_m, 0.0)
    return max(0.0, 1.0 - salinity.slope_pct_per_ds_m / 100.0 * excess)
