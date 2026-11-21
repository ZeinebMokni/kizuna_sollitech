"""Open-Meteo weather reader (hourly -> daily, FAO-56-ready).

Endpoints:
- forecast:  https://api.open-meteo.com/v1/forecast    (past_days + up to 16 forecast days)
- archive:   https://archive-api.open-meteo.com/v1/archive  (reanalysis, ~5-day latency)

LICENCE: the free API is for NON-COMMERCIAL use only (https://open-meteo.com/en/terms).
Commercial deployments need an API subscription or a self-hosted instance.

Provenance: archive data are model reanalyses (ERA5 family) -> data_class `inferred`;
forecasts -> data_class `projected`. Neither is a local measurement.

Daily aggregation is done in the location's local time zone (timezone=auto).
Accumulated hourly variables (radiation, precipitation, ET0) refer to the *preceding*
hour, so they are shifted back one hour before grouping into calendar days.
Days with fewer than 24 hourly values are dropped and reported.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, Literal

import httpx
import pandas as pd

from qatra_ai.contracts import DataClass

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HOURLY_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "wind_speed_10m",
    "shortwave_radiation",
    "precipitation",
    "et0_fao_evapotranspiration",
]
ACCUMULATED = ["shortwave_radiation", "precipitation", "et0_fao_evapotranspiration"]
USER_AGENT = "qatra-ai/0.1 (agricultural decision support research)"


@dataclass
class WeatherFetchResult:
    daily: pd.DataFrame
    source: str
    data_class: DataClass
    latitude: float
    longitude: float
    elevation_m: float
    timezone: str
    retrieved_at: datetime
    dropped_incomplete_days: list[date] = field(default_factory=list)
    url: str = ""


class OpenMeteoError(RuntimeError):
    pass


def _get_json(client: httpx.Client, url: str, params: dict[str, Any], retries: int = 3) -> dict:
    delay = 1.0
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            resp = client.get(url, params=params, timeout=30.0)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise OpenMeteoError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            if resp.status_code >= 400:  # client errors are not retried
                raise OpenMeteoError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            return resp.json()
        except (httpx.TransportError, OpenMeteoError) as exc:
            last_exc = exc
            if isinstance(exc, OpenMeteoError) and "HTTP 4" in str(exc) and "429" not in str(exc):
                raise
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
    raise OpenMeteoError(f"Open-Meteo request failed after {retries} attempts: {last_exc}")


def parse_hourly(payload: dict) -> pd.DataFrame:
    hourly = payload.get("hourly")
    if not hourly or "time" not in hourly:
        raise OpenMeteoError("response has no hourly data")
    units = payload.get("hourly_units", {})
    if units.get("wind_speed_10m") not in (None, "m/s"):
        raise OpenMeteoError(f"unexpected wind unit {units.get('wind_speed_10m')}; request m/s")
    df = pd.DataFrame(hourly)
    df["time"] = pd.to_datetime(df["time"])
    return df.set_index("time").astype(float)


def hourly_to_daily(hourly: pd.DataFrame) -> tuple[pd.DataFrame, list[date]]:
    """Aggregate to FAO-56 daily inputs. Returns (daily, dropped incomplete days)."""
    inst = hourly.drop(columns=[c for c in ACCUMULATED if c in hourly])
    acc = hourly[[c for c in ACCUMULATED if c in hourly]].copy()
    acc.index = acc.index - pd.Timedelta(hours=1)

    g_inst = inst.groupby(inst.index.normalize())
    g_acc = acc.groupby(acc.index.normalize())
    daily = pd.DataFrame(
        {
            "tmin": g_inst["temperature_2m"].min(),
            "tmax": g_inst["temperature_2m"].max(),
            "tdew": g_inst["dew_point_2m"].mean(),
            "rhmin": g_inst["relative_humidity_2m"].min(),
            "rhmax": g_inst["relative_humidity_2m"].max(),
            "wind": g_inst["wind_speed_10m"].mean(),  # m/s at 10 m
            "n_hours": g_inst["temperature_2m"].count(),
        }
    )
    daily["rs"] = g_acc["shortwave_radiation"].sum(min_count=24) * 3600 / 1e6  # MJ m-2 day-1
    daily["precip"] = g_acc["precipitation"].sum(min_count=24)
    daily["et0_provider"] = g_acc["et0_fao_evapotranspiration"].sum(min_count=24)
    daily["n_hours_acc"] = g_acc["shortwave_radiation"].count()

    complete = (daily["n_hours"] == 24) & (daily["n_hours_acc"] == 24)
    dropped = [d.date() for d in daily.index[~complete]]
    daily = daily[complete].drop(columns=["n_hours", "n_hours_acc"])
    daily.index = pd.DatetimeIndex(daily.index, name="date")
    return daily, dropped


def fetch_daily_weather(
    latitude: float,
    longitude: float,
    *,
    kind: Literal["archive", "forecast"],
    start: date | None = None,
    end: date | None = None,
    past_days: int = 0,
    forecast_days: int = 7,
    client: httpx.Client | None = None,
) -> WeatherFetchResult:
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("invalid coordinates")
    params: dict[str, Any] = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ",".join(HOURLY_VARS),
        "wind_speed_unit": "ms",
        "timezone": "auto",
    }
    if kind == "archive":
        if start is None or end is None or end < start:
            raise ValueError("archive requests need start <= end")
        url = ARCHIVE_URL
        params |= {"start_date": start.isoformat(), "end_date": end.isoformat()}
        data_class = DataClass.INFERRED
    else:
        url = FORECAST_URL
        params |= {"past_days": past_days, "forecast_days": forecast_days}
        data_class = DataClass.PROJECTED

    own_client = client is None
    client = client or httpx.Client(headers={"User-Agent": USER_AGENT})
    try:
        payload = _get_json(client, url, params)
    finally:
        if own_client:
            client.close()

    daily, dropped = hourly_to_daily(parse_hourly(payload))
    return WeatherFetchResult(
        daily=daily,
        source=f"open_meteo:{kind}",
        data_class=data_class,
        latitude=float(payload["latitude"]),
        longitude=float(payload["longitude"]),
        elevation_m=float(payload.get("elevation", 0.0)),
        timezone=str(payload.get("timezone", "GMT")),
        retrieved_at=datetime.now(UTC),
        dropped_incomplete_days=dropped,
        url=url,
    )
