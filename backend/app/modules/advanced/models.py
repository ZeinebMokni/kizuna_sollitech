import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin
from app.core.ids import uuid7


class SatelliteObservation(Base, TimestampMixin):
    __tablename__ = "satellite_observations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    farm_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE")
    )
    parcel_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("parcels.id", ondelete="CASCADE")
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    acquisition_date: Mapped[date] = mapped_column(Date)
    provider: Mapped[str] = mapped_column(String(100))
    product: Mapped[str] = mapped_column(String(100))
    ndvi: Mapped[float | None] = mapped_column(Numeric(5, 4))
    cloud_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    resolution_m: Mapped[float | None] = mapped_column(Numeric(8, 2))
    scene_id: Mapped[str | None] = mapped_column(String(200))
    provenance: Mapped[dict] = mapped_column(JSONB)

    __table_args__ = (
        Index("ix_satellite_observations_farm_date", "farm_id", "acquisition_date"),
        Index("ix_satellite_observations_parcel_date", "parcel_id", "acquisition_date"),
    )


class OptimizationRun(Base, TimestampMixin):
    __tablename__ = "optimization_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    farm_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE")
    )
    period_label: Mapped[str] = mapped_column(String(100))
    model_id: Mapped[str] = mapped_column(String(120))
    model_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="computed")
    inputs_hash: Mapped[str] = mapped_column(String(64))
    request: Mapped[dict] = mapped_column(JSONB)
    result: Mapped[dict | None] = mapped_column(JSONB)
    disclaimer: Mapped[str] = mapped_column(Text)

    __table_args__ = (
        Index("ix_optimization_runs_farm_period", "farm_id", "period_label"),
    )


class ClimateScenario(Base, TimestampMixin):
    __tablename__ = "climate_scenarios"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    farm_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(32))
    assumptions: Mapped[dict] = mapped_column(JSONB)
    baseline_period: Mapped[str | None] = mapped_column(String(100))
    future_window: Mapped[str | None] = mapped_column(String(100))
    model_name: Mapped[str | None] = mapped_column(String(100))
    limitations: Mapped[list] = mapped_column(JSONB)


class Incident(Base, TimestampMixin):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE")
    )
    reported_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    incident_type: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="reported")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    description: Mapped[str] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(String(32), default="unverified")

    __table_args__ = (
        Index("ix_incidents_farm_status", "farm_id", "status"),
    )


class EvidenceRecord(Base, TimestampMixin):
    __tablename__ = "evidence_records"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE")
    )
    evidence_type: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text)
    file_hash: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(200))
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provenance: Mapped[dict] = mapped_column(JSONB)
