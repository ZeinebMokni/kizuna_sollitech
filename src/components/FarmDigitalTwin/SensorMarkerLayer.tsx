'use client';

import { useEffect, useRef } from 'react';
import maplibregl, { type Map as MapLibreMap, Marker } from 'maplibre-gl';
import { DEMO_DEVICES } from '@/lib/mockData';
import { useFarmStore } from '@/stores/useFarmStore';

interface SensorMarkerLayerProps {
  map: MapLibreMap | null;
  visible?: boolean;
}

export function SensorMarkerLayer({ map, visible = true }: SensorMarkerLayerProps) {
  const markersRef = useRef<Marker[]>([]);
  const { farm } = useFarmStore();

  useEffect(() => {
    if (!map) return;

    // Clean up existing markers
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    if (!visible) return;

    DEMO_DEVICES.forEach((device) => {
      const el = document.createElement('div');
      el.className = 'group relative cursor-pointer';

      const isAlert = device.status === 'alert';
      const isGateway = device.type === 'esp32_gateway';
      const isPump = device.type === 'irrigation_pump';
      const isSolar = device.type === 'solar_inverter';

      // Badge design
      el.innerHTML = `
        <div class="relative flex items-center justify-center">
          ${isAlert ? '<div class="absolute h-9 w-9 rounded-full bg-alert-500/30 animate-ping"></div>' : ''}
          ${isGateway ? '<div class="absolute h-10 w-10 rounded-full border border-brand-400/40 animate-spin"></div>' : ''}
          <div class="h-7 w-7 rounded-full flex items-center justify-center shadow-lg border-2 ${
            isAlert
              ? 'bg-alert-600 border-on-accent text-on-accent'
              : isGateway
              ? 'bg-accent-deep border-[#B3C796] text-[#E4EBD9]'
              : isPump
              ? 'bg-water-600 border-on-accent text-on-accent'
              : isSolar
              ? 'bg-sun-600 border-on-accent text-on-accent'
              : 'bg-accent border-on-accent text-on-accent'
          }">
            <span class="text-[10px] font-black">${
              isGateway ? 'GW' : isPump ? 'P' : isSolar ? 'PV' : 'S'
            }</span>
          </div>

          <!-- Tooltip on hover -->
          <div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block z-50 pointer-events-none">
            <div class="bg-surface border border-line p-2 rounded-xl shadow-2xl text-[11px] text-ink whitespace-nowrap min-w-[130px]">
              <p class="font-bold text-brand-400">${device.name}</p>
              <p class="text-[10px] text-earth-300 font-mono">${device.id}</p>
              <p class="text-[10px] text-earth-400 mt-1">Statut : <span class="${isAlert ? 'text-alert-400 font-bold' : 'text-brand-300'}">${device.status.toUpperCase()}</span></p>
            </div>
          </div>
        </div>
      `;

      try {
        const marker = new maplibregl.Marker({ element: el })
          .setLngLat(device.coordinates)
          .addTo(map);

        markersRef.current.push(marker);
      } catch (err) {
        console.warn('Marker addition error:', err);
      }
    });

    return () => {
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
    };
  }, [map, visible, farm.zones]);

  return null;
}
