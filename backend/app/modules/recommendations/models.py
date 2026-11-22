import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin
from app.core.ids import uuid7


class Recommendation(Base, TimestampMixin):
    __tablename__ = "ai_recommendations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE")
    )
    zone_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("irrigation_zones.id", ondelete="SET NULL")
    )
    model_id: Mapped[str] = mapped_column(String(120))
    model_version: Mapped[str] = mapped_column(String(32))
    validation_status: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    confidence: Mapped[str] = mapped_column(String(32))
    inputs_hash: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB)
    limitations: Mapped[list | None] = mapped_column(JSONB)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','rejected','superseded','expired')",
            name="recommendation_status_valid",
        ),
        Index("ix_recommendations_farm_generated", "farm_id", "generated_at"),
        Index("ix_recommendations_zone_generated", "zone_id", "generated_at"),
    )


class RecommendationApproval(Base, TimestampMixin):
    __tablename__ = "recommendation_approvals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_recommendations.id", ondelete="CASCADE")
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    decision: Mapped[str] = mapped_column(String(16))
    note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "decision IN ('approved','rejected')",
            name="approval_decision_valid",
        ),
        Index(
            "ix_recommendation_approvals_recommendation",
            "recommendation_id",
            "created_at",
        ),
    )
