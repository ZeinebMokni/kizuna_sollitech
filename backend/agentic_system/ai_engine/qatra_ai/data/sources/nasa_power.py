"""NASA POWER daily point reader (solar radiation and agro-meteorology).

API: https://power.larc.nasa.gov/api/temporal/daily/point  (free, no key; community=AG)
Resolution: ~0.5 x 0.625 degrees (MERRA-2 meteorology, CERES/GEWEX radiation).
Use for: solar/PV estimation and a second, independent weather source.
Do not use for: field-scale microclimate (grid cells are ~50 km wide).

Provenance: model/satellite-derived -> data_class `inferred`.
Missing values are encoded by the API as -999 and converted to NaN here.

Output columns match `agronomy.daily_et0.compute_daily_et0`:
    tmin, tmax, tdew [degC], rhmean [%], wind [m/s at 2 m], rs [MJ m-2 day-1], precip [mm]
NOTE: wind is already at 2 m. Call compute_daily_et0(..., wind_height_m=2.0).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import httpx
import numpy as np
import pandas as pd

from qatra_ai.contracts import DataClass
from qatra_ai.data.sources.open_meteo import USER_AGENT

URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
FILL_VALUE = -999.0
PARAMS = {
    "T2M_MIN": "tmin",
    "T2M_MAX": "tmax",
    "T2MDEW": "tdew",
    "RH2M": "rhmean",
    "WS2M": "wind",
    "ALLSKY_SFC_SW_DWN": "rs",
    "PRECTOTCORR": "precip",
}
EXPECTED_UNITS = {"ALLSKY_SFC_SW_DWN": "MJ/m^2/day", "WS2M": "m/s", "PRECTOTCORR": "mm/day"}


class NasaPowerError(RuntimeError):
    pass


@dataclass
class NasaPowerResult:
    daily: pd.DataFrame
    latitude: float
    longitude: float
    elevation_m: float | None
    source: str = "nasa_power:daily_point"
    data_class: DataClass = DataClass.INFERRED
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    wind_height_m: float = 2.0


def parse_power(payload: dict) -> pd.DataFrame:
    try:
        params = payload["properties"]["parameter"]
    except KeyError as exc:
        raise NasaPowerError(f"unexpected response shape: {list(payload)[:5]}") from exc
    units = payload.get("parameters", {})
    for p, expected in EXPECTED_UNITS.items():
        got = units.get(p, {}).get("units")
        if got is not None and got.replace(" ", "") != expected.replace(" ", ""):
            raise NasaPowerError(f"{p}: expected units {expected}, got {got}")
    frames = {}
    for api_name, col in PARAMS.items():
        if api_name in params:
            s = pd.Series(params[api_name], dtype=float)
            s.index = pd.to_datetime(s.index, format="%Y%m%d")
            frames[col] = s.replace(FILL_VALUE, np.nan)
    if not frames:
        raise NasaPowerError("no requested parameters in response")
    df = pd.DataFrame(frames).sort_index()
    df.index.name = "date"
    return df


def fetch_power_daily(
    latitude: float, longitude: float, start: date, end: date, client: httpx.Client | None = None
) -> NasaPowerResult:
    if end < start:
        raise ValueError("end must be >= start")
    query = {
        "parameters": ",".join(PARAMS),
        "community": "AG",
        "latitude": latitude,
        "longitude": longitude,
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
    }
    own = client is None
    client = client or httpx.Client(headers={"User-Agent": USER_AGENT})
    try:
        resp = client.get(URL, params=query, timeout=60.0)
    finally:
        if own:
            client.close()
    if resp.status_code != 200:
        raise NasaPowerError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    payload = resp.json()
    coords = payload.get("geometry", {}).get("coordinates", [longitude, latitude, None])
    return NasaPowerResult(
        daily=parse_power(payload),
        latitude=float(coords[1]),
        longitude=float(coords[0]),
        elevation_m=float(coords[2]) if len(coords) > 2 and coords[2] is not None else None,
    )
