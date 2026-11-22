import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from ipaddress import ip_address
from secrets import token_urlsafe
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.config import get_settings
from app.core.db import get_db
from app.core.enums import (
    DataClass,
    DeviceStatus,
    FarmRole,
)
from app.core.errors import Conflict, Forbidden, NotFound, Unauthorized, Unprocessable
from app.modules.devices.models import (
    ActuationCommand,
    Device,
    DeviceCommunication,
    IrrigationEvent,
    Sensor,
    SensorMeasurement,
)
from app.modules.devices.schemas import (
    ActuationCommandCreate,
    ActuationCommandResponse,
    DeviceCreate,
    DeviceResponse,
    IrrigationEventCreate,
    IrrigationEventResponse,
    MeasurementCreate,
    MeasurementResponse,
    SensorCreate,
    SensorResponse,
)
from app.modules.farms.models import Farm, FarmMember, IrrigationZone, Parcel
from app.modules.identity.models import User
from app.modules.identity.routes import current_user

router = APIRouter(prefix="/farms", tags=["field operations"])


def _valid_ip(host: str | None) -> str | None:
    if not host:
        return None
    try:
        return str(ip_address(host))
    except ValueError:
        return None


def _operator_member(db: Session, farm_id: UUID, user: User) -> FarmMember:
    member = db.get(FarmMember, (farm_id, user.id))
    if member is None or member.farm_role.rank < FarmRole.OPERATOR.rank:
        raise Forbidden("Owner or operator access required")
    return member


def _zone_for_farm(db: Session, farm_id: UUID, zone_id: UUID) -> IrrigationZone:
    zone = db.get(IrrigationZone, zone_id)
    if zone is None:
        raise NotFound("Irrigation zone not found")
    parcel = db.get(Parcel, zone.parcel_id)
    if parcel is None or parcel.farm_id != farm_id:
        raise Forbidden("Zone does not belong to this farm")
    return zone


def _command_response(row: ActuationCommand) -> ActuationCommandResponse:
    return ActuationCommandResponse(
        id=row.id,
        zone_id=row.zone_id,
        action=row.action,
        duration_s=row.duration_s,
        max_volume_m3=row.max_volume_m3,
        status=row.status,
        mqtt_topic=row.mqtt_topic,
        expires_at=row.expires_at,
        sent_at=row.sent_at,
        acknowledged_at=row.acknowledged_at,
        acknowledgement_status=row.acknowledgement_status,
    )


@router.post(
    "/{farm_id}/devices/{device_id}/commands",
    response_model=ActuationCommandResponse,
    status_code=201,
)
def create_actuation_command(
    farm_id: UUID,
    device_id: UUID,
    payload: ActuationCommandCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ActuationCommandResponse:
    _operator_member(db, farm_id, user)
    device = db.get(Device, device_id)
    if device is None or device.farm_id != farm_id:
        raise NotFound("Device not found")
    if device.status != DeviceStatus.ACTIVE:
        raise Forbidden("Device is not active")
    zone = _zone_for_farm(db, farm_id, payload.zone_id)

    settings = get_settings()
    if payload.action in {"open_valve", "start_pump"} and payload.duration_s is None:
        raise Unprocessable("duration_s is required for open_valve and start_pump")
    if payload.duration_s is not None and payload.duration_s > settings.actuation_max_duration_s:
        raise Unprocessable(
            f"duration_s exceeds safety limit {settings.actuation_max_duration_s}"
        )
    if (
        payload.max_volume_m3 is not None
        and float(payload.max_volume_m3) > settings.actuation_max_volume_m3
    ):
        raise Unprocessable(
            f"max_volume_m3 exceeds safety limit {settings.actuation_max_volume_m3}"
        )
    if (
        payload.action in {"close_valve", "stop_pump", "emergency_stop"}
        and (payload.duration_s is not None or payload.max_volume_m3 is not None)
    ):
        raise Unprocessable(
            "close, stop and emergency-stop commands cannot include runtime limits"
        )

    expires_at = datetime.now(UTC) + timedelta(minutes=5)
    mqtt_topic = f"qatra/{farm_id}/{device_id}/commands/{zone.id}"
    command_payload = {
        "command_id": None,
        "farm_id": str(farm_id),
        "device_id": str(device_id),
        "zone_id": str(zone.id),
        "action": payload.action,
        "duration_s": payload.duration_s,
        "max_volume_m3": (
            float(payload.max_volume_m3)
            if payload.max_volume_m3 is not None
            else None
        ),
        "expires_at": expires_at.isoformat(),
    }
    command_id = UUID(int=secrets.randbits(128), version=4)
    command_payload["command_id"] = str(command_id)
    canonical = json.dumps(command_payload, sort_keys=True, separators=(",", ":"))
    payload_hash = hashlib.sha256(canonical.encode()).hexdigest()
    secret = settings.jwt_secret.get_secret_value()
    signature = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()

    command = ActuationCommand(
        id=command_id,
        farm_id=farm_id,
        device_id=device_id,
        zone_id=zone.id,
        requested_by=user.id,
        action=payload.action,
        duration_s=payload.duration_s,
        max_volume_m3=payload.max_volume_m3,
        status="pending",
        mqtt_topic=mqtt_topic,
        payload_sha256=payload_hash,
        signature=signature,
        expires_at=expires_at,
    )
    db.add(command)
    db.flush()
    record_audit(
        db,
        action="request",
        entity_type="actuation_command",
        entity_id=command.id,
        actor_user_id=user.id,
        farm_id=farm_id,
        after={
            "device_id": str(device_id),
            "zone_id": str(zone.id),
            "action": payload.action,
            "status": "pending",
        },
    )
    db.commit()
    db.refresh(command)
    return _command_response(command)


@router.post(
    "/{farm_id}/devices/{device_id}/commands/{command_id}/approve",
    response_model=ActuationCommandResponse,
)
def approve_actuation_command(
    farm_id: UUID,
    device_id: UUID,
    command_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ActuationCommandResponse:
    _operator_member(db, farm_id, user)
    command = db.get(ActuationCommand, command_id)
    if (
        command is None
        or command.farm_id != farm_id
        or command.device_id != device_id
    ):
        raise NotFound("Actuation command not found")
    if command.status != "pending":
        raise Conflict("Actuation command is no longer pending")
    if command.expires_at <= datetime.now(UTC):
        command.status = "expired"
        db.commit()
        raise Conflict("Actuation command expired")
    if not hasattr(request.app.state, "mqtt_service"):
        raise Unprocessable("MQTT command publisher is unavailable")

    payload = {
        "command_id": str(command.id),
        "farm_id": str(command.farm_id),
        "device_id": str(command.device_id),
        "zone_id": str(command.zone_id),
        "action": command.action,
        "duration_s": command.duration_s,
        "max_volume_m3": (
            float(command.max_volume_m3)
            if command.max_volume_m3 is not None
            else None
        ),
        "expires_at": command.expires_at.isoformat(),
        "signature": command.signature,
    }
    mqtt_service = request.app.state.mqtt_service
    mqtt_service.publish(command.mqtt_topic, payload)

    command.approved_by = user.id
    command.status = "sent"
    command.sent_at = datetime.now(UTC)
    record_audit(
        db,
        action="approve",
        entity_type="actuation_command",
        entity_id=command.id,
        actor_user_id=user.id,
        farm_id=farm_id,
        after={"status": "sent", "action": command.action},
    )
    db.commit()
    db.refresh(command)
    return _command_response(command)


@router.post(
    "/{farm_id}/devices/{device_id}/commands/{command_id}/reject",
    response_model=ActuationCommandResponse,
)
def reject_actuation_command(
    farm_id: UUID,
    device_id: UUID,
    command_id: UUID,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ActuationCommandResponse:
    _operator_member(db, farm_id, user)
    command = db.get(ActuationCommand, command_id)
    if (
        command is None
        or command.farm_id != farm_id
        or command.device_id != device_id
    ):
        raise NotFound("Actuation command not found")
    if command.status != "pending":
        raise Conflict("Actuation command is no longer pending")
    command.status = "rejected"
    command.acknowledgement_detail = str(payload.get("reason") or "")[:2000] or None
    record_audit(
        db,
        action="reject",
        entity_type="actuation_command",
        entity_id=command.id,
        actor_user_id=user.id,
        farm_id=farm_id,
        after={"status": "rejected", "reason": command.acknowledgement_detail},
    )
    db.commit()
    db.refresh(command)
    return _command_response(command)


@router.get(
    "/{farm_id}/devices/{device_id}/commands",
    response_model=list[ActuationCommandResponse],
)
def list_actuation_commands(
    farm_id: UUID,
    device_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[ActuationCommandResponse]:
    _operator_member(db, farm_id, user)
    device = db.get(Device, device_id)
    if device is None or device.farm_id != farm_id:
        raise NotFound("Device not found")
    rows = list(
        db.scalars(
            select(ActuationCommand)
            .where(ActuationCommand.device_id == device_id)
            .order_by(ActuationCommand.created_at.desc())
        )
    )
    return [_command_response(row) for row in rows]


@router.get("/{farm_id}/devices/{device_id}/communications")
def list_device_communications(
    farm_id: UUID,
    device_id: UUID,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[dict]:
    _operator_member(db, farm_id, user)
    device = db.get(Device, device_id)
    if device is None or device.farm_id != farm_id:
        raise NotFound("Device not found")
    rows = list(
        db.scalars(
            select(DeviceCommunication)
            .where(DeviceCommunication.device_id == device_id)
            .order_by(DeviceCommunication.received_at.desc())
            .limit(max(1, min(limit, 500)))
        )
    )
    return [
        {
            "id": str(row.id),
            "protocol": row.protocol,
            "topic": row.topic,
            "event": row.event,
            "status": row.status,
            "payload_sha256": row.payload_sha256,
            "detail": row.detail,
            "received_at": row.received_at.isoformat(),
        }
        for row in rows
    ]


@router.get("/{farm_id}/devices")
def list_devices(
    farm_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[dict]:
    _operator_member(db, farm_id, user)
    devices = list(
        db.scalars(
            select(Device)
            .where(Device.farm_id == farm_id)
            .order_by(Device.name)
        )
    )
    out = []
    for device in devices:
        sensors = list(db.scalars(select(Sensor).where(Sensor.device_id == device.id)))
        out.append(
            {
                "id": str(device.id),
                "external_id": device.external_id,
                "name": device.name,
                "status": device.status.value,
                "firmware_version": device.firmware_version,
                "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None,
                "sensors": [
                    {
                        "id": str(sensor.id),
                        "external_id": sensor.external_id,
                        "kind": sensor.kind.value,
                        "unit": sensor.unit,
                        "calibration_status": sensor.calibration_status,
                        "is_active": sensor.is_active,
                        "zone_id": str(sensor.zone_id) if sensor.zone_id else None,
                    }
                    for sensor in sensors
                ],
            }
        )
    return out


@router.get("/{farm_id}/measurements")
def list_measurements(
    farm_id: UUID,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[dict]:
    _operator_member(db, farm_id, user)
    device_ids = list(
        db.scalars(select(Device.id).where(Device.farm_id == farm_id))
    )
    sensor_ids = list(
        db.scalars(select(Sensor.id).where(Sensor.device_id.in_(device_ids)))
    ) if device_ids else []
    rows = list(
        db.scalars(
            select(SensorMeasurement)
            .where(SensorMeasurement.sensor_id.in_(sensor_ids))
            .order_by(SensorMeasurement.observed_at.desc())
            .limit(max(1, min(limit, 500)))
        )
    ) if sensor_ids else []
    sensors = (
        {
            sensor.id: sensor
            for sensor in db.scalars(
                select(Sensor).where(Sensor.id.in_(sensor_ids))
            )
        }
        if sensor_ids
        else {}
    )
    return [
        {
            "id": str(row.id),
            "sensor_id": str(row.sensor_id),
            "sensor_external_id": sensors[row.sensor_id].external_id,
            "sensor_kind": sensors[row.sensor_id].kind.value,
            "zone_id": str(row.zone_id) if row.zone_id else None,
            "observed_at": row.observed_at.isoformat(),
            "value": float(row.value),
            "unit": row.unit,
            "quality": row.quality.value,
            "quality_note": row.quality_note,
            "data_class": row.data_class.value,
        }
        for row in rows
    ]


@router.post("/{farm_id}/devices", response_model=DeviceResponse, status_code=201)
def register_device(
    farm_id: UUID,
    payload: DeviceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> DeviceResponse:
    if db.get(Farm, farm_id) is None:
        raise NotFound("Farm not found")
    _operator_member(db, farm_id, user)
    if db.scalar(
        select(Device).where(
            Device.farm_id == farm_id,
            Device.external_id == payload.external_id,
        )
    ):
        raise Conflict("Device external_id already exists for this farm")
    api_key = token_urlsafe(32)
    device = Device(
        farm_id=farm_id,
        external_id=payload.external_id,
        name=payload.name,
        status=DeviceStatus.ACTIVE,
        api_key_hash=sha256(api_key.encode()).hexdigest(),
        firmware_version=payload.firmware_version,
    )
    db.add(device)
    db.flush()
    record_audit(
        db,
        action="register",
        entity_type="device",
        entity_id=device.id,
        actor_user_id=user.id,
        farm_id=farm_id,
        after={"external_id": device.external_id, "name": device.name},
    )
    db.commit()
    db.refresh(device)
    return DeviceResponse(
        id=device.id,
        external_id=device.external_id,
        name=device.name,
        status=device.status,
        firmware_version=device.firmware_version,
        last_seen_at=device.last_seen_at,
        api_key=api_key,
    )


@router.post(
    "/{farm_id}/devices/{device_id}/sensors",
    response_model=SensorResponse,
    status_code=201,
)
def register_sensor(
    farm_id: UUID,
    device_id: UUID,
    payload: SensorCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> SensorResponse:
    _operator_member(db, farm_id, user)
    device = db.get(Device, device_id)
    if device is None or device.farm_id != farm_id:
        raise NotFound("Device not found")
    _zone_for_farm(db, farm_id, payload.zone_id)
    if db.scalar(
        select(Sensor).where(
            Sensor.device_id == device_id,
            Sensor.external_id == payload.external_id,
        )
    ):
        raise Conflict("Sensor external_id already exists for this device")
    sensor = Sensor(
        device_id=device_id,
        zone_id=payload.zone_id,
        external_id=payload.external_id,
        kind=payload.kind,
        unit=payload.unit,
        calibration_status=payload.calibration_status,
        calibration_metadata=payload.calibration_metadata,
    )
    db.add(sensor)
    db.flush()
    record_audit(
        db,
        action="register",
        entity_type="sensor",
        entity_id=sensor.id,
        actor_user_id=user.id,
        farm_id=farm_id,
        after={"external_id": sensor.external_id, "kind": sensor.kind.value},
    )
    db.commit()
    db.refresh(sensor)
    return SensorResponse(
        id=sensor.id,
        external_id=sensor.external_id,
        zone_id=sensor.zone_id,
        kind=sensor.kind,
        unit=sensor.unit,
        calibration_status=sensor.calibration_status,
        is_active=sensor.is_active,
    )


@router.post("/{farm_id}/devices/{device_id}/measurements", response_model=MeasurementResponse)
def ingest_measurement(
    farm_id: UUID,
    device_id: UUID,
    payload: MeasurementCreate,
    request: Request,
    x_device_key: str = Header(..., alias="X-Device-Key"),
    db: Session = Depends(get_db),
) -> MeasurementResponse:
    device = db.get(Device, device_id)
    if device is None or device.farm_id != farm_id:
        raise Unauthorized("Unknown device")
    if sha256(x_device_key.encode()).hexdigest() != device.api_key_hash:
        raise Unauthorized("Invalid device key")
    if device.status != DeviceStatus.ACTIVE:
        raise Forbidden("Device is not active")
    sensor = db.scalar(
        select(Sensor).where(
            Sensor.device_id == device_id,
            Sensor.external_id == payload.sensor_external_id,
            Sensor.is_active.is_(True),
        )
    )
    if sensor is None:
        raise NotFound("Sensor not found or inactive")
    if payload.unit.strip() != sensor.unit:
        raise Unprocessable(
            f"Sensor unit mismatch: expected {sensor.unit}, received {payload.unit}"
        )
    if payload.observed_at.tzinfo is None:
        raise Unprocessable("observed_at must include a timezone")
    if payload.observed_at > datetime.now(UTC):
        raise Unprocessable("observed_at cannot be in the future")
    if payload.idempotency_key:
        existing = db.scalar(
            select(SensorMeasurement).where(
                SensorMeasurement.ingestion_idempotency_key
                == payload.idempotency_key
            )
        )
        if existing is not None:
            return MeasurementResponse(
                id=existing.id,
                sensor_id=existing.sensor_id,
                zone_id=existing.zone_id,
                observed_at=existing.observed_at,
                value=existing.value,
                unit=existing.unit,
                quality=existing.quality,
                quality_note=existing.quality_note,
            )
    existing = db.scalar(
        select(SensorMeasurement).where(
            SensorMeasurement.sensor_id == sensor.id,
            SensorMeasurement.observed_at == payload.observed_at,
        )
    )
    if existing is not None:
        return MeasurementResponse(
            id=existing.id,
            sensor_id=existing.sensor_id,
            zone_id=existing.zone_id,
            observed_at=existing.observed_at,
            value=existing.value,
            unit=existing.unit,
            quality=existing.quality,
            quality_note=existing.quality_note,
        )
    measurement = SensorMeasurement(
        sensor_id=sensor.id,
        zone_id=sensor.zone_id,
        observed_at=payload.observed_at,
        value=payload.value,
        unit=payload.unit,
        quality=payload.quality,
        quality_note=payload.quality_note,
        data_class=DataClass.MEASURED,
        ingestion_idempotency_key=payload.idempotency_key,
    )
    device.last_seen_at = datetime.now(UTC)
    db.add(measurement)
    db.flush()
    record_audit(
        db,
        action="ingest",
        entity_type="sensor_measurement",
        entity_id=measurement.id,
        actor_type="device",
        farm_id=farm_id,
        after={"sensor": sensor.external_id, "value": str(measurement.value)},
        ip=_valid_ip(request.client.host if request.client else None),
    )
    db.commit()
    db.refresh(measurement)
    return MeasurementResponse(
        id=measurement.id,
        sensor_id=measurement.sensor_id,
        zone_id=measurement.zone_id,
        observed_at=measurement.observed_at,
        unit=measurement.unit,
        value=measurement.value,
        quality=measurement.quality,
        quality_note=measurement.quality_note,
    )


@router.post(
    "/{farm_id}/irrigation-events",
    response_model=IrrigationEventResponse,
    status_code=201,
)
def create_irrigation_event(
    farm_id: UUID,
    payload: IrrigationEventCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> IrrigationEventResponse:
    _operator_member(db, farm_id, user)
    zone = _zone_for_farm(db, farm_id, payload.zone_id)
    if payload.ended_at <= payload.started_at:
        raise Unprocessable("ended_at must be after started_at")
    if payload.started_at.tzinfo is None or payload.ended_at.tzinfo is None:
        raise Unprocessable("timestamps must include a timezone")
    existing = db.scalar(
        select(IrrigationEvent).where(
            IrrigationEvent.farm_id == farm_id,
            IrrigationEvent.zone_id == zone.id,
            IrrigationEvent.started_at == payload.started_at,
            IrrigationEvent.ended_at == payload.ended_at,
            IrrigationEvent.source == payload.source,
        )
    )
    if existing is not None:
        raise Conflict("Irrigation event already exists")
    event = IrrigationEvent(
        farm_id=farm_id,
        zone_id=zone.id,
        started_at=payload.started_at,
        ended_at=payload.ended_at,
        volume_m3=payload.volume_m3,
        source=payload.source,
        data_class=(
            DataClass.MEASURED
            if payload.source in {"meter", "device"}
            else DataClass.FARMER_REPORTED
        ),
    )
    db.add(event)
    db.flush()
    record_audit(
        db,
        action="create",
        entity_type="irrigation_event",
        entity_id=event.id,
        actor_user_id=user.id,
        farm_id=farm_id,
        after={"zone_id": str(zone.id), "volume_m3": str(event.volume_m3)},
    )
    db.commit()
    db.refresh(event)
    return IrrigationEventResponse(
        id=event.id,
        zone_id=event.zone_id,
        started_at=event.started_at,
        ended_at=event.ended_at,
        volume_m3=event.volume_m3,
        source=event.source,
    )
