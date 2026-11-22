from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class Source(BaseModel):
    name: str
    source_type: Literal["sensor", "satellite", "weather", "market", "human", "system"]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    quality: Literal["good", "suspect", "missing"] = "good"


class ZoneSnapshot(BaseModel):
    zone_id: str
    moisture_percent: float = Field(ge=0, le=100)
    target_min_percent: float = Field(ge=0, le=100)
    target_max_percent: float = Field(ge=0, le=100)
    temperature_c: float | None = None
    irrigation_active: bool = False
    crop_type: str | None = None


class EnergySnapshot(BaseModel):
    solar_kw: float = Field(ge=0)
    pump_kw: float = Field(ge=0)
    battery_soc_percent: float = Field(ge=0, le=100)
    battery_power_kw: float = 0
    grid_available: bool = True


class DecisionRequest(BaseModel):
    farm_id: str
    zones: list[ZoneSnapshot]
    energy: EnergySnapshot
    sources: list[Source] = []
    emergency_stop: bool = False
    human_validation: bool = True


class AgentFinding(BaseModel):
    agent_id: str
    focus: str
    status: Literal["ok", "warning", "critical", "blocked"]
    observation: str
    recommendation: str
    confidence: int = Field(ge=0, le=100)
    sources: list[str]
    checkpoints: list[str]


class DecisionResponse(BaseModel):
    decision_id: str
    farm_id: str
    status: Literal["proposed", "blocked", "human_review"]
    recommendation: str
    expected_impact: dict[str, Any]
    findings: list[AgentFinding]
    sources: list[Source]
    human_validation_required: bool
    created_at: datetime
