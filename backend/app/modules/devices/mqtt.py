from __future__ import annotations

import hashlib
import json
import threading
from datetime import UTC, datetime
from uuid import UUID

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from sqlalchemy import select

from app.core.db import new_session
from app.core.enums import DataClass, DeviceStatus, MeasurementQuality
from app.modules.devices.models import (
    Device,
    DeviceCommunication,
    Sensor,
    SensorMeasurement,
)


class MqttTelemetryError(ValueError):
    pass


def parse_topic(topic: str) -> tuple[UUID, UUID, str]:
    parts = topic.strip("/").split("/")
    if len(parts) != 5 or parts[:1] != ["qatra"] or parts[3] != "measurements":
        raise MqttTelemetryError(
            "topic must be qatra/{farm_id}/{device_id}/measurements/{sensor_id}"
        )
    try:
        farm_id = UUID(parts[1])
        device_id = UUID(parts[2])
    except ValueError as exc:
        raise MqttTelemetryError("topic contains an invalid farm or device UUID") from exc
    return farm_id, device_id, parts[4]


def parse_payload(payload: bytes) -> dict:
    digest = hashlib.sha256(payload).hexdigest()
    try:
        body = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MqttTelemetryError(f"payload is not valid JSON: {exc}") from exc
    if not isinstance(body, dict):
        raise MqttTelemetryError("payload must be a JSON object")
    required = {"api_key", "observed_at", "value", "unit"}
    missing = required - set(body)
    if missing:
        raise MqttTelemetryError(f"missing fields: {sorted(missing)}")
    if not isinstance(body["api_key"], str) or not body["api_key"].strip():
        raise MqttTelemetryError("api_key must be a non-empty string")
    try:
        observed_at = datetime.fromisoformat(str(body["observed_at"]).replace("Z", "+00:00"))
        value = float(body["value"])
    except (TypeError, ValueError) as exc:
        raise MqttTelemetryError(f"invalid observed_at or value: {exc}") from exc
    if observed_at.tzinfo is None:
        raise MqttTelemetryError("observed_at must include a timezone")
    if observed_at > datetime.now(UTC):
        raise MqttTelemetryError("observed_at cannot be in the future")
    quality = str(body.get("quality", "valid"))
    if quality not in {item.value for item in MeasurementQuality}:
        raise MqttTelemetryError(f"unknown quality: {quality}")
    body["_observed_at"] = observed_at
    body["_value"] = value
    body["_quality"] = quality
    body["_sha256"] = digest
    return body


class MqttTelemetryService:
    def __init__(self, host: str, port: int, topic: str):
        self.host = host
        self.port = port
        self.topic = topic
        self.client = mqtt.Client(CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self.client.connect_async(self.host, self.port, keepalive=30)
        self.client.loop_start()

    def stop(self) -> None:
        self.client.disconnect()
        self.client.loop_stop()

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code == 0:
            client.subscribe(self.topic, qos=1)

    def _record(
        self,
        device_id: UUID,
        topic: str,
        event: str,
        status: str,
        sha256: str,
        detail: str | None,
    ) -> None:
        db = new_session()
        try:
            if db.get(Device, device_id) is not None:
                db.add(
                    DeviceCommunication(
                        device_id=device_id,
                        protocol="mqtt",
                        topic=topic,
                        event=event,
                        status=status,
                        payload_sha256=sha256,
                        detail=detail,
                        received_at=datetime.now(UTC),
                    )
                )
                db.commit()
        finally:
            db.close()

    def _on_message(self, client, userdata, message) -> None:
        topic = message.topic
        payload = bytes(message.payload)
        try:
            farm_id, device_id, sensor_external_id = parse_topic(topic)
            body = parse_payload(payload)
        except MqttTelemetryError:
            return

        db = new_session()
        try:
            device = db.get(Device, device_id)
            if device is None or device.farm_id != farm_id:
                self._record(
                    device_id,
                    topic,
                    "measurement",
                    "rejected",
                    body["_sha256"],
                    "unknown device or farm",
                )
                return
            supplied_hash = hashlib.sha256(body["api_key"].encode()).hexdigest()
            if supplied_hash != device.api_key_hash:
                self._record(
                    device_id,
                    topic,
                    "measurement",
                    "rejected",
                    body["_sha256"],
                    "invalid device key",
                )
                return
            if device.status != DeviceStatus.ACTIVE:
                self._record(
                    device_id,
                    topic,
                    "measurement",
                    "rejected",
                    body["_sha256"],
                    "device is not active",
                )
                return
            sensor = db.scalar(
                select(Sensor).where(
                    Sensor.device_id == device_id,
                    Sensor.external_id == sensor_external_id,
                    Sensor.is_active.is_(True),
                )
            )
            if sensor is None:
                self._record(
                    device_id,
                    topic,
                    "measurement",
                    "rejected",
                    body["_sha256"],
                    "unknown or inactive sensor",
                )
                return
            unit = str(body["unit"]).strip()
            if unit != sensor.unit:
                self._record(
                    device_id,
                    topic,
                    "measurement",
                    "rejected",
                    body["_sha256"],
                    f"unit mismatch: expected {sensor.unit}",
                )
                return

            idempotency_key = str(body.get("idempotency_key") or "")[:128] or None
            if idempotency_key:
                existing = db.scalar(
                    select(SensorMeasurement).where(
                        SensorMeasurement.ingestion_idempotency_key == idempotency_key
                    )
                )
                if existing is not None:
                    self._record(
                        device_id,
                        topic,
                        "measurement",
                        "duplicate",
                        body["_sha256"],
                        "idempotency key already accepted",
                    )
                    return

            existing = db.scalar(
                select(SensorMeasurement).where(
                    SensorMeasurement.sensor_id == sensor.id,
                    SensorMeasurement.observed_at == body["_observed_at"],
                )
            )
            if existing is not None:
                self._record(
                    device_id,
                    topic,
                    "measurement",
                    "duplicate",
                    body["_sha256"],
                    "sensor and timestamp already accepted",
                )
                return

            row = SensorMeasurement(
                sensor_id=sensor.id,
                zone_id=sensor.zone_id,
                observed_at=body["_observed_at"],
                value=body["_value"],
                unit=unit,
                quality=MeasurementQuality(body["_quality"]),
                quality_note=str(body.get("quality_note")) if body.get("quality_note") else None,
                data_class=DataClass.MEASURED,
                ingestion_idempotency_key=idempotency_key,
            )
            device.last_seen_at = datetime.now(UTC)
            db.add(row)
            db.flush()
            db.add(
                DeviceCommunication(
                    device_id=device_id,
                    protocol="mqtt",
                    topic=topic,
                    event="measurement",
                    status="accepted",
                    payload_sha256=body["_sha256"],
                    detail=None,
                    received_at=datetime.now(UTC),
                )
            )
            db.commit()
        finally:
            db.close()
