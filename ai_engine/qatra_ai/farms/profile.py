"""Farm profile: everything QATRA needs to know about one farm, in one validated document.

The engine's algorithms are location-independent; a profile supplies the farm-specific inputs
(location, zones and crops, pump, energy, water limits, sensors). Profiles are YAML files:
  - shipped demo:   qatra_ai/reference_data/farms/*.yaml   (kind: demo, hypothetical)
  - your farms:     <data root>/farms/*.yaml                (git-ignored: locations are private)

Validation rejects incomplete or impossible profiles instead of guessing defaults for things
that matter (location, crop, area, pump). Optional parts that are unknown stay None, and the
engine then treats the matching constraint as "not known", never as "unlimited by fact".
"""

from __future__ import annotations

import math
import re
from datetime import date
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from qatra_ai.agronomy.crops import load_crop_profiles
from qatra_ai.optimization.schedule_models import BatterySpec, PumpSystem

PROFILE_SCHEMA_VERSION = "1.0"
MAX_ZONE_DISTANCE_KM = 10.0  # a zone polygon farther than this from the farm point is a typo

_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")


def _check_id(value: str, what: str) -> str:
    if not _ID.match(value):
        raise ValueError(f"{what} {value!r}: use 2-63 lower-case letters, digits or '-'")
    return value


def _known_crop(v: str) -> str:
    known = load_crop_profiles()
    if v not in known:
        raise ValueError(
            f"QATRA has no parameters for crop {v!r} (known: {', '.join(sorted(known))}). "
            "Add a reviewed crop file instead of reusing another crop's values."
        )
    return v


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Location(_Strict):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone: str = Field(description="IANA name, e.g. Africa/Tunis")
    elevation_m: float | None = Field(default=None, ge=-450, le=6000)
    region: str | None = None  # free text, e.g. governorate

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown time zone {v!r}") from exc
        return v


class ZoneProfile(_Strict):
    zone_id: str
    name: str = Field(min_length=1)
    crop: str = Field(description="crop code from qatra_ai/reference_data/crops")
    season_start: date = Field(description="planting date, or start of season for perennials")
    area_ha: float = Field(gt=0, le=10_000)
    design_flow_m3h: float = Field(gt=0, description="flow when this zone's valve is open")
    application_efficiency: float = Field(default=0.9, gt=0, le=1)
    polygon: list[tuple[float, float]] | None = Field(
        default=None, description="[latitude, longitude] corners, for the map"
    )

    @field_validator("zone_id")
    @classmethod
    def _zid(cls, v: str) -> str:
        return _check_id(v, "zone_id")

    @field_validator("crop")
    @classmethod
    def _crop(cls, v: str) -> str:
        return _known_crop(v)

    @field_validator("polygon")
    @classmethod
    def _poly(cls, v: list[tuple[float, float]] | None) -> list[tuple[float, float]] | None:
        if v is None:
            return v
        if len(v) < 3:
            raise ValueError("a polygon needs at least 3 corners")
        for lat, lon in v:
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError(f"polygon corner ({lat}, {lon}) is not a valid coordinate")
        return v


class SoilInput(_Strict):
    """Farm soil data, used instead of the SoilGrids map. Give EITHER a lab texture analysis
    (converted with Saxton & Rawls 2006) OR measured field capacity and wilting point."""

    sand_pct: float | None = Field(default=None, ge=0, le=100)
    clay_pct: float | None = Field(default=None, ge=0, le=100)
    organic_matter_pct: float | None = Field(default=None, ge=0, le=8)
    theta_fc: float | None = Field(default=None, gt=0, lt=0.7, description="m3/m3")
    theta_wp: float | None = Field(default=None, ge=0, lt=0.6, description="m3/m3")
    source: str = Field(min_length=1, description="who measured it, e.g. 'CRDA lab, 2025'")

    @model_validator(mode="after")
    def _one_form(self) -> SoilInput:
        texture = (self.sand_pct, self.clay_pct, self.organic_matter_pct)
        water = (self.theta_fc, self.theta_wp)
        has_t, has_w = any(v is not None for v in texture), any(v is not None for v in water)
        if has_t == has_w:
            raise ValueError(
                "give either sand_pct, clay_pct and organic_matter_pct, or theta_fc and theta_wp"
            )
        if has_t:
            if any(v is None for v in texture):
                raise ValueError("texture needs sand_pct, clay_pct and organic_matter_pct")
            if self.sand_pct + self.clay_pct > 100:  # type: ignore[operator]
                raise ValueError("sand_pct + clay_pct exceeds 100")
        else:
            if any(v is None for v in water):
                raise ValueError("give both theta_fc and theta_wp")
            if self.theta_fc <= self.theta_wp:  # type: ignore[operator]
                raise ValueError("theta_fc must be greater than theta_wp")
        return self


class WaterLimits(_Strict):
    max_volume_per_day_m3: float | None = Field(default=None, gt=0, description="well/permit cap")
    seasonal_m3_per_ha: float | None = Field(default=None, gt=0, description="seasonal budget")
    irrigation_ec_ds_m: float | None = Field(default=None, ge=0, le=30, description="salinity")


class EnergySystem(_Strict):
    pv_rated_kw: float = Field(default=0.0, ge=0)
    battery: BatterySpec | None = None
    grid_hours: list[int] | None = Field(default=None, description="hours (0-23) grid is usable")
    grid_max_kw: float | None = Field(default=None, gt=0)
    seasonal_kwh_per_ha: float | None = Field(default=None, gt=0)

    @field_validator("grid_hours")
    @classmethod
    def _hours(cls, v: list[int] | None) -> list[int] | None:
        if v is not None and (any(not 0 <= h <= 23 for h in v) or len(set(v)) != len(v)):
            raise ValueError("grid_hours must be distinct hours between 0 and 23")
        return v

    @model_validator(mode="after")
    def _some_power(self) -> EnergySystem:
        if self.pv_rated_kw == 0 and not self.grid_hours:
            raise ValueError("the pump needs power: give pv_rated_kw and/or grid_hours")
        if self.grid_hours and self.grid_max_kw is None:
            raise ValueError("grid_hours given without grid_max_kw")
        return self


SensorKind = Literal[
    "soil_moisture", "flow_meter", "pump_status", "pressure", "rain_gauge", "weather_station"
]


class SensorDecl(_Strict):
    sensor_id: str
    kind: SensorKind
    zone_id: str | None = None
    depth_cm: float | None = Field(default=None, gt=0, le=300)

    @field_validator("sensor_id")
    @classmethod
    def _sid(cls, v: str) -> str:
        return _check_id(v, "sensor_id")


class SuitabilityCandidate(_Strict):
    crop: str
    planting_month: int = Field(ge=1, le=12)
    planting_day: int = Field(ge=1, le=31)

    @field_validator("crop")
    @classmethod
    def _crop(cls, v: str) -> str:
        return _known_crop(v)


class ReplayWindow(_Strict):
    """Demo farms replay a past season instead of running on today's date."""

    default_day: date
    weather_start: date
    weather_end: date
    climate_years: tuple[int, int] = (2015, 2024)

    @model_validator(mode="after")
    def _order(self) -> ReplayWindow:
        if not self.weather_start < self.default_day < self.weather_end:
            raise ValueError("need weather_start < default_day < weather_end")
        return self


class AssumedIrrigation(_Strict):
    """Past irrigation ASSUMED when no log exists (labelled as an assumption in outputs)."""

    mm_per_event: float = Field(gt=0, le=200)
    every_days: int = Field(ge=1, le=60)


class FarmProfile(_Strict):
    schema_version: str = PROFILE_SCHEMA_VERSION
    farm_id: str
    name: str = Field(min_length=1)
    kind: Literal["demo", "real"] = Field(
        description="demo = hypothetical farm for demonstration; real = an actual farm"
    )
    location: Location
    soil_depth_m: float | None = Field(default=None, gt=0, le=5)
    soil: SoilInput | None = None  # farm soil data; if absent, the SoilGrids map is used
    zones: list[ZoneProfile] = Field(min_length=1)
    pump: PumpSystem
    water: WaterLimits = Field(default_factory=WaterLimits)
    energy: EnergySystem
    sensors: list[SensorDecl] = Field(default_factory=list)
    suitability_candidates: list[SuitabilityCandidate] = Field(default_factory=list)
    replay: ReplayWindow | None = None
    assumed_past_irrigation: AssumedIrrigation | None = None
    notes: str | None = None

    @field_validator("farm_id")
    @classmethod
    def _fid(cls, v: str) -> str:
        return _check_id(v, "farm_id")

    @model_validator(mode="after")
    def _consistency(self) -> FarmProfile:
        ids = [z.zone_id for z in self.zones]
        dup = {i for i in ids if ids.count(i) > 1}
        if dup:
            raise ValueError(f"duplicate zone_id: {sorted(dup)}")
        sids = [s.sensor_id for s in self.sensors]
        if len(set(sids)) != len(sids):
            raise ValueError("duplicate sensor_id")
        for s in self.sensors:
            if s.zone_id is not None and s.zone_id not in ids:
                raise ValueError(f"sensor {s.sensor_id} refers to unknown zone {s.zone_id!r}")
            if s.kind == "soil_moisture" and (s.zone_id is None or s.depth_cm is None):
                raise ValueError(f"soil_moisture sensor {s.sensor_id} needs zone_id and depth_cm")
        lat, lon = self.location.latitude, self.location.longitude
        for z in self.zones:
            for plat, plon in z.polygon or []:
                if _km(lat, lon, plat, plon) > MAX_ZONE_DISTANCE_KM:
                    raise ValueError(
                        f"zone {z.zone_id} has a corner more than {MAX_ZONE_DISTANCE_KM:g} km "
                        "from the farm location (check latitude/longitude order)"
                    )
        if self.kind == "demo" and self.replay is None:
            raise ValueError("a demo farm needs a replay window")
        return self

    def zone(self, zone_id: str) -> ZoneProfile:
        for z in self.zones:
            if z.zone_id == zone_id:
                return z
        raise KeyError(zone_id)

    @property
    def total_area_ha(self) -> float:
        return sum(z.area_ha for z in self.zones)
