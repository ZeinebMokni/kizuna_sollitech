/**
 * Client for the QATRA backend's real Sentinel-2 endpoints (backend/sentinel.py).
 * Every call has a timeout and throws a SentinelError with a readable message,
 * so the UI can fall back to the simulated layer during a demo.
 */
import type { LngLat } from '@/lib/parcels/types';

export const API_URL = (process.env.NEXT_PUBLIC_QATRA_API_URL || 'http://localhost:8000').replace(/\/$/, '');

export type PolygonGeometry = { type: 'Polygon'; coordinates: number[][][] };

export interface SentinelScene {
  id: string;
  date: string;
  cloud_cover: number | null;
  platform?: string | null;
}

export interface NdviStats {
  date?: string;
  from: string;
  to: string;
  mean: number;
  min: number;
  max: number;
  std: number;
  clear_fraction: number;
}

export interface NdviImage {
  url: string;
  bbox: [number, number, number, number];
  date: string;
}

export class SentinelError extends Error {
  constructor(message: string, readonly kind: 'offline' | 'unconfigured' | 'upstream' | 'nodata') {
    super(message);
  }
}

/** Ring of [lng, lat] (open or closed) → closed GeoJSON polygon. */
export function toPolygon(ring: LngLat[] | number[][]): PolygonGeometry {
  const pts = ring.map((p) => [Number(p[0]), Number(p[1])]);
  const first = pts[0];
  const last = pts[pts.length - 1];
  if (first && (first[0] !== last[0] || first[1] !== last[1])) pts.push([first[0], first[1]]);
  return { type: 'Polygon', coordinates: [pts] };
}

async function call(path: string, body?: unknown, timeoutMs = 45000): Promise<Response> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  let resp: Response;
  try {
    resp = await fetch(`${API_URL}${path}`, {
      method: body === undefined ? 'GET' : 'POST',
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: ctrl.signal,
    });
  } catch {
    throw new SentinelError('Backend QATRA injoignable (http://localhost:8000). Lancez-le pour obtenir les données réelles.', 'offline');
  } finally {
    clearTimeout(timer);
  }
  if (!resp.ok) {
    let detail = `Erreur ${resp.status}`;
    try {
      detail = (await resp.json()).detail ?? detail;
    } catch {
      /* not JSON */
    }
    const kind = resp.status === 503 ? 'unconfigured' : resp.status === 404 ? 'nodata' : 'upstream';
    throw new SentinelError(detail, kind);
  }
  return resp;
}

export async function getSentinelStatus(): Promise<{ configured: boolean; provider: string }> {
  return (await call('/api/sentinel/status', undefined, 4000)).json();
}

export async function getScenes(geometry: PolygonGeometry, days = 120, maxCloud = 40): Promise<SentinelScene[]> {
  return (await call('/api/sentinel/scenes', { geometry, days, max_cloud: maxCloud })).json();
}

export async function getNdviImage(geometry: PolygonGeometry, date: string): Promise<NdviImage> {
  const resp = await call('/api/sentinel/ndvi.png', { geometry, date }, 60000);
  const blob = await resp.blob();
  const bbox = (resp.headers.get('X-Bbox') ?? '').split(',').map(Number) as [number, number, number, number];
  if (bbox.length !== 4 || bbox.some((n) => !Number.isFinite(n))) {
    const xs = geometry.coordinates[0].map((p) => p[0]);
    const ys = geometry.coordinates[0].map((p) => p[1]);
    return { url: URL.createObjectURL(blob), bbox: [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)], date };
  }
  return { url: URL.createObjectURL(blob), bbox, date };
}

export async function getNdviStats(geometry: PolygonGeometry, date: string): Promise<NdviStats> {
  return (await call('/api/sentinel/ndvi/stats', { geometry, date })).json();
}

export async function getNdviTimeseries(geometry: PolygonGeometry, months = 12): Promise<{ points: NdviStats[]; from: string; to: string }> {
  return (await call('/api/sentinel/ndvi/timeseries', { geometry, months, interval_days: 10 }, 90000)).json();
}
