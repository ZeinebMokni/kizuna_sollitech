"""
QATRA · Real Sentinel-2 data from the Copernicus Data Space Ecosystem (CDSE)
===========================================================================

Uses the Sentinel Hub APIs hosted by CDSE (free account, monthly quota):
  - Catalog API      → list real Sentinel-2 L2A acquisitions over a field
  - Process API      → NDVI image (PNG) clipped to the field, clouds masked
  - Statistical API  → NDVI mean / min / max for a date, and over time

Credentials stay on the server. Put them in backend/.env:
    CDSE_CLIENT_ID=sh-xxxxxxxx-....
    CDSE_CLIENT_SECRET=xxxxxxxx
(Create them at https://shapps.dataspace.copernicus.eu/dashboard/ → User settings → OAuth clients.)
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import time
from pathlib import Path
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

# ─────────────────────────────── configuration ───────────────────────────────

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
SH_BASE = "https://sh.dataspace.copernicus.eu"
CATALOG_URL = f"{SH_BASE}/api/v1/catalog/1.0.0/search"
PROCESS_URL = f"{SH_BASE}/api/v1/process"
STATS_URL = f"{SH_BASE}/api/v1/statistics"

CACHE_TTL_SECONDS = 6 * 3600        # identical requests are served from memory for 6 h
HTTP_TIMEOUT = httpx.Timeout(45.0, connect=10.0)
CLOUD_SCL_CLASSES = (3, 8, 9, 10)   # SCL: cloud shadow, cloud medium / high, cirrus


def _load_dotenv() -> None:
    """Minimal .env loader (KEY=VALUE lines) so no extra dependency is needed."""
    env_file = Path(__file__).with_name(".env")
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def _credentials() -> tuple[str, str] | None:
    cid = os.environ.get("CDSE_CLIENT_ID", "").strip()
    secret = os.environ.get("CDSE_CLIENT_SECRET", "").strip()
    return (cid, secret) if cid and secret else None


# ─────────────────────────────── auth + cache ───────────────────────────────

_token: dict[str, Any] = {"value": None, "expires": 0.0}
_cache: dict[str, tuple[float, Any]] = {}


async def _access_token(client: httpx.AsyncClient) -> str:
    if _token["value"] and time.time() < _token["expires"] - 60:
        return _token["value"]
    creds = _credentials()
    if not creds:
        raise HTTPException(503, "Copernicus non configuré : ajoutez CDSE_CLIENT_ID et CDSE_CLIENT_SECRET dans backend/.env")
    resp = await client.post(
        TOKEN_URL,
        data={"grant_type": "client_credentials", "client_id": creds[0], "client_secret": creds[1]},
    )
    if resp.status_code != 200:
        raise HTTPException(502, f"Authentification Copernicus refusée ({resp.status_code}). Vérifiez l'identifiant et la clé.")
    payload = resp.json()
    _token["value"] = payload["access_token"]
    _token["expires"] = time.time() + float(payload.get("expires_in", 600))
    return _token["value"]


def _cache_key(kind: str, body: Any) -> str:
    return kind + ":" + hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def _cache_get(key: str) -> Any:
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_TTL_SECONDS:
        return hit[1]
    return None


def _cache_put(key: str, value: Any) -> None:
    _cache[key] = (time.time(), value)


async def _post(client: httpx.AsyncClient, url: str, body: dict, accept: str = "application/json") -> httpx.Response:
    token = await _access_token(client)
    resp = await client.post(url, json=body, headers={"Authorization": f"Bearer {token}", "Accept": accept})
    if resp.status_code == 401:  # token expired early: retry once
        _token["value"] = None
        token = await _access_token(client)
        resp = await client.post(url, json=body, headers={"Authorization": f"Bearer {token}", "Accept": accept})
    if resp.status_code >= 400:
        detail = resp.text[:300]
        raise HTTPException(502, f"Copernicus a renvoyé une erreur {resp.status_code} : {detail}")
    return resp


# ─────────────────────────────── geometry helpers ───────────────────────────────

class Geometry(BaseModel):
    type: str = Field("Polygon", pattern="^Polygon$")
    coordinates: list[list[list[float]]]


def _bbox(geom: Geometry) -> tuple[float, float, float, float]:
    ring = geom.coordinates[0]
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


def _pixel_size(geom: Geometry, metres_per_px: float, max_px: int) -> tuple[int, int]:
    """Output size so one pixel ≈ `metres_per_px` (Sentinel-2 native is 10 m)."""
    min_x, min_y, max_x, max_y = _bbox(geom)
    lat = (min_y + max_y) / 2
    w_m = (max_x - min_x) * 111_320 * math.cos(math.radians(lat))
    h_m = (max_y - min_y) * 110_540
    w = max(8, min(max_px, round(w_m / metres_per_px)))
    h = max(8, min(max_px, round(h_m / metres_per_px)))
    return w, h


def _bounds(geom: Geometry) -> dict:
    return {
        "geometry": geom.model_dump(),
        "properties": {"crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"},
    }


# ─────────────────────────────── evalscripts ───────────────────────────────

_CLOUD_TEST = " || ".join(f"s.SCL == {c}" for c in CLOUD_SCL_CLASSES)

# Same colour ramp as the frontend legend (lib/geo/ndvi.ts)
NDVI_IMAGE_SCRIPT = f"""//VERSION=3
function setup() {{
  return {{ input: [{{ bands: ["B04", "B08", "SCL", "dataMask"] }}], output: {{ bands: 4 }} }};
}}
const ramp = [
  [-1.0, [211, 47, 47]], [0.15, [211, 47, 47]], [0.15, [251, 140, 0]], [0.30, [251, 140, 0]],
  [0.30, [253, 216, 53]], [0.45, [253, 216, 53]], [0.45, [124, 179, 66]], [0.60, [124, 179, 66]],
  [0.60, [46, 125, 50]], [1.0, [46, 125, 50]]
];
function colour(v) {{
  for (let i = ramp.length - 1; i >= 0; i--) if (v >= ramp[i][0]) return ramp[i][1];
  return ramp[0][1];
}}
function evaluatePixel(s) {{
  if (!s.dataMask || {_CLOUD_TEST}) return [0, 0, 0, 0];
  const ndvi = (s.B08 - s.B04) / (s.B08 + s.B04 + 1e-6);
  const c = colour(ndvi);
  return [c[0] / 255, c[1] / 255, c[2] / 255, 0.92];
}}
"""

NDVI_STATS_SCRIPT = f"""//VERSION=3
function setup() {{
  return {{
    input: [{{ bands: ["B04", "B08", "SCL", "dataMask"] }}],
    output: [
      {{ id: "ndvi", bands: 1, sampleType: "FLOAT32" }},
      {{ id: "dataMask", bands: 1 }}
    ]
  }};
}}
function evaluatePixel(s) {{
  const clear = s.dataMask && !({_CLOUD_TEST});
  const ndvi = (s.B08 - s.B04) / (s.B08 + s.B04 + 1e-6);
  return {{ ndvi: [ndvi], dataMask: [clear ? 1 : 0] }};
}}
"""


def _day_range(date: str) -> dict:
    try:
        d = dt.date.fromisoformat(date)
    except ValueError as exc:
        raise HTTPException(422, "Date invalide, format attendu : AAAA-MM-JJ") from exc
    return {"from": f"{d.isoformat()}T00:00:00Z", "to": f"{d.isoformat()}T23:59:59Z"}


def _parse_stats(entry: dict) -> Optional[dict]:
    band = entry.get("outputs", {}).get("ndvi", {}).get("bands", {}).get("B0", {})
    stats = band.get("stats") or {}
    count = stats.get("sampleCount", 0)
    nodata = stats.get("noDataCount", 0)
    valid = count - nodata
    if not count or valid <= 0 or stats.get("mean") is None or (isinstance(stats.get("mean"), str)):
        return None
    return {
        "from": entry["interval"]["from"][:10],
        "to": entry["interval"]["to"][:10],
        "mean": round(float(stats["mean"]), 3),
        "min": round(float(stats["min"]), 3),
        "max": round(float(stats["max"]), 3),
        "std": round(float(stats.get("stDev", 0.0)), 3),
        "clear_fraction": round(valid / count, 2),
    }


# ─────────────────────────────── API ───────────────────────────────

router = APIRouter(prefix="/api/sentinel", tags=["Sentinel-2 (Copernicus, réel)"])


class ScenesRequest(BaseModel):
    geometry: Geometry
    days: int = Field(120, ge=5, le=730)
    max_cloud: float = Field(40, ge=0, le=100)


class NdviRequest(BaseModel):
    geometry: Geometry
    date: str = Field(..., description="AAAA-MM-JJ, date d'un passage Sentinel-2")


class TimeseriesRequest(BaseModel):
    geometry: Geometry
    months: int = Field(12, ge=1, le=36)
    interval_days: int = Field(10, ge=5, le=31)


@router.get("/status")
async def status():
    """Whether Copernicus credentials are configured (no network call)."""
    return {
        "configured": _credentials() is not None,
        "provider": "Copernicus Data Space Ecosystem · Sentinel-2 L2A",
        "resolution_m": 10,
    }


@router.post("/scenes")
async def scenes(req: ScenesRequest):
    """Real Sentinel-2 L2A acquisitions over the geometry, most recent first."""
    body = {
        "collections": ["sentinel-2-l2a"],
        "datetime": (
            f"{(dt.datetime.utcnow() - dt.timedelta(days=req.days)).strftime('%Y-%m-%dT00:00:00Z')}/"
            f"{dt.datetime.utcnow().strftime('%Y-%m-%dT23:59:59Z')}"
        ),
        "intersects": req.geometry.model_dump(),
        "limit": 100,
        "filter": f"eo:cloud_cover <= {req.max_cloud}",
        "filter-lang": "cql2-text",
        "fields": {"include": ["id", "properties.datetime", "properties.eo:cloud_cover", "properties.platform"]},
    }
    key = _cache_key("scenes", body)
    if (cached := _cache_get(key)) is not None:
        return cached
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await _post(client, CATALOG_URL, body)
    by_date: dict[str, dict] = {}
    for f in resp.json().get("features", []):
        props = f.get("properties", {})
        date = str(props.get("datetime", ""))[:10]
        cloud = props.get("eo:cloud_cover")
        if not date:
            continue
        item = {
            "id": f.get("id"),
            "date": date,
            "cloud_cover": round(float(cloud), 1) if cloud is not None else None,
            "platform": props.get("platform"),
        }
        # keep the clearest acquisition per day
        prev = by_date.get(date)
        if prev is None or (item["cloud_cover"] or 100) < (prev["cloud_cover"] or 100):
            by_date[date] = item
    result = sorted(by_date.values(), key=lambda s: s["date"], reverse=True)
    _cache_put(key, result)
    return result


@router.post("/ndvi.png")
async def ndvi_image(req: NdviRequest):
    """Colour NDVI image of the geometry for one acquisition date (transparent outside the field and under clouds)."""
    width, height = _pixel_size(req.geometry, metres_per_px=5, max_px=1024)  # 2× upsampling for a smooth display
    body = {
        "input": {
            "bounds": _bounds(req.geometry),
            "data": [{"type": "sentinel-2-l2a", "dataFilter": {"timeRange": _day_range(req.date), "mosaickingOrder": "leastCC"}}],
        },
        "output": {"width": width, "height": height, "responses": [{"identifier": "default", "format": {"type": "image/png"}}]},
        "evalscript": NDVI_IMAGE_SCRIPT,
    }
    key = _cache_key("ndvi", body)
    png = _cache_get(key)
    if png is None:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await _post(client, PROCESS_URL, body, accept="image/png")
        png = resp.content
        _cache_put(key, png)
    min_x, min_y, max_x, max_y = _bbox(req.geometry)
    return Response(
        content=png,
        media_type="image/png",
        headers={
            "X-Bbox": f"{min_x},{min_y},{max_x},{max_y}",
            "X-Date": req.date,
            "Cache-Control": "private, max-age=21600",
            "Access-Control-Expose-Headers": "X-Bbox, X-Date",
        },
    )


@router.post("/ndvi/stats")
async def ndvi_stats(req: NdviRequest):
    """NDVI mean / min / max over the geometry for one acquisition date (cloud pixels excluded)."""
    width, height = _pixel_size(req.geometry, metres_per_px=10, max_px=512)
    body = {
        "input": {"bounds": _bounds(req.geometry), "data": [{"type": "sentinel-2-l2a", "dataFilter": {"mosaickingOrder": "leastCC"}}]},
        "aggregation": {
            "timeRange": _day_range(req.date),
            "aggregationInterval": {"of": "P1D"},
            "width": width,
            "height": height,
            "evalscript": NDVI_STATS_SCRIPT,
        },
        "calculations": {"default": {}},
    }
    key = _cache_key("stats", body)
    if (cached := _cache_get(key)) is not None:
        return cached
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await _post(client, STATS_URL, body)
    parsed = [s for s in (_parse_stats(e) for e in resp.json().get("data", [])) if s]
    result = parsed[0] if parsed else None
    if result is None:
        raise HTTPException(404, "Aucun pixel exploitable ce jour-là (nuages ou pas de passage).")
    result["date"] = req.date
    _cache_put(key, result)
    return result


@router.post("/ndvi/timeseries")
async def ndvi_timeseries(req: TimeseriesRequest):
    """NDVI over time for the geometry (one value per interval, cloudy intervals skipped)."""
    width, height = _pixel_size(req.geometry, metres_per_px=10, max_px=512)
    end = dt.date.today()
    start = end - dt.timedelta(days=round(req.months * 30.44))
    body = {
        "input": {"bounds": _bounds(req.geometry), "data": [{"type": "sentinel-2-l2a", "dataFilter": {"mosaickingOrder": "leastCC"}}]},
        "aggregation": {
            "timeRange": {"from": f"{start.isoformat()}T00:00:00Z", "to": f"{end.isoformat()}T23:59:59Z"},
            "aggregationInterval": {"of": f"P{req.interval_days}D"},
            "width": width,
            "height": height,
            "evalscript": NDVI_STATS_SCRIPT,
        },
        "calculations": {"default": {}},
    }
    key = _cache_key("series", body)
    if (cached := _cache_get(key)) is not None:
        return cached
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await _post(client, STATS_URL, body)
    points = [s for s in (_parse_stats(e) for e in resp.json().get("data", [])) if s and s["clear_fraction"] >= 0.5]
    result = {"points": points, "from": start.isoformat(), "to": end.isoformat(), "interval_days": req.interval_days}
    _cache_put(key, result)
    return result
