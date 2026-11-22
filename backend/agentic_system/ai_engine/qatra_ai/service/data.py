"""Weather and soil for any location, cached on disk.

`DataProvider` is the seam used by tests (an offline provider with synthetic data can replace
the network one). Every frame carries its source and data class; nothing is invented when a
download fails: the error is raised and reported to the caller.

Sources:
- past weather: NASA POWER daily (gridded reanalysis/satellite, data class `inferred`)
- recent days and forecast (live farms): Open-Meteo forecast API, past days + 7-day forecast
  (model output: past days `inferred`, future days `projected`). Free tier: non-commercial use.
- soil: SoilGrids 250 m (`inferred`)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Protocol

import pandas as pd

from qatra_ai.agronomy.daily_et0 import compute_daily_et0
from qatra_ai.agronomy.soil import SoilWaterProperties
from qatra_ai.contracts import DataClass

CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "service"
POWER_LATENCY_DAYS = 7  # NASA POWER daily values are complete about a week after the fact
LIVE_FORECAST_DAYS = 7


class DataUnavailableError(RuntimeError):
    """External data could not be obtained; the caller must not substitute invented values."""


class WeatherUnavailableError(DataUnavailableError):
    pass


class SoilUnavailableError(DataUnavailableError):
    def __init__(self, message: str, no_data_here: bool = False):
        super().__init__(message)
        self.no_data_here = no_data_here  # the map has no value at this point (not an outage)


@dataclass(frozen=True)
class WeatherData:
    daily: pd.DataFrame  # et0, precip, rs, tmax, tmin, ... (DatetimeIndex, local dates)
    source: str
    data_class: DataClass
    elevation_m: float
    # Live weather only: first date that is a forecast rather than a past estimate.
    forecast_from: date | None = None


class DataProvider(Protocol):
    def weather(self, lat: float, lon: float, start: date, end: date) -> WeatherData: ...
    def live_weather(self, lat: float, lon: float, start: date, today: date) -> WeatherData: ...
    def soil(self, lat: float, lon: float) -> SoilWaterProperties: ...


def _frame_to_json(df: pd.DataFrame) -> str:
    return df.reset_index().to_json(orient="records", date_format="iso")


def _frame_from_json(text: str) -> pd.DataFrame:
    df = pd.DataFrame(json.loads(text))
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    return df.set_index("date")


def _loc(lat: float, lon: float) -> str:
    return f"{lat:.4f}_{lon:.4f}"


class PublicDataProvider:
    """NASA POWER, Open-Meteo and SoilGrids for any coordinates, cached per location."""

    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._mem: dict[str, object] = {}

    def _power(self, lat: float, lon: float, start: date, end: date) -> WeatherData:
        key = f"power_{_loc(lat, lon)}_{start}_{end}"
        if key in self._mem:
            return self._mem[key]  # type: ignore[return-value]
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            meta = json.loads(path.read_text(encoding="utf-8"))
            daily, elevation = _frame_from_json(meta["daily"]), meta["elevation_m"]
        else:
            from qatra_ai.data.sources.nasa_power import NasaPowerError, fetch_power_daily

            try:
                res = fetch_power_daily(lat, lon, start, end)
            except (NasaPowerError, OSError) as exc:
                raise WeatherUnavailableError(f"NASA POWER: {exc}") from exc
            elevation = res.elevation_m or 0.0
            daily = compute_daily_et0(
                res.daily, latitude_deg=res.latitude, elevation_m=elevation, wind_height_m=2.0
            )
            daily = daily[daily["et0"].notna()]  # recent days may still be fill values
            path.write_text(
                json.dumps({"daily": _frame_to_json(daily), "elevation_m": elevation}),
                encoding="utf-8",
            )
        wd = WeatherData(daily, "nasa_power:daily_point", DataClass.INFERRED, elevation)
        self._mem[key] = wd
        return wd

    def weather(self, lat: float, lon: float, start: date, end: date) -> WeatherData:
        return self._power(lat, lon, start, end)

    def live_weather(self, lat: float, lon: float, start: date, today: date) -> WeatherData:
        """Past days from NASA POWER, the most recent days and the next week from Open-Meteo.
        Cached for the day it was fetched (the forecast changes daily)."""
        key = f"live_{_loc(lat, lon)}_{start}_{today}"
        if key in self._mem:
            return self._mem[key]  # type: ignore[return-value]
        from qatra_ai.data.sources.open_meteo import OpenMeteoError, fetch_daily_weather

        power_end = today - timedelta(days=POWER_LATENCY_DAYS)
        hist = self._power(lat, lon, start, power_end).daily if start <= power_end else None
        gap_start = (
            (hist.index.max().date() + timedelta(days=1))
            if hist is not None and len(hist)
            else start
        )
        past_days = (today - gap_start).days
        if past_days > 92:
            raise WeatherUnavailableError(
                f"NASA POWER has no data after {gap_start - timedelta(days=1)}; Open-Meteo "
                "covers only the last 92 days"
            )
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            meta = json.loads(path.read_text(encoding="utf-8"))
            recent, elevation = _frame_from_json(meta["daily"]), meta["elevation_m"]
        else:
            try:
                res = fetch_daily_weather(
                    lat,
                    lon,
                    kind="forecast",
                    past_days=max(past_days, 0),
                    forecast_days=LIVE_FORECAST_DAYS,
                )
            except (OpenMeteoError, OSError) as exc:
                raise WeatherUnavailableError(f"Open-Meteo forecast: {exc}") from exc
            elevation = res.elevation_m
            recent = compute_daily_et0(
                res.daily, latitude_deg=res.latitude, elevation_m=elevation, wind_height_m=10.0
            )
            path.write_text(
                json.dumps({"daily": _frame_to_json(recent), "elevation_m": elevation}),
                encoding="utf-8",
            )
        recent = recent.loc[pd.Timestamp(gap_start) :]
        parts = [p for p in (hist, recent) if p is not None and len(p)]
        daily = pd.concat(parts).sort_index()
        daily = daily[~daily.index.duplicated(keep="first")]
        if pd.Timestamp(today) not in daily.index:
            raise WeatherUnavailableError(f"no forecast for {today} at {lat}, {lon}")
        wd = WeatherData(
            daily,
            "nasa_power:daily_point+open_meteo:forecast",
            DataClass.INFERRED,
            elevation,
            forecast_from=today,
        )
        self._mem[key] = wd
        return wd

    def soil(self, lat: float, lon: float) -> SoilWaterProperties:
        key = f"soil_{_loc(lat, lon)}"
        if key in self._mem:
            return self._mem[key]  # type: ignore[return-value]
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            soil = SoilWaterProperties.model_validate_json(path.read_text(encoding="utf-8"))
        else:
            import httpx

            from qatra_ai.data.sources.soilgrids import SoilGridsError, fetch_soilgrids

            try:
                soil = fetch_soilgrids(lat, lon).to_soil_properties()
            except SoilGridsError as exc:
                no_data = "no SoilGrids prediction" in str(exc)
                raise SoilUnavailableError(f"SoilGrids: {exc}", no_data_here=no_data) from exc
            except (httpx.HTTPError, OSError) as exc:
                raise SoilUnavailableError(f"SoilGrids: {exc}") from exc
            path.write_text(soil.model_dump_json(), encoding="utf-8")
        self._mem[key] = soil
        return soil


NasaPowerProvider = PublicDataProvider  # former name
