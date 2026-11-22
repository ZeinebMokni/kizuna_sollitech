"""PVGIS hourly photovoltaic power estimate reader."""

from __future__ import annotations

import httpx
import pandas as pd


class PvgisError(RuntimeError):
    pass


def fetch_hourly_solar(
    lat: float,
    lon: float,
    *,
    peak_power_kw: float,
    start_year: int,
    end_year: int,
    client: httpx.Client | None = None,
) -> pd.DataFrame:
    params = {
        "lat": lat,
        "lon": lon,
        "startyear": start_year,
        "endyear": end_year,
        "pvcalculation": 1,
        "peakpower": peak_power_kw,
        "loss": 14,
        "outputformat": "json",
    }
    own = client is None
    client = client or httpx.Client(timeout=120, follow_redirects=True)
    try:
        r = client.get("https://re.jrc.ec.europa.eu/api/v5_2/seriescalc", params=params)
        r.raise_for_status()
        payload = r.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise PvgisError(str(exc)) from exc
    finally:
        if own:
            client.close()

    outputs = payload.get("outputs", {}).get("hourly", [])
    if not outputs:
        raise PvgisError("PVGIS returned no hourly output")
    df = pd.DataFrame(outputs)
    time_col = "time" if "time" in df else "t"
    df["timestamp_utc"] = pd.to_datetime(df[time_col], utc=True, format="%Y%m%d:%H%M")
    power_col = "P" if "P" in df else next((c for c in df if c.lower() in ("power", "pv")), None)
    if power_col is None:
        raise PvgisError("PVGIS response has no power column")
    df["pv_kw"] = pd.to_numeric(df[power_col], errors="coerce") / 1000.0
    return df[["timestamp_utc", "pv_kw"]].dropna()
