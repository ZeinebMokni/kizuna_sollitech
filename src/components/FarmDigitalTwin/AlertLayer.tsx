'use client';

import { useEffect, useRef } from 'react';
import maplibregl, { type Map as MapLibreMap, Marker } from 'maplibre-gl';
import { useFarmStore } from '@/stores/useFarmStore';

interface AlertLayerProps {
  map: MapLibreMap | null;
  visible?: boolean;
}

export function AlertLayer({ map, visible = true }: AlertLayerProps) {
  const markersRef = useRef<Marker[]>([]);
  const { farm, selectZone } = useFarmStore();

  useEffect(() => {
    if (!map) return;

    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    if (!visible) return;

    const criticalZones = farm.zones.filter((z) => z.status === 'critical');

    criticalZones.forEach((zone) => {
      const el = document.createElement('div');
      el.className = 'cursor-pointer';
      el.innerHTML = `
        <div class="relative flex items-center justify-center">
          <div class="absolute h-10 w-10 rounded-full bg-alert-500/40 animate-ping"></div>
          <div class="h-6 w-6 rounded-full bg-alert-600 border-2 border-on-accent flex items-center justify-center shadow-2xl text-on-accent font-black text-xs">
            !
          </div>
        </div>
      `;

      el.addEventListener('click', () => {
        selectZone(zone.id);
      });

      try {
        const marker = new maplibregl.Marker({ element: el })
          .setLngLat(zone.center)
          .addTo(map);

        markersRef.current.push(marker);
      } catch (err) {
        console.warn('Alert marker error:', err);
      }
    });

    return () => {
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
    };
  }, [map, visible, farm.zones, selectZone]);

  return null;
}
