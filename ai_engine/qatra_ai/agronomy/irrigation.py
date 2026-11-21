"""Irrigation requirement: net depth -> gross depth -> volume -> runtime.

Leaching requirement follows FAO-29 (Ayers & Westcot, 1985):
    surface / sprinkler:  LR = ECw / (5 ECe_t - ECw)
    drip (high frequency): LR = ECw / (2 max ECe)
where ECe_t is the crop's threshold ECe and max ECe the ECe at 100 % yield loss.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from qatra_ai.agronomy.crops import Salinity


class IrrigationRequirement(BaseModel):
    model_config = ConfigDict(frozen=True)

    net_mm: float
    gross_mm: float
    volume_m3: float
    runtime_h: float | None
    leaching_requirement: float
    assumptions: list[str]


def leaching_requirement(
    ec_water_ds_m: float, salinity: Salinity, method: Literal["surface", "drip"]
) -> float:
    if ec_water_ds_m < 0:
        raise ValueError("ECw must be >= 0")
    if method == "surface":
        denom = 5 * salinity.threshold_ece_ds_m - ec_water_ds_m
    else:
        max_ece = salinity.threshold_ece_ds_m + 100.0 / salinity.slope_pct_per_ds_m
        denom = 2 * max_ece
    if denom <= 0:
        raise ValueError("Irrigation water too saline for this crop: leaching cannot compensate")
    lr = ec_water_ds_m / denom
    if lr >= 0.9:
        raise ValueError(f"Leaching requirement {lr:.2f} is unrealistic; water unsuitable")
    return lr


def irrigation_requirement(
    *,
    depletion_mm: float,
    area_ha: float,
    application_efficiency: float,
    target_depletion_mm: float = 0.0,
    leaching_fraction: float = 0.0,
    design_flow_m3h: float | None = None,
) -> IrrigationRequirement:
    """Depth and volume needed to bring depletion back to `target_depletion_mm`.

    target 0 = refill to field capacity; a positive target implements deficit irrigation.
    """
    if depletion_mm < 0 or area_ha <= 0:
        raise ValueError("depletion must be >= 0 and area > 0")
    if not 0 < application_efficiency <= 1:
        raise ValueError("application efficiency must be in (0, 1]")
    if not 0 <= leaching_fraction < 0.9:
        raise ValueError("leaching fraction must be in [0, 0.9)")
    if design_flow_m3h is not None and design_flow_m3h <= 0:
        raise ValueError("design flow must be > 0")

    net = max(depletion_mm - target_depletion_mm, 0.0)
    gross = net / (application_efficiency * (1 - leaching_fraction))
    volume = 10.0 * gross * area_ha  # 1 mm over 1 ha = 10 m3
    runtime = volume / design_flow_m3h if design_flow_m3h else None
    assumptions = [
        f"application efficiency {application_efficiency:.2f}",
        "refill to field capacity"
        if target_depletion_mm == 0
        else f"deficit target: leave {target_depletion_mm:.1f} mm depleted",
    ]
    if leaching_fraction:
        assumptions.append(f"leaching fraction {leaching_fraction:.3f} (FAO-29)")
    return IrrigationRequirement(
        net_mm=net,
        gross_mm=gross,
        volume_m3=volume,
        runtime_h=runtime,
        leaching_requirement=leaching_fraction,
        assumptions=assumptions,
    )
