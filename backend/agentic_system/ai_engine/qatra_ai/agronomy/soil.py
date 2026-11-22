"""Soil water-holding properties.

Field capacity (FC) and wilting point (WP) come from, in order of preference:
1. Laboratory or field measurements (data_class=measured);
2. Pedotransfer functions of Saxton & Rawls (2006) from texture and organic matter
   (data_class=inferred).

Saxton, K.E., Rawls, W.J. (2006). Soil water characteristic estimates by texture and
organic matter for hydrologic solutions. Soil Sci. Soc. Am. J. 70:1569-1578. (Eqs. 1-2, Table 1)
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from qatra_ai.contracts import DataClass


class SoilWaterProperties(BaseModel):
    model_config = ConfigDict(frozen=True)

    theta_fc: float = Field(gt=0, lt=0.7, description="Volumetric water content at FC [m3/m3]")
    theta_wp: float = Field(ge=0, lt=0.6, description="Volumetric water content at WP [m3/m3]")
    data_class: DataClass
    source: str
    method: str
    soil_depth_m: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _fc_above_wp(self) -> SoilWaterProperties:
        if self.theta_fc <= self.theta_wp:
            raise ValueError("theta_fc must be greater than theta_wp")
        return self

    def taw_mm(self, root_depth_m: float) -> float:
        """FAO-56 Eq. 82: total available water in the root zone [mm]."""
        return 1000.0 * (self.theta_fc - self.theta_wp) * root_depth_m


def saxton_rawls(sand: float, clay: float, organic_matter_pct: float) -> tuple[float, float]:
    """Return (theta_fc, theta_wp) [m3/m3] from sand and clay fractions [0-1] and OM [% w].

    Valid roughly for OM <= 8 % and clay <= 60 % (Saxton & Rawls, 2006). No density or
    gravel correction is applied here.
    """
    if not (0 <= sand <= 1 and 0 <= clay <= 1 and sand + clay <= 1):
        raise ValueError("sand and clay must be fractions in [0, 1] with sand + clay <= 1")
    if not 0 <= organic_matter_pct <= 8:
        raise ValueError("organic matter outside the 0-8 % validity range of Saxton-Rawls")
    s, c, om = sand, clay, organic_matter_pct

    t1500 = (
        -0.024 * s
        + 0.487 * c
        + 0.006 * om
        + 0.005 * s * om
        - 0.013 * c * om
        + 0.068 * s * c
        + 0.031
    )
    theta_wp = t1500 + (0.14 * t1500 - 0.02)

    t33 = (
        -0.251 * s
        + 0.195 * c
        + 0.011 * om
        + 0.006 * s * om
        - 0.027 * c * om
        + 0.452 * s * c
        + 0.299
    )
    theta_fc = t33 + (1.283 * t33**2 - 0.374 * t33 - 0.015)
    return theta_fc, theta_wp


def soil_from_texture(
    sand: float,
    clay: float,
    organic_matter_pct: float,
    *,
    source: str,
    soil_depth_m: float | None = None,
) -> SoilWaterProperties:
    fc, wp = saxton_rawls(sand, clay, organic_matter_pct)
    return SoilWaterProperties(
        theta_fc=round(fc, 4),
        theta_wp=round(wp, 4),
        data_class=DataClass.INFERRED,
        source=source,
        method="saxton_rawls_2006",
        soil_depth_m=soil_depth_m,
    )
