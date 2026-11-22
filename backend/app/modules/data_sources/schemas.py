from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import DataClass, DataSourceKind


class DataSourceResponse(BaseModel):
    id: UUID
    code: str
    name: str
    provider: str | None
    kind: DataSourceKind
    license: str | None
    terms_url: str | None
    spatial_resolution: str | None
    temporal_resolution: str | None
    methodology_url: str | None
    description: str | None


class WeatherObservationCreate(BaseModel):
    observation_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    latitude: Decimal = Field(ge=-90, le=90)
    longitude: Decimal = Field(ge=-180, le=180)
    tmin_c: Decimal | None = Field(default=None, ge=-100, le=100)
    tmax_c: Decimal | None = Field(default=None, ge=-100, le=100)
    precipitation_mm: Decimal | None = Field(default=None, ge=0)
    solar_radiation_mj_m2_day: Decimal | None = Field(default=None, ge=0)
    wind_m_s: Decimal | None = Field(default=None, ge=0)
    et0_mm: Decimal | None = Field(default=None, ge=0)
    source_code: str = Field(min_length=2, max_length=64)
    data_class: DataClass
    retrieved_at: str
    method: str | None = None


class WeatherObservationResponse(BaseModel):
    id: UUID
    observation_date: str
    latitude: Decimal
    longitude: Decimal
    tmin_c: Decimal | None
    tmax_c: Decimal | None
    precipitation_mm: Decimal | None
    solar_radiation_mj_m2_day: Decimal | None
    wind_m_s: Decimal | None
    et0_mm: Decimal | None
    source_code: str
    data_class: DataClass
    retrieved_at: str
    method: str | None
