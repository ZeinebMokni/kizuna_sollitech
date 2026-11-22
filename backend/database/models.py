from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .session import Base


Json = dict[str, Any]


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    role: Mapped[str] = mapped_column(String(40), default="farmer")
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    privacy_scope: Mapped[str] = mapped_column(String(40), default="private")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    farms: Mapped[list[FarmMembership]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Farm(Base):
    __tablename__ = "farms"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(180))
    governorate: Mapped[str | None] = mapped_column(String(100), nullable=True)
    delegation: Mapped[str | None] = mapped_column(String(100), nullable=True)
    area_ha: Mapped[float | None] = mapped_column(Float, nullable=True)
    center_geojson: Mapped[Json | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active")
    privacy_mode: Mapped[str] = mapped_column(String(30), default="private")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    memberships: Mapped[list[FarmMembership]] = relationship(back_populates="farm", cascade="all, delete-orphan")
    zones: Mapped[list[FarmZone]] = relationship(back_populates="farm", cascade="all, delete-orphan")
    devices: Mapped[list[Device]] = relationship(back_populates="farm", cascade="all, delete-orphan")
    decisions: Mapped[list[Decision]] = relationship(back_populates="farm", cascade="all, delete-orphan")
    alerts: Mapped[list[Alert]] = relationship(back_populates="farm", cascade="all, delete-orphan")
    connections_from: Mapped[list[FarmConnection]] = relationship(
        foreign_keys="FarmConnection.source_farm_id", back_populates="source_farm", cascade="all, delete-orphan"
    )
    connections_to: Mapped[list[FarmConnection]] = relationship(
        foreign_keys="FarmConnection.target_farm_id", back_populates="target_farm", cascade="all, delete-orphan"
    )


class FarmMembership(Base):
    __tablename__ = "farm_memberships"
    __table_args__ = (UniqueConstraint("farm_id", "user_id", name="uq_farm_user"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[str] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(40), default="owner")
    user: Mapped[User] = relationship(back_populates="farms")
    farm: Mapped[Farm] = relationship(back_populates="memberships")


class FarmZone(Base):
    __tablename__ = "farm_zones"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    farm_id: Mapped[str] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    crop_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    area_ha: Mapped[float | None] = mapped_column(Float, nullable=True)
    polygon_geojson: Mapped[Json | None] = mapped_column(JSONB, nullable=True)
    target_moisture_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_moisture_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="healthy")
    farm: Mapped[Farm] = relationship(back_populates="zones")
    telemetry: Mapped[list[TelemetryReading]] = relationship(back_populates="zone", cascade="all, delete-orphan")
    decisions: Mapped[list[Decision]] = relationship(back_populates="zone", cascade="all, delete-orphan")
    ndvi_observations: Mapped[list[NdviObservation]] = relationship(back_populates="zone", cascade="all, delete-orphan")


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    farm_id: Mapped[str] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("farm_zones.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(50))
    protocol: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="offline")
    metadata_json: Mapped[Json | None] = mapped_column(JSONB, nullable=True)
    farm: Mapped[Farm] = relationship(back_populates="devices")
    readings: Mapped[list[TelemetryReading]] = relationship(back_populates="device", cascade="all, delete-orphan")


class TelemetryReading(Base):
    __tablename__ = "telemetry_readings"
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("farm_zones.id", ondelete="SET NULL"), nullable=True, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    measurements: Mapped[Json] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(String(80), default="esp32")
    data_class: Mapped[str] = mapped_column(String(40), default="measured")
    device: Mapped[Device] = relationship(back_populates="readings")
    zone: Mapped[FarmZone | None] = relationship(back_populates="telemetry")


class WeatherObservation(Base):
    __tablename__ = "weather_observations"
    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[str] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    current: Mapped[Json] = mapped_column(JSONB)
    forecast: Mapped[Json | None] = mapped_column(JSONB, nullable=True)
    source: Mapped[str] = mapped_column(String(120), default="Open-Meteo")
    api_key_required: Mapped[bool] = mapped_column(Boolean, default=False)


class Agent(Base):
    __tablename__ = "agents"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    focus: Mapped[str] = mapped_column(String(160))
    version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    decisions: Mapped[list[Decision]] = relationship(back_populates="agent")


class Decision(Base):
    __tablename__ = "decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[str] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("farm_zones.id", ondelete="SET NULL"), nullable=True, index=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    decision_type: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40), default="proposed")
    recommendation: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    predicted_impact: Mapped[Json | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    farm: Mapped[Farm] = relationship(back_populates="decisions")
    zone: Mapped[FarmZone | None] = relationship(back_populates="decisions")
    agent: Mapped[Agent] = relationship(back_populates="decisions")
    evidence: Mapped[list[DecisionEvidence]] = relationship(back_populates="decision", cascade="all, delete-orphan")
    checkpoints: Mapped[list[Checkpoint]] = relationship(back_populates="decision", cascade="all, delete-orphan")
    commands: Mapped[list[IrrigationCommand]] = relationship(back_populates="decision")


class DecisionEvidence(Base):
    __tablename__ = "decision_evidence"
    id: Mapped[int] = mapped_column(primary_key=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[str] = mapped_column(String(60))
    source_ref: Mapped[str] = mapped_column(String(255))
    data_class: Mapped[str] = mapped_column(String(40), default="measured")
    payload: Mapped[Json | None] = mapped_column(JSONB, nullable=True)
    decision: Mapped[Decision] = relationship(back_populates="evidence")


class Checkpoint(Base):
    __tablename__ = "checkpoints"
    id: Mapped[int] = mapped_column(primary_key=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(220))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    required_human: Mapped[bool] = mapped_column(Boolean, default=True)
    completed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision: Mapped[Decision] = relationship(back_populates="checkpoints")


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[str] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("farm_zones.id", ondelete="SET NULL"), nullable=True)
    severity: Mapped[str] = mapped_column(String(30), index=True)
    category: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(220))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    farm: Mapped[Farm] = relationship(back_populates="alerts")


class IrrigationCommand(Base):
    __tablename__ = "irrigation_commands"
    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[str] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    zone_id: Mapped[str] = mapped_column(ForeignKey("farm_zones.id", ondelete="CASCADE"), index=True)
    decision_id: Mapped[int | None] = mapped_column(ForeignKey("decisions.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(30))
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="queued")
    mqtt_topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    decision: Mapped[Decision | None] = relationship(back_populates="commands")


class SatelliteScene(Base):
    __tablename__ = "satellite_scenes"
    id: Mapped[str] = mapped_column(String(180), primary_key=True)
    farm_id: Mapped[str] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    sensor: Mapped[str] = mapped_column(String(80), default="Sentinel-2")
    cloud_cover_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[Json | None] = mapped_column(JSONB, nullable=True)


class NdviObservation(Base):
    __tablename__ = "ndvi_observations"
    id: Mapped[int] = mapped_column(primary_key=True)
    scene_id: Mapped[str] = mapped_column(ForeignKey("satellite_scenes.id", ondelete="CASCADE"), index=True)
    zone_id: Mapped[str] = mapped_column(ForeignKey("farm_zones.id", ondelete="CASCADE"), index=True)
    ndvi_min: Mapped[float] = mapped_column(Float)
    ndvi_mean: Mapped[float] = mapped_column(Float)
    ndvi_max: Mapped[float] = mapped_column(Float)
    ndvi_std: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_class: Mapped[str] = mapped_column(String(40), default="inferred")
    zone: Mapped[FarmZone] = relationship(back_populates="ndvi_observations")


class FarmConnection(Base):
    __tablename__ = "farm_connections"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_farm_id: Mapped[str] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    target_farm_id: Mapped[str] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="proposed")
    shared_resources: Mapped[Json | None] = mapped_column(JSONB, nullable=True)
    impact_projection: Mapped[Json | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    source_farm: Mapped[Farm] = relationship(foreign_keys=[source_farm_id], back_populates="connections_from")
    target_farm: Mapped[Farm] = relationship(foreign_keys=[target_farm_id], back_populates="connections_to")


class MarketplaceListing(Base):
    __tablename__ = "marketplace_listings"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    farm_id: Mapped[str] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("farm_zones.id", ondelete="SET NULL"), nullable=True)
    crop_type: Mapped[str] = mapped_column(String(120))
    quantity_kg: Mapped[float] = mapped_column(Float)
    asking_price_tnd_kg: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(30), default="active")
    cost_per_m2_tnd: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_revenue_tnd: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_profit_tnd: Mapped[float | None] = mapped_column(Float, nullable=True)


class ImpactMeasurement(Base):
    __tablename__ = "impact_measurements"
    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[str] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("farm_zones.id", ondelete="SET NULL"), nullable=True)
    decision_id: Mapped[int | None] = mapped_column(ForeignKey("decisions.id", ondelete="SET NULL"), nullable=True)
    metric: Mapped[str] = mapped_column(String(80))
    baseline_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    observed_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(30))
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    source: Mapped[str] = mapped_column(String(120))
