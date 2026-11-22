"""Geographic nearest-station selection with per-variable quality and freshness checks."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pandas as pd

from qatra_ai.data.qc import INVALID, MISSING, SUSPECT


@dataclass(frozen=True)
class Station:
    station_id: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class VariableSelection:
    variable: str
    source: str | None
    station_id: str | None
    value: float | None
    unit: str | None
    observed_at: datetime | None
    qc_flag: str | None
    distance_km: float | None
    reason: str


STATIONS = (
    Station("sb_crra", 35.684, 9.479),
    Station("sb_el_ayoun", 35.552, 9.664),
    Station("sb_rayhana", 35.695, 9.283),
)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def select_variable(
    observations: pd.DataFrame,
    variable: str,
    farm_lat: float,
    farm_lon: float,
    at: datetime,
    *,
    max_age: timedelta = timedelta(days=30),
) -> VariableSelection:
    """Choose by quality/freshness first, then distance for the newest acceptable reading."""
    candidates = observations[
        (observations["variable"] == variable) & observations["value"].notna()
    ].copy()
    candidates["timestamp_utc"] = pd.to_datetime(candidates["timestamp_utc"], utc=True)
    cutoff = pd.Timestamp(at.astimezone(UTC) - max_age)
    end = pd.Timestamp(at.astimezone(UTC))
    candidates = candidates[
        candidates["timestamp_utc"].between(cutoff, end)
        & ~candidates["qc_flag"].isin([INVALID, MISSING, SUSPECT])
    ]
    if candidates.empty:
        return VariableSelection(
            variable, None, None, None, None, None, None, None,
            "no fresh, valid observation",
        )

    station_by_id = {s.station_id: s for s in STATIONS}
    candidates = candidates.assign(
        distance_km=[
            haversine_km(
                farm_lat,
                farm_lon,
                station_by_id[str(site)].latitude,
                station_by_id[str(site)].longitude,
            )
            if str(site) in station_by_id
            else float("inf")
            for site in candidates["site_id"]
        ]
    )
    candidates = candidates.sort_values(["distance_km", "timestamp_utc"], ascending=[True, False])
    row = candidates.iloc[0]
    return VariableSelection(
        variable=variable,
        source=str(row["source"]),
        station_id=str(row["site_id"]),
        value=float(row["value"]),
        unit=str(row["unit"]),
        observed_at=row["timestamp_utc"].to_pydatetime(),
        qc_flag=str(row["qc_flag"]),
        distance_km=float(row["distance_km"]),
        reason="fresh valid reading; nearest acceptable station",
    )
