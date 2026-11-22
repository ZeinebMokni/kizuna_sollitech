from __future__ import annotations

from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from .session import SessionLocal, database_url
from .models import Alert, Decision, Device, Farm, FarmZone, ImpactMeasurement, MarketplaceListing, TelemetryReading, WeatherObservation

router = APIRouter(prefix="/api/database", tags=["Database integration"])


@router.get("/health")
def database_health():
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "postgresql", "url_configured": bool(database_url())}
    except Exception as exc:
        return {"status": "unavailable", "database": "postgresql", "detail": str(exc)}


@router.get("/relationship-map")
def relationship_map():
    return {
        "root": "farms",
        "relations": [
            {"from": "farms", "to": "farm_zones", "key": "farm_id", "features": ["dashboard", "map", "analytics", "irrigation"]},
            {"from": "farm_zones", "to": "telemetry_readings", "key": "zone_id", "features": ["ESP32", "live status", "alerts"]},
            {"from": "telemetry_readings", "to": "decisions", "key": "evidence", "features": ["agentic decisions", "checkpoints"]},
            {"from": "decisions", "to": "irrigation_commands", "key": "decision_id", "features": ["pump", "valves", "workflow"]},
            {"from": "farms", "to": "satellite_scenes", "key": "farm_id", "features": ["Sentinel-2", "NDVI"]},
            {"from": "satellite_scenes", "to": "ndvi_observations", "key": "scene_id + zone_id", "features": ["growth history"]},
            {"from": "farms", "to": "farm_connections", "key": "source_farm_id / target_farm_id", "features": ["nearby farms", "shared resources"]},
            {"from": "farms", "to": "marketplace_listings", "key": "farm_id", "features": ["cost/m²", "revenue", "profit"]},
            {"from": "decisions", "to": "impact_measurements", "key": "decision_id", "features": ["predicted vs real impact"]},
        ],
        "privacy": "farmer-owned data stays private by default; admin views should use aggregate or consented records.",
    }


@router.post("/init", status_code=201)
def initialize_database():
    try:
        from .session import create_schema

        create_schema()
        return {"status": "ready", "message": "QATRA PostgreSQL schema created or already exists."}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"PostgreSQL unavailable: {exc}") from exc


@router.get("/farms/{farm_id}/zones")
def farm_zones(farm_id: str):
    with SessionLocal() as session:
        zones = session.query(FarmZone).filter(FarmZone.farm_id == farm_id).order_by(FarmZone.id).all()
        return {"farm_id": farm_id, "source": "postgresql", "data": [
            {
                "id": zone.id,
                "farm_id": zone.farm_id,
                "name": zone.name,
                "crop_type": zone.crop_type,
                "area_ha": zone.area_ha,
                "status": zone.status,
                "target_moisture_min": zone.target_moisture_min,
                "target_moisture_max": zone.target_moisture_max,
                "polygon": zone.polygon_geojson,
            }
            for zone in zones
        ]}


@router.get("/farms/{farm_id}/devices")
def farm_devices(farm_id: str):
    with SessionLocal() as session:
        devices = session.query(Device).filter(Device.farm_id == farm_id).order_by(Device.id).all()
        return {"farm_id": farm_id, "source": "postgresql", "data": [
            {
                "id": device.id,
                "farm_id": device.farm_id,
                "zone_id": device.zone_id,
                "kind": device.kind,
                "protocol": device.protocol,
                "status": device.status,
                "metadata": device.metadata_json or {},
            }
            for device in devices
        ]}


@router.get("/farms/{farm_id}/alerts")
def farm_alerts(farm_id: str):
    with SessionLocal() as session:
        alerts = session.query(Alert).filter(Alert.farm_id == farm_id).order_by(Alert.created_at.desc()).all()
        return {"farm_id": farm_id, "source": "postgresql", "data": [
            {
                "id": alert.id,
                "zone_id": alert.zone_id,
                "severity": alert.severity,
                "category": alert.category,
                "title": alert.title,
                "message": alert.message,
                "status": alert.status,
                "created_at": alert.created_at.isoformat() if alert.created_at else None,
            }
            for alert in alerts
        ]}


@router.get("/farms/{farm_id}/marketplace")
def farm_marketplace(farm_id: str):
    with SessionLocal() as session:
        listings = session.query(MarketplaceListing).filter(MarketplaceListing.farm_id == farm_id).all()
        return {"farm_id": farm_id, "source": "postgresql", "data": [
            {
                "id": listing.id,
                "zone_id": listing.zone_id,
                "crop_type": listing.crop_type,
                "quantity_kg": listing.quantity_kg,
                "asking_price_tnd_kg": listing.asking_price_tnd_kg,
                "status": listing.status,
                "cost_per_m2_tnd": listing.cost_per_m2_tnd,
                "expected_revenue_tnd": listing.expected_revenue_tnd,
                "expected_profit_tnd": listing.expected_profit_tnd,
            }
            for listing in listings
        ]}


@router.get("/farms/{farm_id}/telemetry/latest")
def latest_telemetry(farm_id: str):
    with SessionLocal() as session:
        rows = session.query(TelemetryReading).join(Device).filter(Device.farm_id == farm_id).order_by(TelemetryReading.recorded_at.desc()).limit(100).all()
        return {"farm_id": farm_id, "source": "postgresql", "data": [
            {
                "device_id": row.device_id,
                "zone_id": row.zone_id,
                "recorded_at": row.recorded_at.isoformat(),
                "measurements": row.measurements,
                "source": row.source,
                "data_class": row.data_class,
            }
            for row in rows
        ]}


@router.get("/farms/{farm_id}/weather")
async def live_weather(farm_id: str):
    """Fetch live weather from Open-Meteo and archive the response in PostgreSQL."""
    with SessionLocal() as session:
        farm = session.get(Farm, farm_id)
        if farm is None:
            raise HTTPException(status_code=404, detail="Farm not found")
        coordinates = (farm.center_geojson or {}).get("coordinates", [9.665, 37.04])

    longitude, latitude = coordinates[0], coordinates[1]
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,weather_code,wind_speed_10m,shortwave_radiation",
        "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,et0_fao_evapotranspiration,shortwave_radiation",
        "forecast_days": 7,
        "timezone": "Africa/Tunis",
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get("https://api.open-meteo.com/v1/forecast", params=params)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"Weather provider unavailable: {exc}") from exc

    observed_at = datetime.now(timezone.utc)
    with SessionLocal.begin() as session:
        session.add(WeatherObservation(
            farm_id=farm_id,
            observed_at=observed_at,
            latitude=latitude,
            longitude=longitude,
            current=payload.get("current", {}),
            forecast=payload.get("hourly", {}),
            source="Open-Meteo",
            api_key_required=False,
        ))

    return {
        "meta": {
            "farm_id": farm_id,
            "source": "Open-Meteo",
            "source_url": "https://open-meteo.com/",
            "api_key_required": False,
            "observed_at": observed_at.isoformat(),
            "location": {"latitude": latitude, "longitude": longitude},
        },
        "data": payload,
    }


@router.get("/farms/{farm_id}/zones/{zone_id}/history")
def zone_history(farm_id: str, zone_id: str):
    with SessionLocal() as session:
        decisions = session.query(Decision).filter(Decision.farm_id == farm_id, Decision.zone_id == zone_id).order_by(Decision.created_at.desc()).all()
        impacts = session.query(ImpactMeasurement).filter(ImpactMeasurement.farm_id == farm_id, ImpactMeasurement.zone_id == zone_id).order_by(ImpactMeasurement.measured_at.desc()).all()
        return {
            "farm_id": farm_id,
            "zone_id": zone_id,
            "source": "postgresql",
            "decisions": [{
                "id": decision.id,
                "agent_id": decision.agent_id,
                "type": decision.decision_type,
                "status": decision.status,
                "recommendation": decision.recommendation,
                "confidence": decision.confidence,
                "predicted_impact": decision.predicted_impact,
                "created_at": decision.created_at.isoformat(),
            } for decision in decisions],
            "impacts": [{
                "metric": impact.metric,
                "baseline": impact.baseline_value,
                "observed": impact.observed_value,
                "unit": impact.unit,
                "source": impact.source,
                "measured_at": impact.measured_at.isoformat(),
            } for impact in impacts],
        }
