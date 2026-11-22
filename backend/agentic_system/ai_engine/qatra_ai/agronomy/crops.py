"""Crop profiles: the agronomic parameters each crop model needs, with citations.

Profiles live in `qatra_ai/reference_data/crops/*.yaml`. Every profile states its
`review_status`; values taken from international tables (FAO-56, FAO-33, FAO-29) are
*not* locally validated for Tunisian varieties and must be reviewed by an agronomist.
"""

from __future__ import annotations

from functools import lru_cache
from importlib import resources
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

StageName = Literal["initial", "development", "mid", "late"]
STAGES: tuple[StageName, ...] = ("initial", "development", "mid", "late")


class StageLengths(BaseModel):
    model_config = ConfigDict(frozen=True)
    initial: int = Field(gt=0)
    development: int = Field(gt=0)
    mid: int = Field(gt=0)
    late: int = Field(gt=0)

    @property
    def total(self) -> int:
        return self.initial + self.development + self.mid + self.late


class KcValues(BaseModel):
    model_config = ConfigDict(frozen=True)
    ini: float = Field(gt=0, le=1.5)
    mid: float = Field(gt=0, le=1.5)
    end: float = Field(gt=0, le=1.5)


class RootDepth(BaseModel):
    model_config = ConfigDict(frozen=True)
    initial_m: float = Field(gt=0, le=5)
    max_m: float = Field(gt=0, le=5)

    @model_validator(mode="after")
    def _ordered(self) -> RootDepth:
        if self.initial_m > self.max_m:
            raise ValueError("root initial depth must be <= max depth")
        return self


class StageKy(BaseModel):
    model_config = ConfigDict(frozen=True)
    initial: float | None = None
    development: float | None = None
    mid: float | None = None
    late: float | None = None


class Salinity(BaseModel):
    """FAO-29 salinity tolerance: yield declines `slope_pct` per dS/m above `threshold`."""

    model_config = ConfigDict(frozen=True)
    threshold_ece_ds_m: float = Field(ge=0)
    slope_pct_per_ds_m: float = Field(gt=0)


class TemperatureLimits(BaseModel):
    """Damaging temperatures. Values in the shipped profiles are PLACEHOLDERS pending review."""

    model_config = ConfigDict(frozen=True)
    heat_stress_tmax_c: float | None = None
    heat_sensitive_stages: list[StageName] = Field(default_factory=lambda: ["mid"])
    frost_damage_tmin_c: float | None = None
    frost_sensitive_stages: list[StageName] = Field(
        default_factory=lambda: ["initial", "development", "mid", "late"]
    )
    verified: bool = False


class Citation(BaseModel):
    model_config = ConfigDict(frozen=True)
    field: str
    source: str
    note: str | None = None


class CropProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    names: dict[str, str]
    perennial: bool
    stage_lengths_days: StageLengths
    kc: KcValues
    max_height_m: float = Field(gt=0)
    root_depth: RootDepth
    depletion_fraction_p: float = Field(gt=0, lt=1)
    ky_total: float | None = Field(default=None, gt=0)
    ky_stage: StageKy = StageKy()
    salinity: Salinity | None = None
    temperature: TemperatureLimits | None = None
    citations: list[Citation]
    review_status: Literal["needs_review", "reviewed_partial", "reviewed"] = "needs_review"
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _perennial_cycle(self) -> CropProfile:
        if self.perennial and self.stage_lengths_days.total != 365:
            raise ValueError(f"{self.code}: perennial stage lengths must sum to 365 days")
        return self

    @property
    def season_length_days(self) -> int:
        return self.stage_lengths_days.total


@lru_cache
def load_crop_profiles() -> dict[str, CropProfile]:
    folder = resources.files("qatra_ai.reference_data") / "crops"
    profiles: dict[str, CropProfile] = {}
    for entry in folder.iterdir():
        if entry.name.endswith((".yaml", ".yml")):
            data = yaml.safe_load(entry.read_text(encoding="utf-8"))
            profile = CropProfile.model_validate(data)
            if profile.code in profiles:
                raise ValueError(f"duplicate crop code {profile.code}")
            profiles[profile.code] = profile
    return profiles


def get_crop(code: str) -> CropProfile:
    try:
        return load_crop_profiles()[code]
    except KeyError as exc:
        raise KeyError(f"Unknown crop '{code}'. Known: {sorted(load_crop_profiles())}") from exc
