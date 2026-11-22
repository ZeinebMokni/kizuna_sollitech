'use client';

import { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import type { Map as MapLibreMap, GeoJSONSource, MapMouseEvent, MapTouchEvent, MapLayerMouseEvent } from 'maplibre-gl';
import { useParcelStore } from '@/stores/useParcelStore';
import { useFarmStore } from '@/stores/useFarmStore';
import { closeRing } from '@/lib/parcels/geometry';
import { findConflict } from '@/lib/parcels/conflicts';
import { detectFieldAt, FieldDetectionError } from '@/lib/parcels/detectField';
import type { LngLat } from '@/lib/parcels/types';

const SRC = { parcels: 'qatra-parcels', draft: 'qatra-parcel-draft' };
const LAYER = {
  fill: 'qatra-parcels-fill',
  line: 'qatra-parcels-line',
  selected: 'qatra-parcels-selected',
  draftFill: 'qatra-parcel-draft-fill',
  draftLine: 'qatra-parcel-draft-line',
};

const fc = (features: GeoJSON.Feature[] = []): GeoJSON.FeatureCollection => ({ type: 'FeatureCollection', features });

/**
 * Registered land parcels on the digital twin, plus the two ways to claim one:
 * "rectangle" (click-drag a box) and "auto" (click a field, its outline is
 * detected from the satellite image). Each parcel shows its unique ID.
 */
export function ParcelLayer({ map }: { map: MapLibreMap | null }) {
  const { parcels, mode, draft, selectedParcelId, currentOwner, setDraft, selectParcel, setDetecting, setDetectError } =
    useParcelStore();
  const { farm } = useFarmStore();
  const markersRef = useRef<Map<string, maplibregl.Marker>>(new Map());

  // Sources and layers
  useEffect(() => {
    if (!map) return;
    try {
      if (!map.getSource(SRC.parcels)) map.addSource(SRC.parcels, { type: 'geojson', data: fc() });
      if (!map.getSource(SRC.draft)) map.addSource(SRC.draft, { type: 'geojson', data: fc() });
      if (!map.getLayer(LAYER.fill)) {
        map.addLayer({ id: LAYER.fill, type: 'fill', source: SRC.parcels, paint: { 'fill-color': '#FFFFFF', 'fill-opacity': 0.14 } });
        map.addLayer({
          id: LAYER.line,
          type: 'line',
          source: SRC.parcels,
          paint: { 'line-color': '#FFFFFF', 'line-width': 2.2, 'line-dasharray': [3, 1.5], 'line-opacity': 0.95 },
        });
        map.addLayer({
          id: LAYER.selected,
          type: 'line',
          source: SRC.parcels,
          filter: ['==', ['get', 'id'], ''],
          paint: { 'line-color': '#3CCFE0', 'line-width': 4 },
        });
        map.addLayer({
          id: LAYER.draftFill,
          type: 'fill',
          source: SRC.draft,
          paint: { 'fill-color': ['case', ['==', ['get', 'conflict'], 1], '#E06A5A', '#3CCFE0'], 'fill-opacity': 0.28 },
        });
        map.addLayer({
          id: LAYER.draftLine,
          type: 'line',
          source: SRC.draft,
          paint: { 'line-color': ['case', ['==', ['get', 'conflict'], 1], '#E06A5A', '#FFFFFF'], 'line-width': 3 },
        });
      }
    } catch (err) {
      console.warn('Parcel layer setup error:', err);
    }
  }, [map]);

  // Parcel data + ID markers
  useEffect(() => {
    if (!map) return;
    (map.getSource(SRC.parcels) as GeoJSONSource | undefined)?.setData(
      fc(
        parcels.map((p) => ({
          type: 'Feature',
          geometry: { type: 'Polygon', coordinates: [closeRing(p.polygon)] },
          properties: { id: p.id },
        }))
      )
    );

    const markers = markersRef.current;
    const ids = new Set(parcels.map((p) => p.id));
    markers.forEach((m, id) => {
      if (!ids.has(id)) { m.remove(); markers.delete(id); }
    });
    for (const p of parcels) {
      if (markers.has(p.id)) continue;
      const el = document.createElement('button');
      el.type = 'button';
      el.className = 'qa-parcel-tag';
      el.innerHTML = `<span class="qa-parcel-tag-id">${p.id}</span><span class="qa-parcel-tag-meta">${p.areaHa.toLocaleString('fr-TN')} ha · ${p.ownerName.replace(/</g, '&lt;')}</span>`;
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        useParcelStore.getState().selectParcel(p.id);
      });
      markers.set(p.id, new maplibregl.Marker({ element: el }).setLngLat(p.center).addTo(map));
    }
  }, [map, parcels]);

  useEffect(() => () => {
    markersRef.current.forEach((m) => m.remove());
    markersRef.current.clear();
  }, []);

  // Selected outline
  useEffect(() => {
    if (!map || !map.getLayer(LAYER.selected)) return;
    map.setFilter(LAYER.selected, ['==', ['get', 'id'], selectedParcelId ?? '']);
    markersRef.current.forEach((m, id) => m.getElement().classList.toggle('is-selected', id === selectedParcelId));
  }, [map, selectedParcelId, parcels]);

  // Draft outline (blue = free land, coral = overlaps someone's land)
  useEffect(() => {
    if (!map) return;
    const src = map.getSource(SRC.draft) as GeoJSONSource | undefined;
    if (!draft || draft.polygon.length < 3) {
      src?.setData(fc());
      return;
    }
    const conflict = findConflict(draft.polygon, parcels, farm, currentOwner) ? 1 : 0;
    src?.setData(fc([{ type: 'Feature', geometry: { type: 'Polygon', coordinates: [closeRing(draft.polygon)] }, properties: { conflict } }]));
  }, [map, draft, parcels, farm, currentOwner]);

  // Click a parcel to select it
  useEffect(() => {
    if (!map) return;
    const onClick = (e: MapLayerMouseEvent) => {
      if (useParcelStore.getState().mode !== 'idle') return;
      const id = e.features?.[0]?.properties?.id as string | undefined;
      if (id) selectParcel(id);
    };
    map.on('click', LAYER.fill, onClick);
    return () => {
      map.off('click', LAYER.fill, onClick);
    };
  }, [map, selectParcel]);

  // Rectangle mode: click-drag a box on the map
  useEffect(() => {
    if (!map || mode !== 'rectangle') return;
    const canvas = map.getCanvas();
    map.dragPan.disable();
    map.boxZoom.disable();
    canvas.style.cursor = 'crosshair';
    let start: maplibregl.Point | null = null;

    const corners = (a: maplibregl.Point, b: maplibregl.Point): LngLat[] =>
      [
        [a.x, a.y],
        [b.x, a.y],
        [b.x, b.y],
        [a.x, b.y],
      ].map(([x, y]) => {
        const ll = map.unproject([x, y]);
        return [ll.lng, ll.lat] as LngLat;
      });

    const down = (e: MapMouseEvent | MapTouchEvent) => {
      start = e.point;
      setDraft(null);
    };
    const move = (e: MapMouseEvent | MapTouchEvent) => {
      if (!start) return;
      setDraft({ polygon: corners(start, e.point), source: 'rectangle' });
    };
    const up = (e: MapMouseEvent | MapTouchEvent) => {
      if (!start) return;
      const a = start;
      start = null;
      if (Math.abs(e.point.x - a.x) < 8 || Math.abs(e.point.y - a.y) < 8) {
        setDraft(null);
        return;
      }
      setDraft({ polygon: corners(a, e.point), source: 'rectangle', ready: true });
    };

    map.on('mousedown', down);
    map.on('mousemove', move);
    map.on('mouseup', up);
    map.on('touchstart', down);
    map.on('touchmove', move);
    map.on('touchend', up);
    return () => {
      map.off('mousedown', down);
      map.off('mousemove', move);
      map.off('mouseup', up);
      map.off('touchstart', down);
      map.off('touchmove', move);
      map.off('touchend', up);
      map.dragPan.enable();
      map.boxZoom.enable();
      canvas.style.cursor = '';
    };
  }, [map, mode, setDraft]);

  // Auto mode: click a field, detect its outline from the satellite image
  useEffect(() => {
    if (!map || mode !== 'auto') return;
    const canvas = map.getCanvas();
    canvas.style.cursor = 'crosshair';
    const click = async (e: MapMouseEvent) => {
      const store = useParcelStore.getState();
      if (store.detecting) return;
      setDetectError(null);
      setDraft(null);
      setDetecting(true);
      try {
        const polygon = await detectFieldAt([e.lngLat.lng, e.lngLat.lat]);
        if (useParcelStore.getState().mode === 'auto') setDraft({ polygon, source: 'auto', ready: true });
      } catch (err) {
        setDetectError(err instanceof FieldDetectionError ? err.message : 'La détection a échoué. Réessayez ou utilisez le rectangle.');
      } finally {
        setDetecting(false);
      }
    };
    map.on('click', click);
    return () => {
      map.off('click', click);
      canvas.style.cursor = '';
    };
  }, [map, mode, setDraft, setDetecting, setDetectError]);

  // Deep link: /farm/map?parcel=<ID> flies to that parcel
  useEffect(() => {
    if (!map) return;
    const id = new URLSearchParams(window.location.search).get('parcel');
    if (!id) return;
    const p = useParcelStore.getState().parcels.find((x) => x.id === id);
    if (!p) return;
    const xs = p.polygon.map((c) => c[0]);
    const ys = p.polygon.map((c) => c[1]);
    map.fitBounds(
      [
        [Math.min(...xs), Math.min(...ys)],
        [Math.max(...xs), Math.max(...ys)],
      ],
      { padding: 140, duration: 1200, maxZoom: 17.5 }
    );
    selectParcel(id);
  }, [map, selectParcel]);

  return null;
}
