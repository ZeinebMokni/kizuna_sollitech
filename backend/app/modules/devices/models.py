import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, pg_enum
from app.core.enums import (
    DataClass,
    DeviceStatus,
    MeasurementQuality,
    SensorKind,
)
from app.core.ids import uuid7


class Device(Base, TimestampMixin):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE")
    )
    external_id: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[DeviceStatus] = mapped_column(pg_enum(DeviceStatus, "device_status"))
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    firmware_version: Mapped[str | None] = mapped_column(String(64))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("farm_id", "external_id", name="uq_devices_farm_external"),
        Index("ix_devices_farm_status", "farm_id", "status"),
    )


class Sensor(Base, TimestampMixin):
    __tablename__ = "sensors"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE")
    )
    zone_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("irrigation_zones.id", ondelete="SET NULL")
    )
    external_id: Mapped[str] = mapped_column(String(120))
    kind: Mapped[SensorKind] = mapped_column(pg_enum(SensorKind, "sensor_kind"))
    unit: Mapped[str] = mapped_column(String(32))
    calibration_status: Mapped[str] = mapped_column(String(32), default="uncalibrated")
    calibration_metadata: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint("device_id", "external_id", name="uq_sensors_device_external"),
        Index("ix_sensors_zone_kind", "zone_id", "kind"),
    )


class SensorMeasurement(Base, TimestampMixin):
    __tablename__ = "sensor_measurements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    sensor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sensors.id", ondelete="CASCADE")
    )
    zone_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("irrigation_zones.id", ondelete="SET NULL")
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
    )
    value: Mapped[float] = mapped_column(Numeric(14, 6))
    unit: Mapped[str] = mapped_column(String(32))
    quality: Mapped[MeasurementQuality] = mapped_column(
        pg_enum(MeasurementQuality, "measurement_quality")
    )
    quality_note: Mapped[str | None] = mapped_column(Text)
    data_class: Mapped[DataClass] = mapped_column(
        pg_enum(DataClass, "data_class"),
        default=DataClass.MEASURED,
    )
    ingestion_idempotency_key: Mapped[str | None] = mapped_column(String(128))

    __table_args__ = (
        UniqueConstraint(
            "sensor_id",
            "observed_at",
            name="uq_sensor_measurements_sensor_timestamp",
        ),
        Index("ix_sensor_measurements_zone_time", "zone_id", "observed_at"),
        Index("ix_sensor_measurements_sensor_time", "sensor_id", "observed_at"),
    )


class IrrigationEvent(Base, TimestampMixin):
    __tablename__ = "irrigation_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE")
    )
    zone_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("irrigation_zones.id", ondelete="CASCADE")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
    )
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    volume_m3: Mapped[float] = mapped_column(Numeric(12, 3))
    source: Mapped[str] = mapped_column(String(64))
    data_class: Mapped[DataClass] = mapped_column(
        pg_enum(DataClass, "data_class")
    )
    import_idempotency_key: Mapped[str | None] = mapped_column(String(128))

    __table_args__ = (
        UniqueConstraint(
            "farm_id",
            "zone_id",
            "started_at",
            "ended_at",
            "source",
            name="uq_irrigation_event",
        ),
        Index("ix_irrigation_events_zone_time", "zone_id", "started_at"),
    )


class DeviceCommunication(Base, TimestampMixin):
    __tablename__ = "device_communications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE")
    )
    protocol: Mapped[str] = mapped_column(String(16), default="mqtt")
    topic: Mapped[str] = mapped_column(String(300))
    event: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    payload_sha256: Mapped[str] = mapped_column(String(64))
    detail: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("ix_device_communications_device_time", "device_id", "received_at"),
        Index("ix_device_communications_status_time", "status", "received_at"),
    )
