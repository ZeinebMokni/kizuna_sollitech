'use client';

import { useEffect, useRef } from 'react';
import type { Map as MapLibreMap, GeoJSONSource, MapLayerMouseEvent } from 'maplibre-gl';
import { useFarmStore } from '@/stores/useFarmStore';
import { useParcelStore } from '@/stores/useParcelStore';
import { DEMO_DEVICES, DEMO_FARM } from '@/lib/mockData';
import type { FarmZone } from '@/types';
import type { Parcel } from '@/lib/parcels/types';

/* ───────────────────────────── Tunable values ─────────────────────────────
 * PUMP              pump / borehole station [lng, lat], read from the pump device
 * LATERALS          drip lines drawn across each zone
 * INSET             how far pipes stay inside the zone edge (0–0.5)
 * PARTICLE_SPACING  metres between water droplets travelling in a pipe
 * PARTICLE_SPEED    visual speed of the water, metres per second
 * DASH_STEP_MS      speed of the flowing dashes
 * WET_PERIOD        seconds per "water spreading" shimmer on irrigated zones
 * ────────────────────────────────────────────────────────────────────────── */
// Pump position comes from the farm data (the irrigation pump device), so the
// network always starts at the real pump wherever the farm is located.
const PUMP: [number, number] =
  (DEMO_DEVICES.find((d) => d.type === 'irrigation_pump')?.coordinates as [number, number] | undefined) ??
  DEMO_FARM.centerCoordinates;
const LATERALS = 6;
const INSET = 0.1;
const PARTICLE_SPACING = 45;
const PARTICLE_SPEED = 55;
const DASH_STEP_MS = 70;
const WET_PERIOD = 2.8;

const SRC = {
  pipes: 'qatra-irr-pipes',
  valves: 'qatra-irr-valves',
  drops: 'qatra-irr-drops',
  wet: 'qatra-irr-wet',
};
const LAYER = {
  wet: 'qatra-irr-wet-fill',
  casing: 'qatra-irr-pipe-casing',
  core: 'qatra-irr-pipe-core',
  glow: 'qatra-irr-pipe-glow',
  flow: 'qatra-irr-pipe-flow',
  drops: 'qatra-irr-drops-circle',
  valveRing: 'qatra-irr-valve-ring',
  valves: 'qatra-irr-valve',
};
const ALL_LAYERS = [LAYER.wet, LAYER.casing, LAYER.glow, LAYER.core, LAYER.flow, LAYER.drops, LAYER.valveRing, LAYER.valves];

// Dash sequence that makes dashes appear to travel along the line (MapLibre pattern).
const DASH_SEQUENCE: number[][] = [
  [0, 4, 3], [0.5, 4, 2.5], [1, 4, 2], [1.5, 4, 1.5], [2, 4, 1], [2.5, 4, 0.5], [3, 4, 0],
  [0, 0.5, 3, 3.5], [0, 1, 3, 3], [0, 1.5, 3, 2.5], [0, 2, 3, 2], [0, 2.5, 3, 1.5], [0, 3, 3, 1], [0, 3.5, 3, 0.5],
];

type LngLat = [number, number];
type PipeKind = 'main' | 'manifold' | 'lateral';
type Pipe = { zoneId: string; kind: PipeKind; from: LngLat; to: LngLat; lengthM: number };
type ZoneNet = { zone: FarmZone; valve: LngLat; pipes: Pipe[] };
type ParcelNet = { id: string; valve: LngLat; pipes: Pipe[] };

const lerp = (a: LngLat, b: LngLat, t: number): LngLat => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];

function metres(a: LngLat, b: LngLat) {
  const dx = (b[0] - a[0]) * Math.cos((a[1] * Math.PI) / 180) * 111320;
  const dy = (b[1] - a[1]) * 110540;
  return Math.hypot(dx, dy);
}

/** Builds main pipe → valve → manifold along the edge facing the pump → drip laterals. */
function buildNetwork(zone: FarmZone): ZoneNet {
  const ring = zone.polygon.coordinates[0].slice(0, 4) as LngLat[];
  const c: LngLat = [ring.reduce((s, p) => s + p[0], 0) / 4, ring.reduce((s, p) => s + p[1], 0) / 4];
  const inset = (p: LngLat) => lerp(p, c, INSET);

  // Inlet edge = the edge whose midpoint is nearest the pump.
  let best = 0;
  let bestD = Infinity;
  for (let i = 0; i < 4; i++) {
    const d = metres(lerp(ring[i], ring[(i + 1) % 4], 0.5), PUMP);
    if (d < bestD) {
      bestD = d;
      best = i;
    }
  }
  const e0 = inset(ring[best]);
  const e1 = inset(ring[(best + 1) % 4]);
  const o0 = inset(ring[(best + 3) % 4]);
  const o1 = inset(ring[(best + 2) % 4]);
  const valve = lerp(e0, e1, 0.5);

  const mk = (kind: PipeKind, from: LngLat, to: LngLat): Pipe => ({ zoneId: zone.id, kind, from, to, lengthM: metres(from, to) });
  const pipes: Pipe[] = [mk('main', PUMP, valve), mk('manifold', valve, e0), mk('manifold', valve, e1)];
  for (let k = 0; k < LATERALS; k++) {
    const t = (k + 0.5) / LATERALS;
    pipes.push(mk('lateral', lerp(e0, e1, t), lerp(o0, o1, t)));
  }
  return { zone, valve, pipes };
}

/** Build a clean parallel irrigation layout for a rectangle-created parcel. */
function buildParcelNetwork(parcel: Parcel): ParcelNet | null {
  const ring = parcel.polygon.slice(0, 4) as LngLat[];
  if (ring.length < 4) return null;
  const c: LngLat = [ring.reduce((s, p) => s + p[0], 0) / 4, ring.reduce((s, p) => s + p[1], 0) / 4];
  const inset = (p: LngLat) => lerp(p, c, 0.08);
  let best = 0;
  let bestD = Infinity;
  for (let i = 0; i < 4; i++) {
    const d = metres(lerp(ring[i], ring[(i + 1) % 4], 0.5), PUMP);
    if (d < bestD) { bestD = d; best = i; }
  }
  const e0 = inset(ring[best]);
  const e1 = inset(ring[(best + 1) % 4]);
  const o0 = inset(ring[(best + 3) % 4]);
  const o1 = inset(ring[(best + 2) % 4]);
  const valve = lerp(e0, e1, 0.5);
  const id = 'parcel-' + parcel.id;
  const mk = (kind: PipeKind, from: LngLat, to: LngLat): Pipe => ({ zoneId: id, kind, from, to, lengthM: metres(from, to) });
  const pipes: Pipe[] = [mk('main', PUMP, valve), mk('manifold', valve, e0), mk('manifold', valve, e1)];
  const count = Math.max(6, Math.min(12, Math.round(Math.sqrt(Math.max(1, parcel.areaHa)) * 2)));
  for (let k = 0; k < count; k++) {
    const t = (k + 0.5) / count;
    pipes.push(mk('lateral', lerp(e0, e1, t), lerp(o0, o1, t)));
  }
  return { id, valve, pipes };
}

const emptyFC = (): GeoJSON.FeatureCollection => ({ type: 'FeatureCollection', features: [] });

interface IrrigationLayerProps {
  map: MapLibreMap | null;
  visible?: boolean;
}

/**
 * Hydraulic network on the digital twin: pipes, drip lines and valves for each
 * zone. When a valve is open the water is visible: glowing pipes, flowing
 * dashes, droplets travelling from the pump, and a gentle wet shimmer on the
 * zone. Clicking a valve opens / closes it (respects the emergency stop).
 */
export function IrrigationLayer({ map, visible = true }: IrrigationLayerProps) {
  const { farm, emergencyStopActive, startIrrigation, stopIrrigation } = useFarmStore();
  const { parcels, toggleParcelIrrigation } = useParcelStore();
  const netRef = useRef<ZoneNet[]>([]);
  const flowingRef = useRef<Set<string>>(new Set());

  // Create sources and layers once.
  useEffect(() => {
    if (!map) return;
    try {
      for (const id of Object.values(SRC)) {
        if (!map.getSource(id)) map.addSource(id, { type: 'geojson', data: emptyFC() });
      }
      if (!map.getLayer(LAYER.wet)) {
        map.addLayer({
          id: LAYER.wet,
          type: 'fill',
          source: SRC.wet,
          paint: { 'fill-color': '#2FB8E0', 'fill-opacity': 0.28 },
        });
        map.addLayer({
          id: LAYER.casing,
          type: 'line',
          source: SRC.pipes,
          layout: { 'line-cap': 'round', 'line-join': 'round' },
          paint: {
            'line-color': 'rgba(8, 34, 42, 0.55)',
            'line-width': ['interpolate', ['linear'], ['zoom'], 14, ['match', ['get', 'kind'], 'main', 4, 'manifold', 3.4, 2.4], 17.5, ['match', ['get', 'kind'], 'main', 10, 'manifold', 8, 6]],
          },
        });
        map.addLayer({
          id: LAYER.glow,
          type: 'line',
          source: SRC.pipes,
          filter: ['==', ['get', 'flowing'], 1],
          layout: { 'line-cap': 'round' },
          paint: {
            'line-color': '#3CCFE0',
            'line-width': ['interpolate', ['linear'], ['zoom'], 14, ['match', ['get', 'kind'], 'main', 10, 'manifold', 8, 6], 17.5, ['match', ['get', 'kind'], 'main', 26, 'manifold', 22, 16]],
            'line-blur': ['interpolate', ['linear'], ['zoom'], 14, 4, 17.5, 10],
            'line-opacity': 0.5,
          },
        });
        map.addLayer({
          id: LAYER.core,
          type: 'line',
          source: SRC.pipes,
          layout: { 'line-cap': 'round', 'line-join': 'round' },
          paint: {
            'line-color': ['case', ['==', ['get', 'flowing'], 1], '#5FD8EA', 'rgba(232, 242, 245, 0.85)'],
            'line-width': ['interpolate', ['linear'], ['zoom'], 14, ['match', ['get', 'kind'], 'main', 2.4, 'manifold', 2, 1.4], 17.5, ['match', ['get', 'kind'], 'main', 6, 'manifold', 5, 3.6]],
          },
        });
        map.addLayer({
          id: LAYER.flow,
          type: 'line',
          source: SRC.pipes,
          filter: ['==', ['get', 'flowing'], 1],
          layout: { 'line-cap': 'butt' },
          paint: {
            'line-color': '#FFFFFF',
            'line-width': ['interpolate', ['linear'], ['zoom'], 14, ['match', ['get', 'kind'], 'main', 1.6, 'manifold', 1.4, 1], 17.5, ['match', ['get', 'kind'], 'main', 4, 'manifold', 3.4, 2.4]],
            'line-opacity': 0.9,
            'line-dasharray': DASH_SEQUENCE[0],
          },
        });
        map.addLayer({
          id: LAYER.drops,
          type: 'circle',
          source: SRC.drops,
          paint: {
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 14, 2.2, 17.5, 5.5],
            'circle-color': '#EAFDFF',
            'circle-stroke-color': '#1FA9C6',
            'circle-stroke-width': 1,
            'circle-opacity': 0.95,
          },
        });
        map.addLayer({
          id: LAYER.valveRing,
          type: 'circle',
          source: SRC.valves,
          filter: ['==', ['get', 'open'], 1],
          paint: {
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 14, 11, 17.5, 18],
            'circle-color': 'rgba(60, 207, 224, 0.25)',
            'circle-stroke-color': 'rgba(60, 207, 224, 0.7)',
            'circle-stroke-width': 1.5,
          },
        });
        map.addLayer({
          id: LAYER.valves,
          type: 'circle',
          source: SRC.valves,
          paint: {
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 14, ['case', ['==', ['get', 'parcel'], 1], 10, 6], 17.5, ['case', ['==', ['get', 'parcel'], 1], 16, 10]],
            'circle-color': ['case', ['==', ['get', 'open'], 1], '#1FA9C6', '#F4F8F9'],
            'circle-stroke-color': '#0E3A44',
            'circle-stroke-width': 2,
          },
        });
      }
    } catch (err) {
      console.warn('Irrigation layer setup error:', err);
    }
  }, [map]);

  // Rebuild network + data whenever zones or the emergency stop change.
  useEffect(() => {
    if (!map) return;
    const nets = farm.zones.map(buildNetwork);
    const parcelNets = parcels.map(buildParcelNetwork).filter((net): net is ParcelNet => Boolean(net));
    netRef.current = nets;
    const flowing = new Set(
      emergencyStopActive ? [] : [
        ...farm.zones.filter((z) => z.irrigationStatus === 'active').map((z) => z.id),
        ...parcels.filter((parcel) => parcel.irrigationActive).map((parcel) => 'parcel-' + parcel.id),
      ]
    );
    flowingRef.current = flowing;

    const pipesFC: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: [
        ...nets.flatMap((n) =>
        n.pipes.map((p) => ({
          type: 'Feature' as const,
          geometry: { type: 'LineString' as const, coordinates: [p.from, p.to] },
          properties: { zoneId: p.zoneId, kind: p.kind, flowing: flowing.has(p.zoneId) ? 1 : 0 },
        }))
      ),
        ...parcelNets.flatMap((n) => n.pipes.map((p) => ({
          type: 'Feature' as const,
          geometry: { type: 'LineString' as const, coordinates: [p.from, p.to] },
          properties: { zoneId: p.zoneId, kind: p.kind, flowing: 0, parcel: 1 },
        }))),
      ],
    };
    const valvesFC: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: [
        ...nets.map((n) => ({
        type: 'Feature' as const,
        geometry: { type: 'Point' as const, coordinates: n.valve },
        properties: { zoneId: n.zone.id, open: flowing.has(n.zone.id) ? 1 : 0, parcel: 0 },
      })),
        ...parcelNets.map((n) => ({
          type: 'Feature' as const,
          geometry: { type: 'Point' as const, coordinates: n.valve },
          properties: { zoneId: n.id, open: flowing.has(n.id) ? 1 : 0, parcel: 1 },
        })),
      ],
    };
    const wetFC: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: farm.zones
        .filter((z) => flowing.has(z.id))
        .map((z) => ({ type: 'Feature' as const, geometry: z.polygon, properties: { zoneId: z.id } })),
    };

    try {
      (map.getSource(SRC.pipes) as GeoJSONSource | undefined)?.setData(pipesFC);
      (map.getSource(SRC.valves) as GeoJSONSource | undefined)?.setData(valvesFC);
      (map.getSource(SRC.wet) as GeoJSONSource | undefined)?.setData(wetFC);
      if (flowing.size === 0) (map.getSource(SRC.drops) as GeoJSONSource | undefined)?.setData(emptyFC());
    } catch (err) {
      console.warn('Irrigation layer update error:', err);
    }
  }, [map, farm.zones, parcels, emergencyStopActive]);

  // Show / hide with the active map mode.
  useEffect(() => {
    if (!map) return;
    for (const id of ALL_LAYERS) {
      if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none');
    }
  }, [map, visible]);

  // Water animation: flowing dashes, travelling droplets, wet shimmer.
  useEffect(() => {
    if (!map || !visible) return;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce) {
      if (map.getLayer(LAYER.wet)) map.setPaintProperty(LAYER.wet, 'fill-opacity', 0.3);
      return;
    }

    let raf = 0;
    let lastFrame = 0;
    let lastDash = -1;
    const tick = (now: number) => {
      raf = requestAnimationFrame(tick);
      if (now - lastFrame < 33) return; // ~30 fps is plenty for water
      lastFrame = now;
      const flowing = flowingRef.current;
      if (flowing.size === 0) return;
      const s = now / 1000;

      try {
        const step = Math.floor(now / DASH_STEP_MS) % DASH_SEQUENCE.length;
        if (step !== lastDash && map.getLayer(LAYER.flow)) {
          map.setPaintProperty(LAYER.flow, 'line-dasharray', DASH_SEQUENCE[step]);
          lastDash = step;
        }
        if (map.getLayer(LAYER.wet)) {
          const wave = 0.5 + 0.5 * Math.sin((2 * Math.PI * s) / WET_PERIOD);
          map.setPaintProperty(LAYER.wet, 'fill-opacity', 0.16 + wave * 0.24);
        }

        const features: GeoJSON.Feature[] = [];
        for (const net of netRef.current) {
          if (!flowing.has(net.zone.id)) continue;
          for (const p of net.pipes) {
            const n = Math.max(2, Math.round(p.lengthM / PARTICLE_SPACING));
            const base = (s * PARTICLE_SPEED) / p.lengthM;
            for (let k = 0; k < n; k++) {
              const f = (base + k / n) % 1;
              features.push({
                type: 'Feature',
                geometry: { type: 'Point', coordinates: lerp(p.from, p.to, f) },
                properties: {},
              });
            }
          }
        }
        (map.getSource(SRC.drops) as GeoJSONSource | undefined)?.setData({ type: 'FeatureCollection', features });
      } catch {
        /* map torn down mid-frame */
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [map, visible]);

  // Click a valve to open / close it.
  useEffect(() => {
    if (!map) return;
    const onClick = (e: MapLayerMouseEvent) => {
      const zoneId = e.features?.[0]?.properties?.zoneId as string | undefined;
      if (!zoneId) return;
      if (zoneId.startsWith('parcel-')) toggleParcelIrrigation(zoneId.replace(/^parcel-/, ''));
      else if (flowingRef.current.has(zoneId)) stopIrrigation(zoneId);
      else startIrrigation(zoneId);
    };
    const onEnter = () => (map.getCanvas().style.cursor = 'pointer');
    const onLeave = () => (map.getCanvas().style.cursor = '');
    map.on('click', LAYER.valves, onClick);
    map.on('mouseenter', LAYER.valves, onEnter);
    map.on('mouseleave', LAYER.valves, onLeave);
    return () => {
      map.off('click', LAYER.valves, onClick);
      map.off('mouseenter', LAYER.valves, onEnter);
      map.off('mouseleave', LAYER.valves, onLeave);
    };
  }, [map, startIrrigation, stopIrrigation, toggleParcelIrrigation]);

  return null;
}
