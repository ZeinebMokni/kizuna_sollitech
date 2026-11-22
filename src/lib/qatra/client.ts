import type { Farm, FarmZone, HealthStatus } from '@/types';
import { DEMO_FARM } from '@/lib/mockData';

export const QATRA_API_URL = (process.env.NEXT_PUBLIC_QATRA_API_URL || 'http://localhost:8000').replace(/\/$/, '');

type BackendZone = {
  id: string;
  farm_id: string;
  name: string;
  crop_type?: string;
  area_ha?: number;
  target_moisture_min?: number;
  target_moisture_max?: number;
  status?: string;
  polygon?: FarmZone['polygon'] | null;
};

type BackendFarm = {
  id: string;
  name: string;
  owner_name?: string;
  governorate?: string;
  delegation?: string;
  total_area_ha?: number;
  center_coordinates?: [number, number];
  solar_capacity_kw?: number;
  zones?: BackendZone[];
  source?: string;
};

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${QATRA_API_URL}${path}`, { cache: 'no-store' });
  if (!response.ok) throw new Error(`QATRA API ${response.status}`);
  return response.json() as Promise<T>;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${QATRA_API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`QATRA API ${response.status}`);
  return response.json() as Promise<T>;
}

function asHealthStatus(value: string | undefined, fallback: HealthStatus): HealthStatus {
  return value === 'healthy' || value === 'warning' || value === 'critical' || value === 'irrigating' || value === 'nodata'
    ? value
    : fallback;
}

export async function fetchFarm(farmId = 'farm-sbz-01'): Promise<{ farm: Farm; source: string }> {
  const payload = await getJson<BackendFarm>(`/api/farms/${farmId}`);
  const zones = (payload.zones ?? []).map((remoteZone) => {
    const fallback = DEMO_FARM.zones.find((zone) => zone.id === remoteZone.id);
    if (!fallback) return null;
    return {
      ...fallback,
      name: remoteZone.name || fallback.name,
      farmId: remoteZone.farm_id || fallback.farmId,
      cropType: remoteZone.crop_type || fallback.cropType,
      areaHa: remoteZone.area_ha || fallback.areaHa,
      targetMoistureMin: remoteZone.target_moisture_min ?? fallback.targetMoistureMin,
      targetMoistureMax: remoteZone.target_moisture_max ?? fallback.targetMoistureMax,
      status: asHealthStatus(remoteZone.status, fallback.status),
      polygon: remoteZone.polygon ?? fallback.polygon,
    } satisfies FarmZone;
  }).filter((zone): zone is FarmZone => zone !== null);

  const farm: Farm = {
    ...DEMO_FARM,
    id: payload.id || DEMO_FARM.id,
    name: payload.name || DEMO_FARM.name,
    ownerName: payload.owner_name || DEMO_FARM.ownerName,
    governorate: payload.governorate || DEMO_FARM.governorate,
    delegation: payload.delegation || DEMO_FARM.delegation,
    totalAreaHa: payload.total_area_ha ?? DEMO_FARM.totalAreaHa,
    centerCoordinates: payload.center_coordinates || DEMO_FARM.centerCoordinates,
    solarCapacityKw: payload.solar_capacity_kw ?? DEMO_FARM.solarCapacityKw,
    zones: zones.length ? zones : DEMO_FARM.zones,
  };
  return { farm, source: payload.source || 'backend' };
}

export type QatraDevice = { id: string; farm_id: string; zone_id?: string | null; kind: string; protocol?: string; status: string; metadata: Record<string, unknown> };
export type QatraAlert = { id: number; zone_id?: string | null; severity: string; category: string; title: string; message: string; status: string; created_at: string };
export type QatraTelemetry = { device_id: string; zone_id?: string | null; recorded_at: string; measurements: Record<string, number | string | boolean>; source: string; data_class: string };

export async function fetchDevices(farmId = 'farm-sbz-01') {
  return (await getJson<{ data: QatraDevice[] }>(`/api/database/farms/${farmId}/devices`)).data;
}

export async function fetchAlerts(farmId = 'farm-sbz-01') {
  return (await getJson<{ data: QatraAlert[] }>(`/api/database/farms/${farmId}/alerts`)).data;
}

export async function fetchLatestTelemetry(farmId = 'farm-sbz-01') {
  return (await getJson<{ data: QatraTelemetry[] }>(`/api/database/farms/${farmId}/telemetry/latest`)).data;
}

export async function queueIrrigationCommand(zoneId: string, action: 'open' | 'close', durationMinutes = 45) {
  return postJson<{ status: string; persisted: boolean }>('/api/irrigation/command', {
    zone_id: zoneId,
    action,
    duration_minutes: durationMinutes,
  });
}

export type ZoneHistory = {
  decisions: Array<{ id: number; agent_id: string; type: string; status: string; recommendation: string; confidence?: number; predicted_impact?: Record<string, unknown>; created_at: string }>;
  impacts: Array<{ metric: string; baseline?: number; observed?: number; unit: string; source: string; measured_at: string }>;
};

export async function fetchZoneHistory(farmId: string, zoneId: string) {
  return getJson<ZoneHistory>(`/api/database/farms/${farmId}/zones/${zoneId}/history`);
}

export async function requestAgenticDecision(zone: FarmZone) {
  return postJson<{ recommendation: string; expected_impact: Record<string, unknown>; findings: Array<{ agent_id: string; status: string; observation: string; recommendation: string; confidence: number; checkpoints: string[] }> }>('/api/agentic/decisions', {
    farm_id: zone.farmId,
    zones: [{
      zone_id: zone.id,
      moisture_percent: zone.soilMoisturePercent,
      target_min_percent: zone.targetMoistureMin,
      target_max_percent: zone.targetMoistureMax,
      temperature_c: zone.temperatureC,
      irrigation_active: zone.irrigationStatus === 'active',
      crop_type: zone.cropType,
    }],
    energy: { solar_kw: 14.8, pump_kw: 6.8, battery_soc_percent: 89, battery_power_kw: 4.5, grid_available: true },
    sources: [{ name: 'ESP32 + PostgreSQL telemetry', source_type: 'sensor', quality: 'good' }],
    human_validation: true,
  });
}
