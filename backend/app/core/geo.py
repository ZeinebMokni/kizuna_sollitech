"""GeoJSON <-> PostGIS helpers and geometry validation.

All geometries are stored as MultiPolygon in WGS84 (SRID 4326).
Areas are computed on the spheroid by PostGIS (geography cast), never in degrees.
"""

from typing import Any, Literal

from geoalchemy2.elements import WKBElement, WKTElement
from geoalchemy2.shape import to_shape
from pydantic import BaseModel, field_validator
from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from shapely.validation import explain_validity
from sqlalchemy import text
from sqlalchemy.orm import Session

SRID = 4326
# Tolerance (metres) used for containment checks, to absorb hand-drawing imprecision.
CONTAINMENT_TOLERANCE_M = 5.0
# Share of a new polygon's area that may overlap a sibling before we reject it.
MAX_OVERLAP_RATIO = 0.01


class GeoJSONPolygonal(BaseModel):
    """A GeoJSON Polygon or MultiPolygon in WGS84 longitude/latitude."""

    type: Literal["Polygon", "MultiPolygon"]
    coordinates: list[Any]

    @field_validator("coordinates")
    @classmethod
    def _non_empty(cls, v: list[Any]) -> list[Any]:
        if not v:
            raise ValueError("coordinates must not be empty")
        return v

    def to_multipolygon(self) -> MultiPolygon:
        try:
            geom = shape(self.model_dump())
        except Exception as exc:  # shapely raises various errors for malformed input
            raise ValueError(f"Malformed geometry: {exc}") from exc
        if isinstance(geom, Polygon):
            geom = MultiPolygon([geom])
        if not isinstance(geom, MultiPolygon) or geom.is_empty:
            raise ValueError("Geometry must be a non-empty Polygon or MultiPolygon")
        if not geom.is_valid:
            raise ValueError(f"Invalid geometry: {explain_validity(geom)}")
        minx, miny, maxx, maxy = geom.bounds
        if minx < -180 or maxx > 180 or miny < -90 or maxy > 90:
            raise ValueError("Coordinates must be WGS84 [longitude, latitude]")
        return geom


def to_db(geom: MultiPolygon) -> WKTElement:
    return WKTElement(geom.wkt, srid=SRID)


def to_geojson(value: WKBElement | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return dict(mapping(to_shape(value)))


def area_ha(db: Session, geom: MultiPolygon) -> float:
    return float(
        db.scalar(
            text("SELECT ST_Area(ST_GeomFromText(:wkt, 4326)::geography) / 10000.0"),
            {"wkt": geom.wkt},
        )
    )


def covered_by(db: Session, inner: MultiPolygon, outer_sql: str, params: dict[str, Any]) -> bool:
    """True if `inner` lies within the geometry returned by `outer_sql` (+ tolerance).

    `outer_sql` must be a trusted, constant SQL fragment selecting one geometry column `g`.
    """
    sql = text(
        f"SELECT ST_Covers(ST_Buffer(o.g::geography, :tol)::geometry, "  # noqa: S608
        f"ST_GeomFromText(:wkt, 4326)) FROM ({outer_sql}) AS o"
    )
    result = db.scalar(sql, {**params, "wkt": inner.wkt, "tol": CONTAINMENT_TOLERANCE_M})
    return bool(result)
