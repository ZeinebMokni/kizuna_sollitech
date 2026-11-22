"""Everything the API computes for ONE farm, from its profile and the data provider.

Two time modes, decided by the profile:
- replay (demo farms, or any profile with a `replay` window): a past season is replayed; the
  "forecast" is the weather that actually happened (labelled as such).
- live (real farms without `replay`): today's date in the farm's time zone; past weather from
  NASA POWER + Open-Meteo, the next days from the Open-Meteo forecast.

Nothing farm-specific lives in code: location, zones, pump, energy and limits come from the
profile. When something required is missing (e.g. no irrigation history), the runtime says so
with `MissingInputError` instead of assuming a value.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta
from functools import cached_property, lru_cache
from zoneinfo import ZoneInfo

import pandas as pd

from qatra_ai.agronomy.crops import get_crop
from qatra_ai.agronomy.soil import SoilWaterProperties, soil_from_texture
from qatra_ai.agronomy.water_balance import ZoneSetup, simulate_water_balance
from qatra_ai.contracts import DataClass, Provenance
from qatra_ai.evaluation.synthetic_water import ALL_FAULTS, generate
from qatra_ai.farms.profile import FarmProfile, ZoneProfile
from qatra_ai.orchestrator.decision import FarmContext, ZoneContext, decide
from qatra_ai.predictive.anomaly import DetectorConfig, detect_anomalies
from qatra_ai.service.data import DataProvider, SoilUnavailableError, WeatherData
from qatra_ai.suitability.engine import SiteConditions, assess_crops

MIN_SEASON_DAYS = 7  # a zone needs this much history before its balance is shown
FORECAST_DAYS_NEEDED = 3  # the 72 h scheduler


class MissingInputError(RuntimeError):
    """A required farm input is missing; the message says which and how to supply it."""


class FarmRuntime:
    def __init__(
        self,
        profile: FarmProfile,
        provider: DataProvider,
        today: Callable[[], date] | None = None,
    ):
        self.profile = profile
        self.provider = provider
        self._today = today
        # per-instance caches (functools.lru_cache on methods would share across farms)
        self.balance_tables = lru_cache(maxsize=32)(self._balance_tables)
        self.decision = lru_cache(maxsize=16)(self._decision)

    # --- time ---------------------------------------------------------------------------------

    @property
    def mode(self) -> str:
        return "replay" if self.profile.replay is not None else "live"

    def today(self) -> date:
        if self._today is not None:
            return self._today()
        return datetime.now(ZoneInfo(self.profile.location.timezone)).date()

    @property
    def lat(self) -> float:
        return self.profile.location.latitude

    @property
    def lon(self) -> float:
        return self.profile.location.longitude

    def day_range(self) -> tuple[date, date]:
        first_zone = min(z.season_start for z in self.profile.zones)
        if self.profile.replay is not None:
            r = self.profile.replay
            first = max(first_zone, r.weather_start) + timedelta(days=MIN_SEASON_DAYS)
            return first, r.weather_end - timedelta(days=FORECAST_DAYS_NEEDED + 1)
        t = self.today()
        return t, t

    def default_day(self) -> date:
        return self.profile.replay.default_day if self.profile.replay else self.today()

    def valid_day(self, day: date | None) -> date:
        d = day or self.default_day()
        first, last = self.day_range()
        if not first <= d <= last:
            if self.mode == "live":
                raise ValueError(f"live farm: only today ({first}) can be planned")
            raise ValueError(f"day must be between {first} and {last}")
        return d

    # --- data ---------------------------------------------------------------------------------

    def season_weather(self, day: date) -> WeatherData:
        if self.profile.replay is not None:
            r = self.profile.replay
            return self.provider.weather(self.lat, self.lon, r.weather_start, r.weather_end)
        start = min(z.season_start for z in self.profile.zones) - timedelta(days=1)
        return self.provider.live_weather(self.lat, self.lon, start, day)

    def forecast_note(self, day: date) -> str:
        if self.mode == "replay":
            return (
                f"Forecast = historical weather from {day} onward, replayed (no archived "
                "forecasts are used)."
            )
        return (
            "Forecast = Open-Meteo model forecast from today; past days are gridded estimates "
            "(NASA POWER, Open-Meteo), not on-farm measurements."
        )

    def climate_years(self) -> tuple[int, int]:
        if self.profile.replay is not None:
            return self.profile.replay.climate_years
        y = self.today().year
        return y - 10, y - 1

    @cached_property
    def soil(self) -> SoilWaterProperties:
        """The farm's own soil data if its profile has it, else the SoilGrids map."""
        s = self.profile.soil
        if s is not None:
            if s.theta_fc is not None and s.theta_wp is not None:
                return SoilWaterProperties(
                    theta_fc=s.theta_fc,
                    theta_wp=s.theta_wp,
                    data_class=DataClass.MEASURED,
                    source=s.source,
                    method="measured field capacity and wilting point (farm profile)",
                )
            return soil_from_texture(
                s.sand_pct / 100,  # type: ignore[operator]
                s.clay_pct / 100,  # type: ignore[operator]
                s.organic_matter_pct,  # type: ignore[arg-type]
                source=f"farm texture analysis: {s.source}",
            )
        try:
            return self.provider.soil(self.lat, self.lon)
        except SoilUnavailableError as exc:
            if exc.no_data_here:
                raise MissingInputError(
                    "the SoilGrids map has no soil data at this location (urban, water or "
                    "no-data area). Add `soil:` to the farm profile: a lab texture analysis "
                    "(sand_pct, clay_pct, organic_matter_pct) or measured theta_fc and theta_wp."
                ) from exc
            raise

    # --- engine -------------------------------------------------------------------------------

    def active_zones(self, day: date) -> tuple[list[ZoneProfile], list[str]]:
        """Zones in season for the whole planning horizon from `day`, and notes on the others
        (not planted yet, or an annual crop whose season ends within the horizon)."""
        active, notes = [], []
        for z in self.profile.zones:
            crop = get_crop(z.crop)
            end = z.season_start + timedelta(days=crop.season_length_days)
            if z.season_start + timedelta(days=1) > day:
                notes.append(f"{z.zone_id}: season starts {z.season_start}, not yet active")
            elif not crop.perennial and day + timedelta(days=FORECAST_DAYS_NEEDED) > end:
                notes.append(f"{z.zone_id}: {z.crop} season ends {end}, not planned")
            else:
                active.append(z)
        return active, notes

    def setup(self, z: ZoneProfile) -> ZoneSetup:
        return ZoneSetup(
            crop=get_crop(z.crop),
            season_start=z.season_start,
            soil=self.soil,
            area_ha=z.area_ha,
            application_efficiency=z.application_efficiency,
            initial_depletion_mm=0.0,
        )

    def irrigation_note(self) -> str:
        a = self.profile.assumed_past_irrigation
        if a is None:
            return "no irrigation history"
        return f"past irrigation ASSUMED: {a.mm_per_event:g} mm every {a.every_days} days"

    def _balance_tables(self, day: date) -> dict[str, pd.DataFrame]:
        a = self.profile.assumed_past_irrigation
        if a is None:
            raise MissingInputError(
                "this farm has no irrigation history: add irrigation logs or, as a stated "
                "assumption, `assumed_past_irrigation` to its profile. QATRA does not guess "
                "how much water the zones received."
            )
        w = self.season_weather(day).daily
        hist = w.loc[: pd.Timestamp(day - timedelta(days=1))]
        out = {}
        for z in self.active_zones(day)[0]:
            h = hist.loc[pd.Timestamp(z.season_start) :]
            irr = pd.Series(a.mm_per_event, index=h.index[:: a.every_days])
            table, _ = simulate_water_balance(self.setup(z), h, irr)
            out[z.zone_id] = table
        return out

    def _decision(self, day: date):
        wd = self.season_weather(day)
        tables = self.balance_tables(day)
        if not tables:
            raise MissingInputError(f"no zone has an active season on {day}")
        forecast = wd.daily.loc[pd.Timestamp(day) :]
        if len(forecast) < FORECAST_DAYS_NEEDED:
            raise MissingInputError(
                f"only {len(forecast)} forecast day(s) from {day}; the planner needs "
                f"{FORECAST_DAYS_NEEDED}"
            )
        zones = []
        for z in self.active_zones(day)[0]:
            zones.append(
                ZoneContext(
                    z.zone_id,
                    self.setup(z),
                    z.design_flow_m3h,
                    float(tables[z.zone_id]["dr_end_mm"].iloc[-1]),
                    Provenance(
                        data_class=wd.data_class,
                        source=f"fao56_water_balance+{wd.source}",
                        quality_grade="C",
                        method="modelled; no soil-moisture sensor",
                    ),
                )
            )
        e = self.profile.energy
        ctx = FarmContext(
            farm_id=self.profile.farm_id,
            as_of=datetime.combine(day, datetime.min.time()),
            zones=zones,
            forecast_daily=forecast,
            forecast_source=wd.source,
            pump=self.profile.pump,
            pv_rated_kw=e.pv_rated_kw,
            battery=e.battery,
            grid_hours=frozenset(e.grid_hours or ()),
            grid_max_kw=e.grid_max_kw or 0.0,
            max_volume_per_day_m3=self.profile.water.max_volume_per_day_m3,
        )
        return decide(ctx)

    @cached_property
    def suitability(self):
        if not self.profile.suitability_candidates:
            raise MissingInputError("no `suitability_candidates` in this farm's profile")
        y0, y1 = self.climate_years()
        wd = self.provider.weather(self.lat, self.lon, date(y0, 1, 1), date(y1, 12, 31))
        soil = self.soil
        if self.profile.soil_depth_m is not None:
            soil = soil.model_copy(update={"soil_depth_m": self.profile.soil_depth_m})
        site = SiteConditions(
            latitude=self.lat,
            soil=soil,
            irrigation_water_ec_ds_m=self.profile.water.irrigation_ec_ds_m,
            available_water_m3_per_ha=self.profile.water.seasonal_m3_per_ha,
            available_energy_kwh_per_ha=self.profile.energy.seasonal_kwh_per_ha,
            pumping_head_m=self.profile.pump.total_head_m,
            pump_efficiency=self.profile.pump.pump_efficiency,
            weather_source=wd.source,
            weather_data_class=wd.data_class,
        )
        crops = {
            c.crop: (c.planting_month, c.planting_day) for c in self.profile.suitability_candidates
        }
        return assess_crops(crops, site, wd.daily), wd

    @cached_property
    def anomalies(self):
        """Demo farms: labelled synthetic data. Real farms: None until a flow meter streams."""
        if self.profile.kind != "demo":
            return None
        start = self.profile.replay.default_day.replace(day=1) if self.profile.replay else None
        sysd = generate(seed=3, faults=ALL_FAULTS, start=str(start or "2025-06-01"))
        res = detect_anomalies(
            sysd.data, sysd.schedule, DetectorConfig(design_flow_m3h=sysd.design_flow_m3h)
        )
        return sysd, res
