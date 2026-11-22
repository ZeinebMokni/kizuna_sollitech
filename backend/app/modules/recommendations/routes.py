import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.db import get_db
from app.core.enums import FarmRole
from app.core.errors import Conflict, Forbidden, NotFound
from app.modules.devices.models import Sensor, SensorMeasurement
from app.modules.farms.models import Farm, FarmMember, IrrigationZone, Parcel
from app.modules.identity.models import User
from app.modules.identity.routes import current_user
from app.modules.recommendations.models import (
    Recommendation,
    RecommendationApproval,
)
from app.modules.recommendations.schemas import (
    ApprovalRequest,
    ApprovalResponse,
    RecommendationResponse,
    RecommendationRunRequest,
)

router = APIRouter(prefix="/farms", tags=["decision intelligence"])


def _viewer_member(db: Session, farm_id: UUID, user: User) -> FarmMember:
    member = db.get(FarmMember, (farm_id, user.id))
    if member is None:
        raise Forbidden("You cannot access this farm")
    return member


def _operator_member(db: Session, farm_id: UUID, user: User) -> FarmMember:
    member = _viewer_member(db, farm_id, user)
    if member.farm_role.rank < FarmRole.OPERATOR.rank:
        raise Forbidden("Owner or operator access required")
    return member


def _zone(db: Session, farm_id: UUID, zone_id: UUID) -> IrrigationZone:
    zone = db.get(IrrigationZone, zone_id)
    if zone is None:
        raise NotFound("Irrigation zone not found")
    parcel = db.get(Parcel, zone.parcel_id)
    if parcel is None or parcel.farm_id != farm_id:
        raise Forbidden("Zone does not belong to this farm")
    return zone


def _latest_measurements(db: Session, zone_id: UUID) -> list[dict]:
    sensors = list(
        db.scalars(
            select(Sensor).where(
                Sensor.zone_id == zone_id,
                Sensor.is_active.is_(True),
            )
        )
    )
    evidence = []
    for sensor in sensors:
        row = db.scalar(
            select(SensorMeasurement)
            .where(
                SensorMeasurement.sensor_id == sensor.id,
                SensorMeasurement.quality != "invalid",
            )
            .order_by(SensorMeasurement.observed_at.desc())
        )
        if row is not None:
            evidence.append(
                {
                    "sensor_external_id": sensor.external_id,
                    "sensor_kind": sensor.kind.value,
                    "value": float(row.value),
                    "unit": row.unit,
                    "observed_at": row.observed_at.isoformat(),
                    "quality": row.quality.value,
                    "quality_note": row.quality_note,
                    "calibration_status": sensor.calibration_status,
                    "data_class": row.data_class.value,
                }
            )
    return evidence


def _hash_payload(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


@router.post(
    "/{farm_id}/recommendations/run",
    response_model=RecommendationResponse,
)
def run_recommendation(
    farm_id: UUID,
    payload: RecommendationRunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> RecommendationResponse:
    if db.get(Farm, farm_id) is None:
        raise NotFound("Farm not found")
    _operator_member(db, farm_id, user)

    if payload.zone_id is not None:
        zones = [_zone(db, farm_id, payload.zone_id)]
    else:
        zones = list(
            db.scalars(
                select(IrrigationZone)
                .join(Parcel, Parcel.id == IrrigationZone.parcel_id)
                .where(Parcel.farm_id == farm_id)
            )
        )
    if not zones:
        raise NotFound("No irrigation zones exist for this farm")

    as_of = payload.as_of or datetime.now(UTC)
    if as_of.tzinfo is None:
        raise ValueError("as_of must include a timezone")

    zone = zones[0]
    evidence = _latest_measurements(db, zone.id)
    has_usable_soil_moisture = any(
        item["sensor_kind"] == "soil_moisture"
        and item["quality"] in {"valid", "suspect"}
        and item["calibration_status"] == "calibrated"
        for item in evidence
    )

    if has_usable_soil_moisture:
        action = "insufficient_evidence"
        confidence = "insufficient_evidence"
        reasons = [
            "A calibrated soil-moisture reading exists, but FAO-56 root-zone state "
            "and a measured irrigation target are not available"
        ]
        limitations = [
            "No irrigation volume or schedule is proposed",
            "Soil-moisture calibration does not validate crop water demand",
        ]
    else:
        action = "insufficient_evidence"
        confidence = "insufficient_evidence"
        reasons = ["Current usable root-zone water state is unavailable"]
        limitations = [
            "No calibrated, fresh soil-moisture measurement is available",
            "No irrigation volume or schedule is proposed",
        ]

    envelope_payload = {
        "action": action,
        "target": str(zone.id),
        "as_of": as_of.isoformat(),
        "requires_human_approval": action != "insufficient_evidence",
        "reasons": reasons,
        "supporting_measurements": evidence,
        "alternatives": [
            {"action": "inspect", "note": "check soil moisture and irrigation history"}
        ],
        "model_fallback_requested": payload.include_model_fallback,
    }
    inputs_hash = _hash_payload(envelope_payload)
    recommendation = Recommendation(
        farm_id=farm_id,
        zone_id=zone.id,
        model_id="qatra.explainable_irrigation_guard",
        model_version="0.1.0",
        validation_status="literature_parameterised",
        status="pending",
        confidence=confidence,
        inputs_hash=inputs_hash,
        payload=envelope_payload,
        limitations=limitations,
        generated_at=as_of,
    )
    db.add(recommendation)
    db.flush()
    record_audit(
        db,
        action="generate",
        entity_type="ai_recommendation",
        entity_id=recommendation.id,
        actor_user_id=user.id,
        farm_id=farm_id,
        after={"zone_id": str(zone.id), "confidence": confidence, "action": action},
    )
    db.commit()
    db.refresh(recommendation)
    return _recommendation_response(recommendation)


def _recommendation_response(row: Recommendation) -> RecommendationResponse:
    limitations = row.limitations if isinstance(row.limitations, list) else []
    return RecommendationResponse(
        id=row.id,
        farm_id=row.farm_id,
        zone_id=row.zone_id,
        model_id=row.model_id,
        model_version=row.model_version,
        validation_status=row.validation_status,
        status=row.status,
        confidence=row.confidence,
        inputs_hash=row.inputs_hash,
        payload=row.payload,
        limitations=limitations,
        generated_at=row.generated_at,
    )


@router.get(
    "/{farm_id}/recommendations",
    response_model=list[RecommendationResponse],
)
def list_recommendations(
    farm_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[RecommendationResponse]:
    _viewer_member(db, farm_id, user)
    rows = list(
        db.scalars(
            select(Recommendation)
            .where(Recommendation.farm_id == farm_id)
            .order_by(Recommendation.generated_at.desc())
        )
    )
    return [_recommendation_response(row) for row in rows]


@router.post(
    "/{farm_id}/recommendations/{recommendation_id}/approval",
    response_model=ApprovalResponse,
)
def approve_recommendation(
    farm_id: UUID,
    recommendation_id: UUID,
    payload: ApprovalRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ApprovalResponse:
    _operator_member(db, farm_id, user)
    recommendation = db.get(Recommendation, recommendation_id)
    if recommendation is None or recommendation.farm_id != farm_id:
        raise NotFound("Recommendation not found")
    if recommendation.status != "pending":
        raise Conflict("Recommendation has already been resolved")
    approval = RecommendationApproval(
        recommendation_id=recommendation.id,
        actor_user_id=user.id,
        decision=payload.decision,
        note=payload.note,
    )
    recommendation.status = payload.decision
    db.add(approval)
    db.flush()
    record_audit(
        db,
        action="approve" if payload.decision == "approved" else "reject",
        entity_type="recommendation",
        entity_id=recommendation.id,
        actor_user_id=user.id,
        farm_id=farm_id,
        after={"decision": payload.decision, "note": payload.note},
    )
    db.commit()
    db.refresh(approval)
    return ApprovalResponse(
        id=approval.id,
        recommendation_id=approval.recommendation_id,
        decision=approval.decision,
        note=approval.note,
        created_at=approval.created_at,
    )
