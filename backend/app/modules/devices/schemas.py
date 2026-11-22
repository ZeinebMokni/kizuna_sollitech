from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import DeviceStatus, MeasurementQuality, SensorKind


class DeviceCreate(BaseModel):
    external_id: str = Field(min_length=2, max_length=120)
    name: str = Field(min_length=2, max_length=200)
    firmware_version: str | None = Field(default=None, max_length=64)


class DeviceResponse(BaseModel):
    id: UUID
    external_id: str
    name: str
    status: DeviceStatus
    firmware_version: str | None
    last_seen_at: datetime | None
    api_key: str | None = None


class SensorCreate(BaseModel):
    external_id: str = Field(min_length=1, max_length=120)
    zone_id: UUID
    kind: SensorKind
    unit: str = Field(min_length=1, max_length=32)
    calibration_status: str = Field(default="uncalibrated", max_length=32)
    calibration_metadata: str | None = None


class SensorResponse(BaseModel):
    id: UUID
    external_id: str
    zone_id: UUID | None
    kind: SensorKind
    unit: str
    calibration_status: str
    is_active: bool


class MeasurementCreate(BaseModel):
    sensor_external_id: str = Field(min_length=1, max_length=120)
    observed_at: datetime
    value: Decimal
    unit: str = Field(min_length=1, max_length=32)
    quality: MeasurementQuality = MeasurementQuality.VALID
    quality_note: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=128)


class MeasurementResponse(BaseModel):
    id: UUID
    sensor_id: UUID
    zone_id: UUID | None
    observed_at: datetime
    value: Decimal
    unit: str
    quality: MeasurementQuality
    quality_note: str | None


class IrrigationEventCreate(BaseModel):
    zone_id: UUID
    started_at: datetime
    ended_at: datetime
    volume_m3: Decimal = Field(gt=0)
    source: str = Field(default="manual", min_length=2, max_length=64)


class IrrigationEventResponse(BaseModel):
    id: UUID
    zone_id: UUID
    started_at: datetime
    ended_at: datetime
    volume_m3: Decimal
    source: str


class ActuationCommandCreate(BaseModel):
    zone_id: UUID
    action: Literal["open_valve", "close_valve", "start_pump", "stop_pump", "emergency_stop"]
    duration_s: int | None = Field(default=None, ge=1)
    max_volume_m3: Decimal | None = Field(default=None, gt=0)


class ActuationCommandResponse(BaseModel):
    id: UUID
    zone_id: UUID
    action: str
    duration_s: int | None
    max_volume_m3: Decimal | None
    status: str
    mqtt_topic: str
    expires_at: datetime
    sent_at: datetime | None
    acknowledged_at: datetime | None
    acknowledgement_status: str | None
