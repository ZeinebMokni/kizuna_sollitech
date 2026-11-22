"""
QATRA Backend – FastAPI Server
==============================
Hackathon Kizuna 2026 · Tunisie × Japon

Architecture proposée :
  - FastAPI + Pydantic v2 (Python 3.11+)
  - PostgreSQL + PostGIS (géospatial)
  - Rasterio + TiTiler (traitement Sentinel-2 / NDVI)
  - WebSockets (télémétrie ESP32 temps réel)
  - Sentinelhub SDK (accès Copernicus CDSE)

IMPORTANT : Ce backend est un scaffold documenté pour le pitch hackathon.
Les endpoints sont définis avec leurs contrats d'entrée/sortie complets.
L'implémentation réelle (PostGIS, Rasterio, MQTT) est indiquée par des TODO.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Any
import asyncio
import json
import random
import datetime

# ─────────────────────────────────────────────
#  App Configuration
# ─────────────────────────────────────────────

app = FastAPI(
    title="QATRA Agricultural Intelligence API",
    description="Backend for the QATRA smart farm platform (Kizuna 2026 Hackathon)",
    version="1.0.0-hackathon",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3005", "https://qatra.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Bbox", "X-Date"],
)

# Real Sentinel-2 data (Copernicus Data Space) — see sentinel.py
from sentinel import router as sentinel_router  # noqa: E402
from agentic_system.router import router as agentic_router  # noqa: E402
from database.router import router as database_router  # noqa: E402

app.include_router(sentinel_router)
app.include_router(agentic_router)
app.include_router(database_router)


# ─────────────────────────────────────────────
#  Pydantic Models (Request / Response Schemas)
# ─────────────────────────────────────────────

class GeoPoint(BaseModel):
    lng: float = Field(..., ge=-180, le=180, description="Longitude WGS84")
    lat: float = Field(..., ge=-90, le=90, description="Latitude WGS84")

class PolygonGeometry(BaseModel):
    type: str = "Polygon"
    coordinates: List[List[List[float]]]

class FarmZoneCreate(BaseModel):
    name: str
    crop_type: str
    polygon: PolygonGeometry

class NDVIResponse(BaseModel):
    zone_id: str
    acquisition_date: str
    cloud_cover_percent: float
    ndvi_min: float
    ndvi_mean: float
    ndvi_max: float
    ndvi_std: float
    sensor: str = "Sentinel-2 L2A MSI"
    resolution_meters: int = 10
    tile_id: str = "T32SMF"
    attribution: str = "Copernicus CDSE / ESA"

class SensorTelemetry(BaseModel):
    device_id: str
    farm_id: str
    zone_id: str
    timestamp: str
    soil_moisture_percent: float
    temperature_c: float
    humidity_percent: float
    battery_percent: float
    signal_rssi: int

class IrrigationCommand(BaseModel):
    zone_id: str
    action: str = Field(..., pattern="^(open|close|schedule)$")
    duration_minutes: Optional[int] = Field(None, ge=1, le=120)
    target_moisture_percent: Optional[float] = Field(None, ge=10, le=90)

class CropRecommendationRequest(BaseModel):
    lat: float
    lng: float
    area_ha: float
    soil_type: str
    water_source: str
    budget_tnd: float
    season: str = Field(..., pattern="^(autumn|spring|summer|winter)$")

class MarketForecastQuery(BaseModel):
    crop_type: str
    region: str
    horizon_weeks: int = Field(12, ge=4, le=52)


# ─────────────────────────────────────────────
#  Health Check
# ─────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    return {
        "service": "QATRA Agricultural Intelligence Backend",
        "version": "1.0.0-hackathon",
        "status": "online",
        "hackathon": "Kizuna 2026 · Tunisie × Japon",
        "organizers": "Esprit × JICA × Takolor",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    }

@app.get("/health", tags=["Health"])
async def health():
    from database.router import database_health

    return {"status": "ok", "database": database_health(), "redis": "not_configured"}


# ─────────────────────────────────────────────
#  Farm Management Endpoints
# ─────────────────────────────────────────────

@app.get("/api/farms/{farm_id}", tags=["Farm"])
async def get_farm(farm_id: str):
    """
    Récupère la fiche complète d'une exploitation agricole.
    TODO: Implémenter requête PostgreSQL + PostGIS (ST_AsGeoJSON)
    """
    # Prefer the persisted farm graph when PostgreSQL is available.
    try:
        from database.models import Farm
        from database.session import SessionLocal

        with SessionLocal() as session:
            farm = session.get(Farm, farm_id)
            if farm is not None:
                return {
                    "id": farm.id,
                    "name": farm.name,
                    "owner_name": "Tarak Ben Salem",
                    "governorate": farm.governorate or "",
                    "delegation": farm.delegation or "",
                    "total_area_ha": farm.area_ha or 0,
                    "center_coordinates": (farm.center_geojson or {}).get("coordinates", [9.665, 37.04]),
                    "solar_capacity_kw": 18.5,
                    "water_source": "Puits profond 145m",
                    "zones": [
                        {
                            "id": zone.id,
                            "farm_id": zone.farm_id,
                            "name": zone.name,
                            "crop_type": zone.crop_type or "",
                            "area_ha": zone.area_ha or 0,
                            "target_moisture_min": zone.target_moisture_min or 30,
                            "target_moisture_max": zone.target_moisture_max or 60,
                            "status": zone.status,
                            "polygon": zone.polygon_geojson,
                        }
                        for zone in farm.zones
                    ],
                    "source": "postgresql",
                }
    except Exception:
        # Keep the demo contract available while PostgreSQL is offline.
        pass

    # Fallback demo response when PostgreSQL is unavailable or the farm is unknown.
    return {
        "id": farm_id,
        "name": "Domaine El-Baraka",
        "governorate": "Sidi Bouzid",
        "delegation": "Regueb",
        "total_area_ha": 15.3,
        "center_coordinates": [9.4858, 35.0382],
        "solar_capacity_kw": 18.5,
        "water_source": "Puits profond 145m",
    }

@app.post("/api/farms/{farm_id}/zones", tags=["Farm"], status_code=201)
async def create_zone(farm_id: str, zone: FarmZoneCreate):
    """
    Crée une nouvelle parcelle géoréférencée dans la ferme.
    TODO: Implémenter INSERT dans PostgreSQL/PostGIS avec ST_GeomFromGeoJSON
    TODO: Calculer superficie réelle avec ST_Area(ST_Transform(geom, 32632))
    """
    return {
        "id": f"zone-new-{random.randint(1000, 9999)}",
        "farm_id": farm_id,
        "name": zone.name,
        "crop_type": zone.crop_type,
        "area_ha": round(random.uniform(0.5, 5.0), 2),  # TODO: PostGIS area calculation
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        "message": "Parcelle enregistrée dans le SIG PostGIS",
    }


# ─────────────────────────────────────────────
#  Sentinel-2 / NDVI Endpoints
# ─────────────────────────────────────────────

@app.get("/api/satellite/scenes", tags=["Satellite & NDVI"])
async def list_sentinel2_scenes(
    lat: float = Query(..., description="Latitude du centre"),
    lng: float = Query(..., description="Longitude du centre"),
    max_cloud_cover: float = Query(10.0, le=100),
    limit: int = Query(10, le=50),
):
    """
    Liste les passages Sentinel-2 disponibles pour une localisation.
    TODO: Implémenter via Sentinelhub SDK (SentinelHubCatalog / CDSE OAuth2)
    TODO: Filtrer par tuile MGRS T32SMF pour la Tunisie centrale
    """
    return {
        "query": {"lat": lat, "lng": lng, "tile": "T32SMF"},
        "scenes": [
            {
                "id": "S2B_MSIL2A_20261112T102219_N0500_R065_T32SMF",
                "date": "2026-11-12",
                "cloud_cover": 1.8,
                "sensor": "Sentinel-2B",
                "orbit": 65,
            },
            {
                "id": "S2A_MSIL2A_20261028T102141_N0500_R065_T32SMF",
                "date": "2026-10-28",
                "cloud_cover": 0.4,
                "sensor": "Sentinel-2A",
                "orbit": 65,
            },
        ],
    }

@app.get("/api/satellite/ndvi/{zone_id}", response_model=NDVIResponse, tags=["Satellite & NDVI"])
async def get_zone_ndvi(
    zone_id: str,
    scene_id: str = Query(..., description="ID du passage Sentinel-2"),
):
    """
    Calcule les statistiques NDVI pour une parcelle à partir des bandes B04/B08 Sentinel-2.
    
    Formule NDVI = (B08 NIR - B04 RED) / (B08 NIR + B04 RED)
    
    TODO: Implémenter avec Rasterio + Sentinelhub SDK :
      1. Télécharger B04 (rouge) et B08 (PIR) depuis CDSE
      2. Découper sur la géométrie de la zone (rasterio.mask)
      3. Calculer NDVI pixel par pixel
      4. Calculer statistiques (min, mean, max, std)
      5. Générer tuiles WMTS pour affichage MapLibre (TiTiler)
    """
    return NDVIResponse(
        zone_id=zone_id,
        acquisition_date="2026-11-12",
        cloud_cover_percent=1.8,
        ndvi_min=round(random.uniform(0.1, 0.3), 3),
        ndvi_mean=round(random.uniform(0.35, 0.65), 3),
        ndvi_max=round(random.uniform(0.6, 0.85), 3),
        ndvi_std=round(random.uniform(0.04, 0.12), 3),
    )

@app.get("/api/satellite/tiles/{scene_id}/{z}/{x}/{y}.png", tags=["Satellite & NDVI"])
async def get_ndvi_tile(scene_id: str, z: int, x: int, y: int, colormap: str = "RdYlGn"):
    """
    Sert les tuiles NDVI au format PNG pour affichage MapLibre GL JS.
    TODO: Implémenter avec TiTiler (titiler.extension.stac ou titiler.core)
    TODO: Colormaps disponibles : RdYlGn, Greens, Spectral, viridis
    """
    raise HTTPException(
        status_code=501,
        detail="TiTiler NDVI tile server - à déployer avec titiler-pgstac. Voir README pour configuration.",
    )


# ─────────────────────────────────────────────
#  IoT / ESP32 Sensor Endpoints
# ─────────────────────────────────────────────

@app.get("/api/telemetry/{device_id}", response_model=SensorTelemetry, tags=["IoT Sensors"])
async def get_latest_telemetry(device_id: str):
    """
    Récupère la dernière mesure d'un capteur ESP32.
    TODO: Implémenter via MQTT broker (Mosquitto) ou Redis time-series
    """
    return SensorTelemetry(
        device_id=device_id,
        farm_id="farm-sbz-01",
        zone_id="zone-1",
        timestamp=datetime.datetime.utcnow().isoformat() + "Z",
        soil_moisture_percent=round(random.uniform(20, 65), 1),
        temperature_c=round(random.uniform(22, 38), 1),
        humidity_percent=round(random.uniform(30, 70), 1),
        battery_percent=round(random.uniform(60, 100), 1),
        signal_rssi=random.randint(-85, -40),
    )

@app.post("/api/irrigation/command", tags=["IoT Sensors"])
async def send_irrigation_command(command: IrrigationCommand):
    """
    Envoie une commande d'ouverture/fermeture de vanne à un ESP32 via MQTT.
    
    TODO: Publier sur topic MQTT : qatra/{farm_id}/zones/{zone_id}/valve
    TODO: Payload JSON : {"action": "open", "duration_minutes": 45, "timestamp": "..."}
    TODO: Vérifier sécurité : arrêt d'urgence actif → rejeter commande
    """
    persisted = False
    farm_id = "farm-sbz-01"
    try:
        from database.models import FarmZone, IrrigationCommand as DbIrrigationCommand
        from database.session import SessionLocal

        with SessionLocal.begin() as session:
            zone = session.get(FarmZone, command.zone_id)
            if zone is not None:
                farm_id = zone.farm_id
                session.add(DbIrrigationCommand(
                    farm_id=farm_id,
                    zone_id=command.zone_id,
                    action=command.action,
                    duration_minutes=command.duration_minutes,
                    status="queued",
                    mqtt_topic=f"qatra/{farm_id}/zones/{command.zone_id}/valve",
                ))
                persisted = True
    except Exception:
        pass

    return {
        "status": "command_queued",
        "zone_id": command.zone_id,
        "action": command.action,
        "duration_minutes": command.duration_minutes,
        "mqtt_topic": f"qatra/{farm_id}/zones/{command.zone_id}/valve",
        "acknowledged_at": datetime.datetime.utcnow().isoformat() + "Z",
        "persisted": persisted,
        "disclaimer": "Commande enregistrée; publication MQTT physique à connecter au gateway ESP32.",
    }


# ─────────────────────────────────────────────
#  AI / Intelligence Endpoints
# ─────────────────────────────────────────────

@app.post("/api/intelligence/crop-recommendation", tags=["AI Intelligence"])
async def get_crop_recommendation(request: CropRecommendationRequest):
    """
    Recommandation de culture basée sur :
    - Données pédologiques (type de sol, pH estimé)
    - Climat historique et prévisions (Meteostat API)
    - Disponibilité eau (source + volume autorisé)
    - Données de marché ONAGRI (prix, offre/demande)
    - Budget exploitation
    
    TODO: Implémenter modèle ML (RandomForest ou XGBoost) entraîné sur
          données ONAGRI 2015-2026 + données FAO Tunisie
    """
    crops = [
        {"name": "Piment Baklouti", "roi_tnd_per_ha": 8500, "water_m3_per_ha": 3200, "risk": "medium"},
        {"name": "Tomates primeurs", "roi_tnd_per_ha": 12000, "water_m3_per_ha": 5800, "risk": "medium"},
        {"name": "Olivier Chemlali", "roi_tnd_per_ha": 4200, "water_m3_per_ha": 1800, "risk": "low"},
    ]
    return {
        "query": request.model_dump(),
        "recommendations": crops,
        "model": "QATRA-AgroML-v1 (stub hackathon)",
        "data_sources": ["ONAGRI", "FAO-TUN", "Meteostat", "INAT-Tunisie"],
        "disclaimer": "Recommandations indicatives - valider avec un ingénieur agronome",
    }

@app.get("/api/intelligence/market-forecast", tags=["AI Intelligence"])
async def get_market_forecast(
    crop_type: str = Query(...),
    region: str = Query("Sidi Bouzid"),
    horizon_weeks: int = Query(12),
):
    """
    Prévision de prix et de disponibilité marché pour un produit agricole.
    TODO: Scraper ONAGRI.tn / SMSA + modèle ARIMA ou Prophet
    TODO: Intégrer données d'importation / exportation Tunisie (INS)
    """
    return {
        "crop_type": crop_type,
        "region": region,
        "horizon_weeks": horizon_weeks,
        "current_price_tnd_per_kg": round(random.uniform(0.8, 4.5), 2),
        "forecast_price_tnd_per_kg": round(random.uniform(0.9, 5.2), 2),
        "trend": random.choice(["bullish", "stable", "bearish"]),
        "shortage_probability": round(random.uniform(0, 0.6), 2),
        "data_source": "ONAGRI.tn (données publiques Tunisie)",
    }


# ─────────────────────────────────────────────
#  WebSocket – Live IoT Telemetry Stream
# ─────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)

    async def broadcast(self, message: dict):
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

@app.websocket("/ws/telemetry/{farm_id}")
async def websocket_telemetry(websocket: WebSocket, farm_id: str):
    """
    Stream WebSocket pour télémétrie temps réel ESP32 → Frontend.
    
    Message format (toutes les 5 secondes) :
    {
        "type": "sensor_update",
        "farm_id": "farm-sbz-01",
        "timestamp": "2026-11-21T10:30:00Z",
        "zones": [
            {"zone_id": "zone-1", "soil_moisture": 38.4, "temp_c": 28.1, ...},
            ...
        ]
    }
    
    TODO: Brancher sur MQTT broker (Mosquitto) au lieu de simulation
    TODO: Sécuriser avec JWT Bearer token (Authorization header)
    """
    await manager.connect(websocket)
    try:
        while True:
            await asyncio.sleep(5)
            telemetry = {
                "type": "sensor_update",
                "farm_id": farm_id,
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "zones": [
                    {
                        "zone_id": f"zone-{i}",
                        "soil_moisture_percent": round(random.uniform(15, 75), 1),
                        "temperature_c": round(random.uniform(22, 38), 1),
                        "humidity_percent": round(random.uniform(30, 70), 1),
                        "battery_percent": round(random.uniform(60, 100), 0),
                    }
                    for i in range(1, 6)
                ],
            }
            await websocket.send_json(telemetry)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ─────────────────────────────────────────────
#  Run (dev mode)
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
