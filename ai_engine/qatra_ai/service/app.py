"""Read-only HTTP API over the QATRA engine for the dashboard (local demo; no auth, no writes).

Run: uv run uvicorn qatra_ai.service.app:app --port 8100
Every response is {"meta": {...provenance and demo labels...}, "data": ...}.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from qatra_ai.agronomy.crops import get_crop
from qatra_ai.agronomy.water_balance import ZoneSetup, simulate_water_balance
from qatra_ai.assistant.assistant import QatraAssistant
from qatra_ai.assistant.tools import AssistantContext
from qatra_ai.contracts import DataClass, Provenance
from qatra_ai.evaluation.synthetic_water import ALL_FAULTS, generate
from qatra_ai.orchestrator.decision import FarmContext, ZoneContext, decide
from qatra_ai.predictive.anomaly import DetectorConfig, detect_anomalies
from qatra_ai.service import demo_farm as farm
from qatra_ai.service.data import CACHE_DIR, DataProvider, NasaPowerProvider
from qatra_ai.suitability.engine import SiteConditions, assess_crops

DEMO_NOTE = (
    "Demo farm: location, weather and soil are real; the farm (zones, crops, pump, "
    "solar, quotas, past irrigation) is hypothetical. Not advice for any real farm."
)
FORECAST_NOTE = "Forecast = historical 2025 weather replayed (no archived forecasts are used)."
RESULTS_DIR = CACHE_DIR.parent / "results"


def _meta(**extra: Any) -> dict:
    return {"farm_id": farm.FARM_ID, "demo": True, "note": DEMO_NOTE, **extra}


class AskRequest(BaseModel):
    """Module level: FastAPI resolves postponed annotations from module globals."""

    question: str = Field(min_length=2, max_length=1000)
    day: date | None = None


def create_app(provider: DataProvider | None = None) -> FastAPI:
    prov = provider or NasaPowerProvider()
    app = FastAPI(title="QATRA engine API (demo)", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    def valid_day(day: date | None) -> date:
        d = day or farm.DEFAULT_DAY
        first = min(z.season_start for z in farm.ZONES) + timedelta(days=7)
        last = farm.WEATHER_END - timedelta(days=4)
        if not first <= d <= last:
            raise HTTPException(422, f"day must be between {first} and {last}")
        return d

    def setups() -> list[tuple[farm.DemoZone, ZoneSetup]]:
        soil = prov.soil()
        return [
            (
                z,
                ZoneSetup(
                    crop=get_crop(z.crop),
                    season_start=z.season_start,
                    soil=soil,
                    area_ha=z.area_ha,
                    application_efficiency=farm.APPLICATION_EFFICIENCY,
                    initial_depletion_mm=0.0,
                ),
            )
            for z in farm.ZONES
        ]

    @lru_cache(maxsize=64)
    def balance_tables(day: date) -> dict[str, pd.DataFrame]:
        w = prov.season_weather().daily
        hist = w.loc[: pd.Timestamp(day - timedelta(days=1))]
        out = {}
        for z, setup in setups():
            h = hist.loc[pd.Timestamp(z.season_start) :]
            irr = pd.Series(
                farm.PAST_IRRIGATION_MM, index=h.index[:: farm.PAST_IRRIGATION_EVERY_DAYS]
            )
            table, _ = simulate_water_balance(setup, h, irr)
            out[z.zone_id] = table
        return out

    @lru_cache(maxsize=32)
    def decision(day: date):
        wd = prov.season_weather()
        tables = balance_tables(day)
        zones = []
        for z, setup in setups():
            prov_ = Provenance(
                data_class=wd.data_class,
                source=f"fao56_water_balance+{wd.source}",
                quality_grade="C",
                method="modelled; no soil-moisture sensor",
            )
            zones.append(
                ZoneContext(
                    z.zone_id,
                    setup,
                    z.design_flow_m3h,
                    float(tables[z.zone_id]["dr_end_mm"].iloc[-1]),
                    prov_,
                )
            )
        ctx = FarmContext(
            farm_id=farm.FARM_ID,
            as_of=datetime.combine(day, datetime.min.time()),
            zones=zones,
            forecast_daily=wd.daily.loc[pd.Timestamp(day) :],
            forecast_source=wd.source,
            pump=farm.PUMP,
            pv_rated_kw=farm.PV_RATED_KW,
            battery=farm.BATTERY,
            max_volume_per_day_m3=farm.MAX_VOLUME_PER_DAY_M3,
        )
        return decide(ctx)

    @lru_cache(maxsize=1)
    def suitability():
        wd = prov.multi_year_weather()
        soil = prov.soil().model_copy(update={"soil_depth_m": farm.SITE_SOIL_DEPTH_M})
        site = SiteConditions(
            latitude=farm.LATITUDE,
            soil=soil,
            irrigation_water_ec_ds_m=farm.SITE_IRRIGATION_EC_DS_M,
            available_water_m3_per_ha=farm.SITE_WATER_M3_PER_HA,
            available_energy_kwh_per_ha=farm.SITE_ENERGY_KWH_PER_HA,
            pumping_head_m=60,
            weather_source=wd.source,
            weather_data_class=wd.data_class,
        )
        return assess_crops(farm.SUITABILITY_CROPS, site, wd.daily)

    @lru_cache(maxsize=1)
    def anomalies():
        sysd = generate(seed=3, faults=ALL_FAULTS, start="2025-06-01")
        res = detect_anomalies(
            sysd.data, sysd.schedule, DetectorConfig(design_flow_m3h=sysd.design_flow_m3h)
        )
        return sysd, res

    # --- endpoints -------------------------------------------------------------------------

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/farm")
    def farm_info() -> dict:
        soil = prov.soil()
        return {
            "meta": _meta(),
            "data": {
                "name": farm.FARM_NAME,
                "latitude": farm.LATITUDE,
                "longitude": farm.LONGITUDE,
                "timezone": farm.TIMEZONE,
                "default_day": str(farm.DEFAULT_DAY),
                "day_range": [
                    str(min(z.season_start for z in farm.ZONES) + timedelta(days=7)),
                    str(farm.WEATHER_END - timedelta(days=4)),
                ],
                "zones": [
                    {
                        "zone_id": z.zone_id,
                        "name": z.name,
                        "crop": z.crop,
                        "crop_name": get_crop(z.crop).names,
                        "area_ha": z.area_ha,
                        "season_start": str(z.season_start),
                        "design_flow_m3h": z.design_flow_m3h,
                        "polygon": [[farm.LATITUDE + a, farm.LONGITUDE + b] for a, b in z.polygon],
                    }
                    for z in farm.ZONES
                ],
                "pump": farm.PUMP.model_dump(),
                "pv_rated_kw": farm.PV_RATED_KW,
                "battery": farm.BATTERY.model_dump(),
                "max_volume_per_day_m3": farm.MAX_VOLUME_PER_DAY_M3,
                "soil": soil.model_dump(mode="json"),
            },
        }

    @app.get("/api/decision")
    def get_decision(day: date | None = None) -> dict:
        d = valid_day(day)
        env = decision(d)
        return {
            "meta": _meta(day=str(d), forecast_note=FORECAST_NOTE),
            "data": env.model_dump(mode="json"),
        }

    @app.get("/api/water-balance")
    def water_balance(day: date | None = None) -> dict:
        d = valid_day(day)
        out = {}
        for zid, t in balance_tables(d).items():
            cols = [
                "season_day",
                "stage",
                "kc",
                "taw_mm",
                "raw_mm",
                "dr_end_mm",
                "ks",
                "et0_mm",
                "etc_mm",
                "eta_mm",
                "precip_mm",
                "peff_mm",
                "irrigation_gross_mm",
                "deep_percolation_mm",
            ]
            rows = t[cols].round(3).reset_index()
            rows["date"] = rows["date"].dt.date.astype(str)
            out[zid] = rows.to_dict("records")
        wd = prov.season_weather()
        return {
            "meta": _meta(
                day=str(d),
                weather_source=wd.source,
                weather_data_class=wd.data_class.value,
                irrigation_note="past irrigation is a hypothetical practice "
                f"({farm.PAST_IRRIGATION_MM} mm every "
                f"{farm.PAST_IRRIGATION_EVERY_DAYS} days)",
            ),
            "data": out,
        }

    @app.get("/api/suitability")
    def get_suitability() -> dict:
        wd = prov.multi_year_weather()
        return {
            "meta": _meta(
                weather_source=wd.source,
                years=list(farm.CLIMATE_YEARS),
                site={
                    "water_m3_per_ha": farm.SITE_WATER_M3_PER_HA,
                    "energy_kwh_per_ha": farm.SITE_ENERGY_KWH_PER_HA,
                    "irrigation_ec_ds_m": farm.SITE_IRRIGATION_EC_DS_M,
                    "soil_depth_m": farm.SITE_SOIL_DEPTH_M,
                },
            ),
            "data": [r.model_dump(mode="json") for r in suitability()],
        }

    @app.get("/api/climate")
    def get_climate() -> dict:
        path = RESULTS_DIR / "climate_2050.json"
        if not path.exists():
            raise HTTPException(
                404,
                "climate results not computed yet: run `uv run python examples/climate_2050.py`",
            )
        return {
            "meta": _meta(
                kind_note="historical / projected / hypothetical; projections "
                "are a spread across models, not a forecast"
            ),
            "data": json.loads(path.read_text(encoding="utf-8")),
        }

    @app.get("/api/anomalies")
    def get_anomalies() -> dict:
        sysd, res = anomalies()
        series = sysd.data[["inlet_m3h", "pressure_kpa"]].copy()
        series["scheduled_m3h"] = sum(
            sysd.schedule[z].astype(float) * f for z, f in sysd.design_flow_m3h.items()
        )
        series = series.round(3).reset_index().rename(columns={"index": "time"})
        series["time"] = series["time"].astype(str)
        return {
            "meta": _meta(
                data_class=DataClass.SIMULATED.value,
                simulated_note="Synthetic hydraulic data with injected, labelled "
                "faults (no real meter data yet).",
                injected_faults=[
                    {"name": f.name, "start": str(f.start), "end": str(f.end)} for f in sysd.faults
                ],
            ),
            "data": {
                "events": [e.model_dump(mode="json") for e in res.events],
                "series": series.to_dict("records"),
                "assumptions": res.assumptions,
            },
        }

    @app.post("/api/assistant")
    def ask(req: AskRequest) -> dict:
        d = valid_day(req.day)
        _, res = anomalies()
        ctx = AssistantContext(
            decision=decision(d), suitability=suitability(), anomalies=res.events
        )
        ans = QatraAssistant(ctx).ask(req.question)
        return {
            "meta": _meta(day=str(d)),
            "data": {
                "text": ans.text,
                "language": ans.language,
                "verified": ans.verified,
                "used_fallback": ans.used_fallback,
                "fallback_reason": ans.fallback_reason,
                "violations": ans.violations,
                "citations": ans.citations,
                "tool_calls": [c.name for c in ans.tool_calls],
                "provider": ans.provider,
                "model": ans.model,
            },
        }

    return app


app = create_app()
