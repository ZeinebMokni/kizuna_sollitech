from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SatelliteObservationCreate(BaseModel):
    parcel_id: UUID | None = None
    observed_at: datetime
    acquisition_date: date
    provider: str = "Copernicus"
    product: str = "Sentinel-2"
    ndvi: float | None = Field(default=None, ge=-1, le=1)
    cloud_pct: float | None = Field(default=None, ge=0, le=100)
    resolution_m: float | None = Field(default=None, gt=0)
    scene_id: str | None = None


class OptimizationRunCreate(BaseModel):
    period_label: str = Field(min_length=2, max_length=100)
    farms: list[dict]
    aquifers: list[dict]
    policy: dict = Field(default_factory=dict)
    strategies: list[str] = Field(
        default=["S1", "S2", "S3", "S4", "S5", "S6"],
    )


class ClimateScenarioCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    kind: Literal["historical", "projected", "hypothetical"]
    temperature_delta_c: float = 0
    precipitation_pct: float = 0
    radiation_pct: float = 0
    baseline_period: str | None = None
    future_window: str | None = None
    model_name: str | None = None


class IncidentCreate(BaseModel):
    incident_type: str = Field(min_length=2, max_length=64)
    occurred_at: datetime
    description: str = Field(min_length=10, max_length=5000)


class EvidenceCreate(BaseModel):
    evidence_type: str = Field(min_length=2, max_length=64)
    description: str = Field(min_length=2, max_length=5000)
    file_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source: str = Field(min_length=2, max_length=200)
    observed_at: datetime | None = None
