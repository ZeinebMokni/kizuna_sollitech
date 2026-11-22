from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import DataClass, IrrigationMethod
from app.core.geo import GeoJSONPolygonal


class FarmCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    code: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    country_code: str = Field(default="TN", pattern=r"^[A-Z]{2}$")
    governorate: str | None = Field(default=None, max_length=64)
    timezone: str = "Africa/Tunis"
    boundary: GeoJSONPolygonal | None = None


class FarmResponse(BaseModel):
    id: UUID
    name: str
    code: str
    country_code: str
    governorate: str | None
    timezone: str
    boundary: dict | None = None
    data_class: DataClass


class ParcelCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    boundary: GeoJSONPolygonal
    slope_pct: Decimal | None = Field(default=None, ge=-100, le=100)


class ParcelResponse(BaseModel):
    id: UUID
    name: str
    area_ha: Decimal
    boundary: dict
    data_class: DataClass


class ZoneCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    boundary: GeoJSONPolygonal | None = None
    irrigation_method: IrrigationMethod
    area_ha: Decimal = Field(gt=0)
    emitter_flow_lph: Decimal | None = Field(default=None, gt=0)
    application_efficiency: Decimal | None = Field(default=None, gt=0, le=1)
    design_flow_m3h: Decimal | None = Field(default=None, gt=0)


class ZoneResponse(BaseModel):
    id: UUID
    name: str
    area_ha: Decimal
    boundary: dict | None
    irrigation_method: IrrigationMethod
    data_class: DataClass
