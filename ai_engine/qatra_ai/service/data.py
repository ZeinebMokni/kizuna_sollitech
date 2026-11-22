"""Data access for the service: real weather and soil for the demo location, cached on disk.

`DataProvider` is the seam used by tests (an offline provider with synthetic data can replace
the network one). Every frame carries its source and data class.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

import pandas as pd

from qatra_ai.agronomy.daily_et0 import compute_daily_et0
from qatra_ai.agronomy.soil import SoilWaterProperties
from qatra_ai.contracts import DataClass
from qatra_ai.service import demo_farm as farm

CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "service"


@dataclass(frozen=True)
class WeatherData:
    daily: pd.DataFrame  # et0, precip, rs, tmax, tmin, ... (DatetimeIndex)
    source: str
    data_class: DataClass
    elevation_m: float


class DataProvider(Protocol):
    def season_weather(self) -> WeatherData: ...
    def multi_year_weather(self) -> WeatherData: ...
    def soil(self) -> SoilWaterProperties: ...


def _frame_to_json(df: pd.DataFrame) -> str:
    return df.reset_index().to_json(orient="records", date_format="iso")


def _frame_from_json(text: str) -> pd.DataFrame:
    df = pd.DataFrame(json.loads(text))
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    return df.set_index("date")


class NasaPowerProvider:
    """NASA POWER weather + SoilGrids soil, each fetched once and cached on disk."""

    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._mem: dict[str, object] = {}

    def _weather(self, key: str, start: date, end: date) -> WeatherData:
        if key in self._mem:
            return self._mem[key]  # type: ignore[return-value]
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            meta = json.loads(path.read_text(encoding="utf-8"))
            daily = _frame_from_json(meta["daily"])
            elevation = meta["elevation_m"]
        else:
            from qatra_ai.data.sources.nasa_power import fetch_power_daily

            res = fetch_power_daily(farm.LATITUDE, farm.LONGITUDE, start, end)
            elevation = res.elevation_m or 0.0
            daily = compute_daily_et0(
                res.daily, latitude_deg=res.latitude, elevation_m=elevation, wind_height_m=2.0
            )
            path.write_text(
                json.dumps({"daily": _frame_to_json(daily), "elevation_m": elevation}),
                encoding="utf-8",
            )
        wd = WeatherData(daily, "nasa_power:daily_point", DataClass.INFERRED, elevation)
        self._mem[key] = wd
        return wd

    def season_weather(self) -> WeatherData:
        return self._weather("weather_season", farm.WEATHER_START, farm.WEATHER_END)

    def multi_year_weather(self) -> WeatherData:
        y0, y1 = farm.CLIMATE_YEARS
        return self._weather("weather_multi_year", date(y0, 1, 1), date(y1, 12, 31))

    def soil(self) -> SoilWaterProperties:
        if "soil" in self._mem:
            return self._mem["soil"]  # type: ignore[return-value]
        path = self.cache_dir / "soil.json"
        if path.exists():
            soil = SoilWaterProperties.model_validate_json(path.read_text(encoding="utf-8"))
        else:
            from qatra_ai.data.sources.soilgrids import fetch_soilgrids

            soil = fetch_soilgrids(farm.LATITUDE, farm.LONGITUDE).to_soil_properties()
            path.write_text(soil.model_dump_json(), encoding="utf-8")
        self._mem["soil"] = soil
        return soil
