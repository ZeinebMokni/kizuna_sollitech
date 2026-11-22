import hashlib
import json
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.config import get_settings
from app.core.db import get_db
from app.core.enums import FarmRole
from app.core.errors import Forbidden, NotFound, Unprocessable
from app.modules.advanced.models import (
    ClimateScenario,
    EvidenceRecord,
    Incident,
    OptimizationRun,
    SatelliteObservation,
)
from app.modules.advanced.schemas import (
    ClimateScenarioCreate,
    EvidenceCreate,
    IncidentCreate,
    OptimizationRunCreate,
    SatelliteObservationCreate,
)
from app.modules.farms.models import Farm, FarmMember, Parcel
from app.modules.identity.models import User
from app.modules.identity.routes import current_user

router = APIRouter(tags=["advanced"])


def _member(db: Session, farm_id: UUID, user: User) -> FarmMember:
    member = db.get(FarmMember, (farm_id, user.id))
    if member is None:
        raise Forbidden("You cannot access this farm")
    return member


def _require_farm(db: Session, farm_id: UUID) -> Farm:
    farm = db.get(Farm, farm_id)
    if farm is None:
        raise NotFound("Farm not found")
    return farm


@router.post("/farms/{farm_id}/satellite-observations")
def add_satellite_observation(
    farm_id: UUID,
    payload: SatelliteObservationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    _require_farm(db, farm_id)
    member = _member(db, farm_id, user)
    if member.farm_role.rank < FarmRole.OPERATOR.rank:
        raise Forbidden("Owner or operator access required")
    if payload.observed_at.tzinfo is None:
        raise Unprocessable("observed_at must include a timezone")
    if payload.parcel_id is not None:
        parcel = db.get(Parcel, payload.parcel_id)
        if parcel is None or parcel.farm_id != farm_id:
            raise Forbidden("Parcel does not belong to this farm")
    row = SatelliteObservation(
        farm_id=farm_id,
        parcel_id=payload.parcel_id,
        observed_at=payload.observed_at,
        acquisition_date=payload.acquisition_date,
        provider=payload.provider,
        product=payload.product,
        ndvi=payload.ndvi,
        cloud_pct=payload.cloud_pct,
        resolution_m=payload.resolution_m,
        scene_id=payload.scene_id,
        provenance={
            "data_class": "remote_sensed",
            "source": f"{payload.provider}:{payload.product}",
            "quality": "provisional" if payload.cloud_pct is None else "scene_metadata",
        },
    )
    db.add(row)
    db.flush()
    record_audit(
        db,
        action="ingest",
        entity_type="satellite_observation",
        entity_id=row.id,
        actor_user_id=user.id,
        farm_id=farm_id,
        after={"provider": row.provider, "acquisition_date": str(row.acquisition_date)},
    )
    db.commit()
    db.refresh(row)
    return {
        "id": str(row.id),
        "data_class": "remote_sensed",
        "provider": row.provider,
        "product": row.product,
        "acquisition_date": row.acquisition_date.isoformat(),
        "ndvi": float(row.ndvi) if row.ndvi is not None else None,
        "cloud_pct": float(row.cloud_pct) if row.cloud_pct is not None else None,
    }


@router.post("/farms/{farm_id}/optimization-runs")
def create_optimization_run(
    farm_id: UUID,
    payload: OptimizationRunCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    _require_farm(db, farm_id)
    member = _member(db, farm_id, user)
    if member.farm_role.rank < FarmRole.OPERATOR.rank:
        raise Forbidden("Owner or operator access required")

    canonical = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    inputs_hash = hashlib.sha256(canonical.encode()).hexdigest()
    request_payload = payload.model_dump(mode="json")
    engine_url = getattr(get_settings(), "engine_url", "http://127.0.0.1:8100")
    try:
        response = httpx.post(
            f"{engine_url.rstrip('/')}/api/allocation",
            json=request_payload,
            timeout=120,
        )
        response.raise_for_status()
        engine_result = response.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise Unprocessable(f"Allocation engine unavailable: {exc}") from exc

    row = OptimizationRun(
        farm_id=farm_id,
        period_label=payload.period_label,
        model_id=engine_result.get("model", {}).get("model_id", "lp_aquifer_allocation"),
        model_version=engine_result.get("model", {}).get("version", "0.1.0"),
        status="computed",
        inputs_hash=inputs_hash,
        request=request_payload,
        result=engine_result,
        disclaimer=(
            "Decision support only: results are not an allocation order and do not "
            "establish fairness, legality or water rights."
        ),
    )
    db.add(row)
    db.flush()
    record_audit(
        db,
        action="compute",
        entity_type="optimization_run",
        entity_id=row.id,
        actor_user_id=user.id,
        farm_id=farm_id,
        after={"period_label": row.period_label, "inputs_hash": row.inputs_hash},
    )
    db.commit()
    db.refresh(row)
    return {
        "id": str(row.id),
        "period_label": row.period_label,
        "inputs_hash": row.inputs_hash,
        "disclaimer": row.disclaimer,
        "engine": engine_result,
    }


@router.post("/farms/{farm_id}/climate-scenarios")
def create_climate_scenario(
    farm_id: UUID,
    payload: ClimateScenarioCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    _require_farm(db, farm_id)
    member = _member(db, farm_id, user)
    if member.farm_role.rank < FarmRole.OPERATOR.rank:
        raise Forbidden("Owner or operator access required")
    if (
        payload.kind == "hypothetical"
        and payload.temperature_delta_c == 0
        and payload.precipitation_pct == 0
    ):
        raise Unprocessable("A hypothetical scenario must change at least one assumption")
    assumptions = {
        "temperature_delta_c": payload.temperature_delta_c,
        "precipitation_pct": payload.precipitation_pct,
        "radiation_pct": payload.radiation_pct,
    }
    limitations = [
        "Scenario, not a scientific forecast",
        "Delta-change method does not represent new variability or extreme-event statistics",
        "Crop calendars and CO2 effects are not adapted",
    ]
    row = ClimateScenario(
        farm_id=farm_id,
        name=payload.name,
        kind=payload.kind,
        assumptions=assumptions,
        baseline_period=payload.baseline_period,
        future_window=payload.future_window,
        model_name=payload.model_name,
        limitations=limitations,
    )
    db.add(row)
    db.flush()
    record_audit(
        db,
        action="create",
        entity_type="climate_scenario",
        entity_id=row.id,
        actor_user_id=user.id,
        farm_id=farm_id,
        after={"name": row.name, "kind": row.kind},
    )
    db.commit()
    db.refresh(row)
    return {
        "id": str(row.id),
        "name": row.name,
        "kind": row.kind,
        "assumptions": row.assumptions,
        "limitations": row.limitations,
    }


@router.post("/farms/{farm_id}/incidents")
def create_incident(
    farm_id: UUID,
    payload: IncidentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    _require_farm(db, farm_id)
    _member(db, farm_id, user)
    if payload.occurred_at.tzinfo is None:
        raise Unprocessable("occurred_at must include a timezone")
    row = Incident(
        farm_id=farm_id,
        reported_by=user.id,
        incident_type=payload.incident_type,
        occurred_at=payload.occurred_at,
        description=payload.description,
    )
    db.add(row)
    db.flush()
    record_audit(
        db,
        action="report",
        entity_type="incident",
        entity_id=row.id,
        actor_user_id=user.id,
        farm_id=farm_id,
        after={"incident_type": row.incident_type, "status": row.status},
    )
    db.commit()
    db.refresh(row)
    return {"id": str(row.id), "status": row.status, "verification_status": row.verification_status}


@router.post("/farms/{farm_id}/incidents/{incident_id}/evidence")
def add_evidence(
    farm_id: UUID,
    incident_id: UUID,
    payload: EvidenceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    _member(db, farm_id, user)
    incident = db.get(Incident, incident_id)
    if incident is None or incident.farm_id != farm_id:
        raise NotFound("Incident not found")
    if payload.observed_at is not None and payload.observed_at.tzinfo is None:
        raise Unprocessable("observed_at must include a timezone")
    row = EvidenceRecord(
        incident_id=incident.id,
        evidence_type=payload.evidence_type,
        description=payload.description,
        file_hash=payload.file_hash,
        source=payload.source,
        observed_at=payload.observed_at,
        provenance={
            "submitted_by": str(user.id),
            "evidence_type": payload.evidence_type,
            "verification": "unverified",
        },
    )
    db.add(row)
    db.flush()
    record_audit(
        db,
        action="attach",
        entity_type="evidence_record",
        entity_id=row.id,
        actor_user_id=user.id,
        farm_id=farm_id,
        after={"incident_id": str(incident.id), "evidence_type": row.evidence_type},
    )
    db.commit()
    db.refresh(row)
    return {"id": str(row.id), "verification": "unverified"}
