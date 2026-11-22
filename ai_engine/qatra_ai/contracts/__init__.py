"""Typed contracts shared by every QATRA AI module (see AI_ENGINE_BLUEPRINT.md section 8).

Rules:
- Physical values cross module boundaries as `Quantity` (value + unit), never bare floats.
- Every engine output is wrapped in `EngineEnvelope`, which carries provenance, the model's
  validation status, confidence and limitations.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "0.1"


class DataClass(StrEnum):
    MEASURED = "measured"
    OFFICIAL = "official"
    FARMER_REPORTED = "farmer_reported"
    REMOTE_SENSED = "remote_sensed"
    INFERRED = "inferred"
    SIMULATED = "simulated"
    PROJECTED = "projected"
    WEB_REPORTED = "web_reported"  # figures read from web pages by an agent; unverified


class ValidationStatus(StrEnum):
    """How far a model has been checked against reality. Never upgrade without evidence."""

    LITERATURE_PARAMETERISED = "literature_parameterised"
    SIMULATION_TESTED = "simulation_tested"
    PILOT_VALIDATED = "pilot_validated"
    FIELD_VALIDATED = "field_validated"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


QualityGrade = Literal["A", "B", "C", "D"]
"""A: measured & calibrated. B: measured uncalibrated, or official. C: remote/inferred.
D: simulated or projected."""

CalibrationStatus = Literal[
    "calibrated", "factory_default", "uncalibrated", "expired", "not_applicable"
]


class Quantity(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: float
    unit: str
    interval: tuple[float, float] | None = None
    interval_kind: (
        Literal["quantile_10_90", "ensemble_range", "ci_95", "plus_minus_1_std"] | None
    ) = None


class Provenance(BaseModel):
    model_config = ConfigDict(frozen=True)

    data_class: DataClass
    source: str
    quality_grade: QualityGrade
    observed_at: datetime | None = None
    calibration_status: CalibrationStatus = "not_applicable"
    method: str | None = None


class ModelInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    model_id: str
    version: str
    validation_status: ValidationStatus
    references: list[str] = Field(default_factory=list)
    evaluation_ref: str | None = None


class EngineEnvelope[P: BaseModel](BaseModel):
    schema_version: str = SCHEMA_VERSION
    request_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    engine: str
    model: ModelInfo
    inputs_hash: str
    provenance_summary: dict[DataClass, int] = Field(default_factory=dict)
    confidence: Confidence
    confidence_reasons: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    payload: P | None = None  # None only when confidence == insufficient_evidence


def inputs_hash(obj: Any) -> str:
    """Deterministic SHA-256 of any JSON-serialisable input snapshot (for reproducibility)."""
    canonical = json.dumps(obj, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
