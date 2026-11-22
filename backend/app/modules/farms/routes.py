import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.db import get_db
from app.core.enums import FarmRole, RoleName
from app.core.errors import Conflict, Forbidden, NotFound
from app.core.geo import area_ha, to_db, to_geojson
from app.modules.farms.models import Farm, FarmBoundary, FarmMember, IrrigationZone, Parcel
from app.modules.farms.schemas import (
    FarmCreate,
    FarmResponse,
    ParcelCreate,
    ParcelResponse,
    ZoneCreate,
    ZoneResponse,
)
from app.modules.identity.models import User
from app.modules.identity.routes import current_user

router = APIRouter(prefix="/farms", tags=["farms"])


def _member(db: Session, farm_id: uuid.UUID, user: User) -> FarmMember | None:
    if user.has_role(RoleName.ADMIN):
        member = db.get(FarmMember, (farm_id, user.id))
        return member or FarmMember(
            farm_id=farm_id,
            user_id=user.id,
            farm_role=FarmRole.OWNER,
        )
    return db.get(FarmMember, (farm_id, user.id))


@router.post("", response_model=FarmResponse, status_code=201)
def create_farm(
    payload: FarmCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> FarmResponse:
    if db.scalar(select(Farm).where(Farm.code == payload.code)):
        raise Conflict("A farm with this code already exists")
    farm = Farm(
        name=payload.name.strip(),
        code=payload.code,
        country_code=payload.country_code,
        governorate=payload.governorate,
        timezone=payload.timezone,
        created_by=user.id,
        data_class="farmer_reported",
    )
    db.add(farm)
    db.flush()
    db.add(
        FarmMember(
            farm_id=farm.id,
            user_id=user.id,
            farm_role=FarmRole.OWNER,
            granted_by=user.id,
        )
    )
    if payload.boundary:
        geometry = payload.boundary.to_multipolygon()
        db.add(
            FarmBoundary(
                farm_id=farm.id,
                geom=to_db(geometry),
                area_ha=area_ha(db, geometry),
                data_class="farmer_reported",
                created_by=user.id,
            )
        )
    record_audit(
        db,
        action="create",
        entity_type="farm",
        entity_id=farm.id,
        actor_user_id=user.id,
        farm_id=farm.id,
        after={"name": farm.name, "code": farm.code},
    )
    db.commit()
    db.refresh(farm)
    boundary = payload.boundary.model_dump() if payload.boundary else None
    return FarmResponse(
        id=farm.id,
        name=farm.name,
        code=farm.code,
        country_code=farm.country_code,
        governorate=farm.governorate,
        timezone=farm.timezone,
        boundary=boundary,
        data_class=farm.data_class,
    )


@router.get("", response_model=list[FarmResponse])
def list_farms(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[FarmResponse]:
    if user.has_role(RoleName.ADMIN):
        farms = list(db.scalars(select(Farm).order_by(Farm.name)))
    else:
        farms = list(
            db.scalars(
                select(Farm)
                .join(FarmMember, FarmMember.farm_id == Farm.id)
                .where(FarmMember.user_id == user.id)
                .order_by(Farm.name)
            )
        )
    out = []
    for farm in farms:
        current = db.scalar(
            select(FarmBoundary).where(
                FarmBoundary.farm_id == farm.id,
                FarmBoundary.valid_to.is_(None),
            )
        )
        out.append(
            FarmResponse(
                id=farm.id,
                name=farm.name,
                code=farm.code,
                country_code=farm.country_code,
                governorate=farm.governorate,
                timezone=farm.timezone,
                boundary=to_geojson(current.geom) if current else None,
                data_class=farm.data_class,
            )
        )
    return out


@router.get("/{farm_id}", response_model=FarmResponse)
def get_farm(
    farm_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> FarmResponse:
    farm = db.get(Farm, farm_id)
    if farm is None:
        raise NotFound("Farm not found")
    if _member(db, farm_id, user) is None:
        raise Forbidden("You cannot access this farm")
    current = db.scalar(
        select(FarmBoundary).where(FarmBoundary.farm_id == farm_id, FarmBoundary.valid_to.is_(None))
    )
    return FarmResponse(
        id=farm.id,
        name=farm.name,
        code=farm.code,
        country_code=farm.country_code,
        governorate=farm.governorate,
        timezone=farm.timezone,
        boundary=to_geojson(current.geom) if current else None,
        data_class=farm.data_class,
    )


@router.post("/{farm_id}/parcels", response_model=ParcelResponse, status_code=201)
def create_parcel(
    farm_id: uuid.UUID,
    payload: ParcelCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ParcelResponse:
    farm = db.get(Farm, farm_id)
    if farm is None:
        raise NotFound("Farm not found")
    member = _member(db, farm_id, user)
    if member is None or member.farm_role.rank < FarmRole.OPERATOR.rank:
        raise Forbidden("Owner or operator access required")
    geometry = payload.boundary.to_multipolygon()
    parcel = Parcel(
        farm_id=farm_id,
        name=payload.name.strip(),
        geom=to_db(geometry),
        area_ha=area_ha(db, geometry),
        slope_pct=payload.slope_pct,
        data_class="farmer_reported",
    )
    db.add(parcel)
    db.flush()
    record_audit(
        db,
        action="create",
        entity_type="parcel",
        entity_id=parcel.id,
        actor_user_id=user.id,
        farm_id=farm_id,
        after={"name": parcel.name},
    )
    db.commit()
    db.refresh(parcel)
    return ParcelResponse(
        id=parcel.id,
        name=parcel.name,
        area_ha=parcel.area_ha,
        boundary=to_geojson(parcel.geom),
        data_class=parcel.data_class,
    )


@router.post("/{farm_id}/parcels/{parcel_id}/zones", response_model=ZoneResponse, status_code=201)
def create_zone(
    farm_id: uuid.UUID,
    parcel_id: uuid.UUID,
    payload: ZoneCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ZoneResponse:
    member = _member(db, farm_id, user)
    if member is None or member.farm_role.rank < FarmRole.OPERATOR.rank:
        raise Forbidden("Owner or operator access required")
    parcel = db.get(Parcel, parcel_id)
    if parcel is None or parcel.farm_id != farm_id:
        raise NotFound("Parcel not found")
    geometry = payload.boundary.to_multipolygon() if payload.boundary else None
    zone = IrrigationZone(
        parcel_id=parcel_id,
        name=payload.name.strip(),
        geom=to_db(geometry) if geometry else None,
        area_ha=payload.area_ha,
        irrigation_method=payload.irrigation_method,
        emitter_flow_lph=payload.emitter_flow_lph,
        application_efficiency=payload.application_efficiency,
        design_flow_m3h=payload.design_flow_m3h,
        data_class="farmer_reported",
    )
    db.add(zone)
    db.flush()
    record_audit(
        db,
        action="create",
        entity_type="irrigation_zone",
        entity_id=zone.id,
        actor_user_id=user.id,
        farm_id=farm_id,
        after={"name": zone.name},
    )
    db.commit()
    db.refresh(zone)
    return ZoneResponse(
        id=zone.id,
        name=zone.name,
        area_ha=zone.area_ha,
        boundary=to_geojson(zone.geom),
        irrigation_method=zone.irrigation_method,
        data_class=zone.data_class,
    )
