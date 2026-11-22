"""Read-only HTTP API over the QATRA engine, for ANY farm with a profile (no auth, no writes).

Run: uv run uvicorn qatra_ai.service.app:app --port 8100
Every response is {"meta": {...provenance and labels...}, "data": ...}.

Routes:
  GET  /api/farms                          farms QATRA can run on (+ invalid profiles, reasons)
  GET  /api/farms/{farm_id}                profile, soil, time mode and plannable days
  GET  /api/farms/{farm_id}/decision       ranked interventions + 72 h schedule  (?day=)
  GET  /api/farms/{farm_id}/water-balance  root-zone water balance per zone      (?day=)
  GET  /api/farms/{farm_id}/suitability    crop suitability on 10 years of weather
  GET  /api/farms/{farm_id}/climate        2041-2060 scenarios, if computed for this farm
  GET  /api/farms/{farm_id}/anomalies      leak/fault detection (demo: labelled synthetic data)
  POST /api/farms/{farm_id}/assistant      questions about the decisions
The former single-farm routes (/api/farm, /api/decision, ...) still answer for the default
farm ($QATRA_DEFAULT_FARM, else demo-farm), so older dashboards keep working.
"""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from qatra_ai.agronomy.crops import get_crop
from qatra_ai.assistant.assistant import QatraAssistant, detect_language
from qatra_ai.assistant.tools import AssistantContext
from qatra_ai.contracts import DataClass
from qatra_ai.data.fusion import DataFusionEngine
from qatra_ai.data.ingestion import (
    ImportValidationError,
    import_irrigation_csv,
    import_sensor_csv,
)
from qatra_ai.data.station_selection import STATIONS, select_variable
from qatra_ai.data.store import Zone, data_root, read_observations
from qatra_ai.farms.registry import FarmRegistry, load_registry
from qatra_ai.market import MarketOutlookRequest, market_outlook
from qatra_ai.market.regional import RegionalRequest, regional_equilibrium
from qatra_ai.optimization.allocation import (
    AllocationRequest,
    compare_allocations,
)
from qatra_ai.service import telemetry
from qatra_ai.service.data import (
    CACHE_DIR,
    DataProvider,
    DataUnavailableError,
    PublicDataProvider,
    WeatherUnavailableError,
)
from qatra_ai.service.runtime import FarmRuntime, MissingInputError
from qatra_ai.strategy.agent import FarmStrategyAgent, brief_from_profile

DEMO_NOTE = (
    "Demo farm: location, weather and soil are real; the farm (zones, crops, pump, "
    "solar, quotas, past irrigation) is hypothetical. Not advice for any real farm."
)
REAL_NOTE = (
    "Real farm profile. Weather and soil are gridded/model estimates for its location, not "
    "on-farm measurements; results are decision support and need the farmer's approval."
)
RESULTS_DIR = CACHE_DIR.parent / "results"
WATER_BALANCE_COLUMNS = [
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


class AskRequest(BaseModel):
    """Module level: FastAPI resolves postponed annotations from module globals."""

    question: str = Field(min_length=2, max_length=1000)
    day: date | None = None


class StrategyRequest(BaseModel):
    question: str | None = Field(default=None, max_length=1000)
    language: str | None = Field(default=None, pattern="^(ar|fr|en)$")
    day: date | None = None


def default_farm_id() -> str:
    return os.environ.get("QATRA_DEFAULT_FARM", "demo-farm")


def create_app(
    provider: DataProvider | None = None,
    registry: FarmRegistry | None = None,
    today: Any = None,
) -> FastAPI:
    prov = provider or PublicDataProvider()
    reg = registry or load_registry()
    runtimes: dict[str, FarmRuntime] = {}
    app = FastAPI(title="QATRA engine API", version="0.2.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    def rt(farm_id: str) -> FarmRuntime:
        if farm_id not in runtimes:
            try:
                profile = reg.get(farm_id)
            except KeyError as exc:
                raise HTTPException(404, str(exc.args[0])) from exc
            runtimes[farm_id] = FarmRuntime(profile, prov, today=today)
        return runtimes[farm_id]

    def meta(r: FarmRuntime, **extra: Any) -> dict:
        demo = r.profile.kind == "demo"
        return {
            "farm_id": r.profile.farm_id,
            "demo": demo,
            "mode": r.mode,
            "note": DEMO_NOTE if demo else REAL_NOTE,
            **extra,
        }

    def day_of(r: FarmRuntime, day: date | None) -> date:
        try:
            return r.valid_day(day)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    def guarded(fn):
        """Missing farm inputs -> 409 with the reason; weather download failure -> 503."""
        try:
            return fn()
        except MissingInputError as exc:
            raise HTTPException(409, str(exc)) from exc
        except WeatherUnavailableError as exc:
            raise HTTPException(503, f"weather unavailable: {exc}") from exc
        except DataUnavailableError as exc:
            raise HTTPException(503, f"data unavailable: {exc}") from exc

    # --- handlers (shared by per-farm and legacy routes) --------------------------------------

    def farm_info(farm_id: str) -> dict:
        r = rt(farm_id)
        p = r.profile
        first, last = r.day_range()
        return {
            "meta": meta(r),
            "data": {
                "farm_id": p.farm_id,
                "name": p.name,
                "kind": p.kind,
                "mode": r.mode,
                "latitude": p.location.latitude,
                "longitude": p.location.longitude,
                "timezone": p.location.timezone,
                "region": p.location.region,
                "default_day": str(r.default_day()),
                "day_range": [str(first), str(last)],
                "zones": [
                    {
                        "zone_id": z.zone_id,
                        "name": z.name,
                        "crop": z.crop,
                        "crop_name": get_crop(z.crop).names,
                        "area_ha": z.area_ha,
                        "season_start": str(z.season_start),
                        "design_flow_m3h": z.design_flow_m3h,
                        "polygon": [list(c) for c in z.polygon] if z.polygon else None,
                    }
                    for z in p.zones
                ],
                "pump": p.pump.model_dump(),
                "pv_rated_kw": p.energy.pv_rated_kw,
                "battery": p.energy.battery.model_dump() if p.energy.battery else None,
                "grid_hours": p.energy.grid_hours,
                "max_volume_per_day_m3": p.water.max_volume_per_day_m3,
                "sensors": [s.model_dump() for s in p.sensors],
                "soil": guarded(lambda: r.soil).model_dump(mode="json"),
            },
        }

    def decision(farm_id: str, day: date | None) -> dict:
        r = rt(farm_id)
        d = day_of(r, day)
        env = guarded(lambda: r.decision(d))
        inactive = r.active_zones(d)[1]
        return {
            "meta": meta(
                r,
                day=str(d),
                forecast_note=r.forecast_note(d),
                irrigation_note=r.irrigation_note(),
                inactive_zones=inactive,
            ),
            "data": env.model_dump(mode="json"),
        }

    def water_balance(farm_id: str, day: date | None) -> dict:
        r = rt(farm_id)
        d = day_of(r, day)
        tables = guarded(lambda: r.balance_tables(d))
        out = {}
        for zid, t in tables.items():
            rows = t[WATER_BALANCE_COLUMNS].round(3).reset_index()
            rows["date"] = rows["date"].dt.date.astype(str)
            out[zid] = rows.to_dict("records")
        wd = guarded(lambda: r.season_weather(d))
        return {
            "meta": meta(
                r,
                day=str(d),
                weather_source=wd.source,
                weather_data_class=wd.data_class.value,
                irrigation_note=r.irrigation_note(),
                inactive_zones=r.active_zones(d)[1],
            ),
            "data": out,
        }

    def suitability(farm_id: str) -> dict:
        r = rt(farm_id)
        results, wd = guarded(lambda: r.suitability)
        p = r.profile
        return {
            "meta": meta(
                r,
                weather_source=wd.source,
                years=list(r.climate_years()),
                site={
                    "water_m3_per_ha": p.water.seasonal_m3_per_ha,
                    "energy_kwh_per_ha": p.energy.seasonal_kwh_per_ha,
                    "irrigation_ec_ds_m": p.water.irrigation_ec_ds_m,
                    "soil_depth_m": p.soil_depth_m,
                },
            ),
            "data": [x.model_dump(mode="json") for x in results],
        }

    def climate(farm_id: str) -> dict:
        r = rt(farm_id)
        path = RESULTS_DIR / f"climate_2050_{farm_id}.json"
        legacy = RESULTS_DIR / "climate_2050.json"
        if not path.exists() and farm_id == "demo-farm" and legacy.exists():
            path = legacy
        if not path.exists():
            raise HTTPException(
                404,
                f"climate results not computed for {farm_id} yet: run "
                f"`uv run python examples/climate_2050.py --farm {farm_id}`",
            )
        return {
            "meta": meta(
                r,
                kind_note="historical / projected / hypothetical; projections "
                "are a spread across models, not a forecast",
            ),
            "data": json.loads(path.read_text(encoding="utf-8")),
        }

    def anomalies(farm_id: str) -> dict:
        r = rt(farm_id)
        result = r.anomalies
        if result is None:
            return {
                "meta": meta(
                    r,
                    data_class=None,
                    status="no_meter_data",
                    status_note="No flow-meter data is connected for this farm, so leak and "
                    "fault detection has nothing to analyse yet.",
                ),
                "data": {"events": [], "series": [], "assumptions": []},
            }
        sysd, res = result
        series = sysd.data[["inlet_m3h", "pressure_kpa"]].copy()
        series["scheduled_m3h"] = sum(
            sysd.schedule[z].astype(float) * f for z, f in sysd.design_flow_m3h.items()
        )
        series = series.round(3).reset_index().rename(columns={"index": "time"})
        series["time"] = series["time"].astype(str)
        return {
            "meta": meta(
                r,
                data_class=DataClass.SIMULATED.value,
                status="simulated",
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

    def assistant_context(r: FarmRuntime, d: date) -> AssistantContext:
        """Engine outputs the LLM may read, with the origin of each data feed."""
        env = guarded(lambda: r.decision(d))
        try:
            suit, wd = r.suitability
            suit_dc = wd.data_class
        except (MissingInputError, DataUnavailableError):
            suit, suit_dc = None, None
        anomalies = r.anomalies
        return AssistantContext(
            decision=env,
            suitability=suit,
            suitability_data_class=suit_dc,
            # None (not []) when no hydraulic data exists: "no anomalies" would be a false claim
            anomalies=anomalies[1].events if anomalies is not None else None,
            # demo farms analyse labelled synthetic data (see FarmRuntime.anomalies)
            anomalies_data_class=DataClass.SIMULATED if anomalies is not None else None,
        )

    def ask(farm_id: str, req: AskRequest) -> dict:
        r = rt(farm_id)
        d = day_of(r, req.day)
        ctx = assistant_context(r, d)
        t0 = time.perf_counter()
        ans = QatraAssistant(ctx).ask(req.question)
        telemetry.record(
            "assistant",
            farm_id=farm_id,
            language=ans.language,
            provider=ans.provider,
            model=ans.model,
            verified=ans.verified,
            used_fallback=ans.used_fallback,
            fallback_reason=ans.fallback_reason,
            violations=max(len(ans.violations), ans.rejected_drafts),
            tool_calls=len(ans.tool_calls),
            latency_s=time.perf_counter() - t0,
            violation_messages=ans.violations or ans.draft_violations,
        )
        return {
            "meta": meta(r, day=str(d)),
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

    # --- routes ----------------------------------------------------------------------------

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/api/allocation")
    def allocation(req: AllocationRequest) -> dict:
        envelope = compare_allocations(req)
        return envelope.model_dump(mode="json")

    @app.post("/api/market/outlook")
    def market(req: MarketOutlookRequest) -> dict:
        """Scenario price bands and reflexivity for caller-supplied market parameters."""
        return market_outlook(req).model_dump(mode="json")

    @app.post("/api/market/regional")
    def market_regional(req: RegionalRequest) -> dict:
        """Crop plan and prices solved together for a group of following farms."""
        try:
            return regional_equilibrium(req).model_dump(mode="json")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/farms")
    def list_farms() -> dict:
        return {
            "meta": {
                "default_farm": default_farm_id(),
                "invalid_profiles": [{"file": f, "reason": e} for f, e in reg.errors.items()],
            },
            "data": [
                {
                    "farm_id": p.farm_id,
                    "name": p.name,
                    "kind": p.kind,
                    "mode": "replay" if p.replay else "live",
                    "region": p.location.region,
                    "latitude": p.location.latitude,
                    "longitude": p.location.longitude,
                    "zones": len(p.zones),
                    "area_ha": p.total_area_ha,
                    "crops": sorted({z.crop for z in p.zones}),
                }
                for p in sorted(reg.profiles.values(), key=lambda p: (p.kind != "real", p.name))
            ],
        }

    @app.get("/api/farms/{farm_id}")
    def farm_route(farm_id: str) -> dict:
        return farm_info(farm_id)

    @app.get("/api/farms/{farm_id}/decision")
    def decision_route(farm_id: str, day: date | None = None) -> dict:
        return decision(farm_id, day)

    @app.get("/api/farms/{farm_id}/water-balance")
    def water_balance_route(farm_id: str, day: date | None = None) -> dict:
        return water_balance(farm_id, day)

    @app.get("/api/farms/{farm_id}/suitability")
    def suitability_route(farm_id: str) -> dict:
        return suitability(farm_id)

    @app.get("/api/farms/{farm_id}/climate")
    def climate_route(farm_id: str) -> dict:
        return climate(farm_id)

    @app.get("/api/farms/{farm_id}/anomalies")
    def anomalies_route(farm_id: str) -> dict:
        return anomalies(farm_id)

    @app.post("/api/farms/{farm_id}/assistant")
    def ask_route(farm_id: str, req: AskRequest) -> dict:
        return ask(farm_id, req)

    @app.post("/api/farms/{farm_id}/strategy")
    def strategy_route(farm_id: str, req: StrategyRequest) -> dict:
        """Web trend research + the farm's sensor-based engine state -> checked strategy.
        Billed Claude calls and web searches; without credentials an engine-only fallback."""
        r = rt(farm_id)
        d = day_of(r, req.day)
        ctx = assistant_context(r, d)
        lang = req.language or (detect_language(req.question) if req.question else "en")
        brief = brief_from_profile(r.profile, language=lang, question=req.question)
        t0 = time.perf_counter()
        report = FarmStrategyAgent(ctx).run(brief, as_of=d)
        telemetry.record(
            "strategy",
            farm_id=farm_id,
            language=lang,
            provider=report.provider,
            model=report.model,
            verified=report.verified,
            used_fallback=report.used_fallback,
            fallback_reason=report.fallback_reason,
            violations=max(len(report.violations), report.rejected_submissions),
            tool_calls=len(report.tool_calls),
            latency_s=time.perf_counter() - t0,
            web_research=report.web_research,
            violation_messages=report.violations,
        )
        return {"meta": meta(r, day=str(d)), "data": report.model_dump(mode="json")}

    @app.get("/api/telemetry/llm")
    def llm_telemetry() -> dict:
        """Verified / fallback / rejected-draft rates, served models and latency per kind."""
        return {
            "path": str(telemetry.telemetry_path()),
            **telemetry.summarize(telemetry.read_events()),
        }

    # former single-farm routes -> default farm
    @app.get("/api/farm")
    def legacy_farm() -> dict:
        return farm_info(default_farm_id())

    @app.get("/api/decision")
    def legacy_decision(day: date | None = None) -> dict:
        return decision(default_farm_id(), day)

    @app.get("/api/water-balance")
    def legacy_water_balance(day: date | None = None) -> dict:
        return water_balance(default_farm_id(), day)

    @app.get("/api/suitability")
    def legacy_suitability() -> dict:
        return suitability(default_farm_id())

    @app.get("/api/climate")
    def legacy_climate() -> dict:
        return climate(default_farm_id())

    @app.get("/api/anomalies")
    def legacy_anomalies() -> dict:
        return anomalies(default_farm_id())

    @app.post("/api/assistant")
    def legacy_ask(req: AskRequest) -> dict:
        return ask(default_farm_id(), req)

    @app.get("/api/data-status")
    def data_status() -> dict:
        root = data_root()
        processed = root / "processed" / "dgacta_sidi_bouzid"
        stations = []
        if processed.is_dir():
            for path in sorted(processed.glob("*.csv")):
                try:
                    table = read_observations(path, Zone.PROCESSED)
                    latest = table["timestamp_utc"].max()
                    age_h = (datetime.now(UTC) - latest.to_pydatetime()).total_seconds() / 3600
                    stations.append({
                        "station": path.stem,
                        "rows": len(table),
                        "latest_observation_utc": latest.isoformat(),
                        "age_hours": round(age_h, 1),
                        "stale": age_h > 72,
                        "qc_counts": table["qc_flag"].value_counts().to_dict(),
                    })
                except (OSError, ValueError) as exc:
                    stations.append({"station": path.stem, "error": str(exc)})
        sensor_files = list((root / "sensors").glob("*/*.csv"))
        return {
            "meta": {"generated_at": datetime.now(UTC).isoformat()},
            "data": {
                "stations": stations,
                "sensor_imports": len(sensor_files),
                "raw_archive": str(root / "raw"),
            },
        }

    @app.post("/api/farms/{farm_id}/imports/sensors")
    async def import_sensors(farm_id: str, file: UploadFile) -> dict:
        rt(farm_id)
        content = await file.read()
        try:
            path, table, duplicates = import_sensor_csv(content, farm_id=farm_id)
        except ImportValidationError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {
            "meta": {"farm_id": farm_id, "import_name": file.filename},
            "data": {
                "path": str(path),
                "rows": len(table),
                "duplicates_removed": duplicates,
                "provenance": "sensor_import",
            },
        }

    @app.post("/api/farms/{farm_id}/imports/irrigation")
    async def import_irrigation(farm_id: str, file: UploadFile) -> dict:
        r = rt(farm_id)
        content = await file.read()
        known = {z.zone_id for z in r.profile.zones}
        try:
            path, table, duplicates = import_irrigation_csv(
                content, farm_id=farm_id, known_zones=known
            )
        except ImportValidationError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {
            "meta": {"farm_id": farm_id, "import_name": file.filename},
            "data": {
                "path": str(path),
                "rows": len(table),
                "duplicates_removed": duplicates,
                "provenance": "farmer_reported",
            },
        }

    @app.get("/api/farms/{farm_id}/solar-profile")
    def solar_profile(farm_id: str, start_year: int = 2020, end_year: int = 2020) -> dict:
        r = rt(farm_id)
        try:
            from qatra_ai.data.sources.pvgis import PvgisError, fetch_hourly_solar

            solar = fetch_hourly_solar(
                r.profile.location.latitude,
                r.profile.location.longitude,
                peak_power_kw=r.profile.energy.pv_rated_kw,
                start_year=start_year,
                end_year=end_year,
            )
        except PvgisError as exc:
            raise HTTPException(503, f"PVGIS unavailable: {exc}") from exc
        peak = float(solar["pv_kw"].max())
        daily = solar.set_index("timestamp_utc").resample("1D")["pv_kw"].sum().round(3)
        return {
            "meta": {
                "farm_id": farm_id,
                "source": "PVGIS 5.2 seriescalc",
                "data_class": "inferred",
                "assumed_rated_kw": r.profile.energy.pv_rated_kw,
            },
            "data": {
                "hourly_rows": len(solar),
                "peak_kw": peak,
                "estimated_daily_kwh": daily.to_dict(),
                "fallback": "existing assumed solar profile remains available",
            },
        }

    @app.get("/api/farms/{farm_id}/station-selection")
    def station_selection(farm_id: str, variable: str = "air_temperature") -> dict:
        r = rt(farm_id)
        root = data_root()
        frames = []
        for path in (root / "processed" / "dgacta_sidi_bouzid").glob("*.csv"):
            try:
                frames.append(read_observations(path, Zone.PROCESSED))
            except (OSError, ValueError):
                continue
        observations = frames[0] if not frames else pd.concat(frames, ignore_index=True)
        selection = (
            select_variable(
                observations,
                variable,
                r.profile.location.latitude,
                r.profile.location.longitude,
                datetime.now(UTC),
                max_age=timedelta(days=30),
            )
            if len(frames)
            else None
        )
        engine = DataFusionEngine()
        fused = engine.fuse(
            variable,
            selection,
            model_value=None,
            model_unit="",
            model_source="no model fallback configured",
        )
        return {
            "meta": {
                "farm_id": farm_id,
                "station_catalogue": [
                    {"station_id": s.station_id, "latitude": s.latitude, "longitude": s.longitude}
                    for s in STATIONS
                ],
            },
            "data": fused.__dict__,
        }

    return app


app = create_app()
