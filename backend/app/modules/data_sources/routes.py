from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from shapely.geometry import Point
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import Conflict, NotFound, Unprocessable
from app.core.geo import to_db
from app.modules.data_sources.models import DataSource
from app.modules.data_sources.models_observations import WeatherObservation
from app.modules.data_sources.schemas import (
    DataSourceResponse,
    WeatherObservationCreate,
    WeatherObservationResponse,
)
from app.modules.identity.models import User
from app.modules.identity.routes import current_user

router = APIRouter(prefix="/data", tags=["data integration"])


@router.get("/sources", response_model=list[DataSourceResponse])
def list_sources(
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
) -> list[DataSourceResponse]:
    sources = list(db.scalars(select(DataSource).order_by(DataSource.code)))
    return [DataSourceResponse.model_validate(source, from_attributes=True) for source in sources]


@router.post("/weather", response_model=WeatherObservationResponse, status_code=201)
def ingest_weather(
    payload: WeatherObservationCreate,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
) -> WeatherObservationResponse:
    source = db.scalar(select(DataSource).where(DataSource.code == payload.source_code))
    if source is None:
        raise NotFound(f"Unknown data source: {payload.source_code}")

    try:
        observation_date = date.fromisoformat(payload.observation_date)
        retrieved_at = datetime.fromisoformat(payload.retrieved_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Unprocessable(str(exc)) from exc
    if retrieved_at.tzinfo is None:
        raise Unprocessable("retrieved_at must include a timezone")
    if (
        payload.tmin_c is not None
        and payload.tmax_c is not None
        and payload.tmin_c > payload.tmax_c
    ):
        raise Unprocessable("tmin_c cannot exceed tmax_c")

    existing = db.scalar(
        select(WeatherObservation).where(
            WeatherObservation.observation_date == observation_date,
            WeatherObservation.latitude == payload.latitude,
            WeatherObservation.longitude == payload.longitude,
            WeatherObservation.source_id == source.id,
        )
    )
    if existing is not None:
        raise Conflict("This observation already exists for the source, point and date")

    point = Point(float(payload.longitude), float(payload.latitude))
    row = WeatherObservation(
        observation_date=observation_date,
        location=to_db(point),
        latitude=payload.latitude,
        longitude=payload.longitude,
        tmin_c=payload.tmin_c,
        tmax_c=payload.tmax_c,
        precipitation_mm=payload.precipitation_mm,
        solar_radiation_mj_m2_day=payload.solar_radiation_mj_m2_day,
        wind_m_s=payload.wind_m_s,
        et0_mm=payload.et0_mm,
        source_id=source.id,
        data_class=payload.data_class,
        retrieved_at=retrieved_at,
        method=payload.method,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _weather_response(row, payload.source_code)


def _weather_response(
    row: WeatherObservation,
    source_code: str,
) -> WeatherObservationResponse:
    return WeatherObservationResponse(
        id=row.id,
        observation_date=row.observation_date.isoformat(),
        latitude=row.latitude,
        longitude=row.longitude,
        tmin_c=row.tmin_c,
        tmax_c=row.tmax_c,
        precipitation_mm=row.precipitation_mm,
        solar_radiation_mj_m2_day=row.solar_radiation_mj_m2_day,
        wind_m_s=row.wind_m_s,
        et0_mm=row.et0_mm,
        source_code=source_code,
        data_class=row.data_class,
        retrieved_at=row.retrieved_at.isoformat(),
        method=row.method,
    )


@router.get("/weather", response_model=list[WeatherObservationResponse])
def list_weather(
    start: date = Query(...),
    end: date = Query(...),
    latitude: Decimal | None = Query(default=None, ge=-90, le=90),
    longitude: Decimal | None = Query(default=None, ge=-180, le=180),
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
) -> list[WeatherObservationResponse]:
    if end < start:
        raise Unprocessable("end must be on or after start")
    statement = select(WeatherObservation).where(
        WeatherObservation.observation_date >= start,
        WeatherObservation.observation_date <= end,
    )
    if latitude is not None:
        statement = statement.where(WeatherObservation.latitude == latitude)
    if longitude is not None:
        statement = statement.where(WeatherObservation.longitude == longitude)
    rows = list(db.scalars(statement.order_by(WeatherObservation.observation_date)))
    out = []
    for row in rows:
        source = db.get(DataSource, row.source_id)
        response = _weather_response(row, source.code if source else "unknown")
        out.append(response)
    return out
