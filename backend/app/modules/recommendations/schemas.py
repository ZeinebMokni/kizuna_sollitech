from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class RecommendationRunRequest(BaseModel):
    zone_id: UUID | None = None
    as_of: datetime | None = None
    include_model_fallback: bool = False


class RecommendationResponse(BaseModel):
    id: UUID
    farm_id: UUID
    zone_id: UUID | None
    model_id: str
    model_version: str
    validation_status: str
    status: Literal["pending", "approved", "rejected", "superseded", "expired"]
    confidence: Literal["high", "medium", "low", "insufficient_evidence"]
    inputs_hash: str
    payload: dict
    limitations: list[str]
    generated_at: datetime


class ApprovalRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=2000)


class ApprovalResponse(BaseModel):
    id: UUID
    recommendation_id: UUID
    decision: Literal["approved", "rejected"]
    note: str | None
    created_at: datetime
