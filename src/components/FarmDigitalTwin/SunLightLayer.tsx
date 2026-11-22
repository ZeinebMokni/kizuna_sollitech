'use client';

import { useEffect, useRef } from 'react';
import maplibregl, { type Map as MapLibreMap, Marker } from 'maplibre-gl';
import { useFarmStore } from '@/stores/useFarmStore';
import { calculateSunPosition } from '@/lib/geo/sun';

interface SunLightLayerProps {
  map: MapLibreMap | null;
  visible?: boolean;
}

export function SunLightLayer({ map, visible = true }: SunLightLayerProps) {
  const { farm, sunSimulationEnabled } = useFarmStore();
  const sunMarkerRef = useRef<Marker | null>(null);

  useEffect(() => {
    if (!map) return;

    const sourceId = 'qatra-sun-beam-source';
    const lineLayerId = 'qatra-sun-beam-line';
    const fillLayerId = 'qatra-sun-beam-fill';

    if (!visible || !sunSimulationEnabled) {
      if (sunMarkerRef.current) {
        sunMarkerRef.current.remove();
        sunMarkerRef.current = null;
      }
      if (map.getLayer(lineLayerId)) map.removeLayer(lineLayerId);
      if (map.getLayer(fillLayerId)) map.removeLayer(fillLayerId);
      if (map.getSource(sourceId)) map.removeSource(sourceId);
      return;
    }

    const [centerLng, centerLat] = farm.centerCoordinates;
    const now = new Date();
    const sunPos = calculateSunPosition(now, centerLat, centerLng);

    // Compute virtual sun source position placed on a distant circle around the farm
    // Azimuth in degrees from North
    const distanceKm = 1.2; // 1.2km radius for visible ray in farm view
    // 1 deg lat ~ 111km, 1 deg lng ~ 111 * cos(lat)
    const latOffset = (distanceKm / 111) * Math.cos(sunPos.azimuth * (Math.PI / 180));
    const lngOffset = (distanceKm / (111 * Math.cos(centerLat * (Math.PI / 180)))) * Math.sin(sunPos.azimuth * (Math.PI / 180));

    const sunSourceLng = centerLng + lngOffset;
    const sunSourceLat = centerLat + latOffset;

    // Create a cone of light spanning across the farm
    const beamAngleSpread = 25 * (Math.PI / 180); // spread cone
    const centerAzimuthRad = sunPos.azimuth * (Math.PI / 180);

    const leftLngOffset = ((distanceKm * 1.5) / (111 * Math.cos(centerLat * (Math.PI / 180)))) * Math.sin(centerAzimuthRad - beamAngleSpread);
    const leftLatOffset = ((distanceKm * 1.5) / 111) * Math.cos(centerAzimuthRad - beamAngleSpread);

    const rightLngOffset = ((distanceKm * 1.5) / (111 * Math.cos(centerLat * (Math.PI / 180)))) * Math.sin(centerAzimuthRad + beamAngleSpread);
    const rightLatOffset = ((distanceKm * 1.5) / 111) * Math.cos(centerAzimuthRad + beamAngleSpread);

    // Light cone polygon
    const lightPolygon: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: {
            type: 'Polygon',
            coordinates: [
              [
                [sunSourceLng, sunSourceLat],
                [centerLng - leftLngOffset, centerLat - leftLatOffset],
                [centerLng - rightLngOffset, centerLat - rightLatOffset],
                [sunSourceLng, sunSourceLat],
              ],
            ],
          },
          properties: {
            isDaylight: sunPos.isDaylight ? 1 : 0,
            altitude: sunPos.altitude,
          },
        },
        // Central ray line
        {
          type: 'Feature',
          geometry: {
            type: 'LineString',
            coordinates: [
              [sunSourceLng, sunSourceLat],
              [centerLng, centerLat],
            ],
          },
          properties: {
            type: 'ray',
          },
        },
      ],
    };

    try {
      if (map.getSource(sourceId)) {
        (map.getSource(sourceId) as any).setData(lightPolygon);
      } else {
        map.addSource(sourceId, {
          type: 'geojson',
          data: lightPolygon,
        });

        // Warm solar cone of light
        map.addLayer({
          id: fillLayerId,
          type: 'fill',
          source: sourceId,
          filter: ['==', '$type', 'Polygon'],
          paint: {
            'fill-color': sunPos.isDaylight ? '#E39A26' : '#56B8B2',
            'fill-opacity': sunPos.isDaylight ? 0.08 : 0.04,
          },
        });

        // Golden luminous sunlight beam line
        map.addLayer({
          id: lineLayerId,
          type: 'line',
          source: sourceId,
          filter: ['==', '$type', 'LineString'],
          paint: {
            'line-color': sunPos.isDaylight ? '#F4C76A' : '#7FCDC8',
            'line-width': 2.5,
            'line-dasharray': [3, 2],
            'line-opacity': 0.75,
          },
        });
      }

      // Add Glowing Sun Billboard Marker at the source coordinates
      if (!sunMarkerRef.current) {
        const el = document.createElement('div');
        el.className = 'sun-source-marker pointer-events-none';
        el.innerHTML = `
          <div class="relative flex items-center justify-center -translate-x-1/2 -translate-y-1/2">
            <div class="absolute h-12 w-12 rounded-full bg-sun-400/30 animate-ping"></div>
            <div class="absolute h-16 w-16 rounded-full bg-sun-500/10 animate-pulse"></div>
            <div class="h-8 w-8 rounded-full bg-gradient-to-tr from-[#E39A26] to-[#F8D88E] border-2 border-on-accent shadow-[0_0_20px_#E39A26] flex items-center justify-center">
              <span class="text-[12px]">☀️</span>
            </div>
            <div class="absolute top-full mt-1 px-2 py-0.5 rounded-full bg-surface/90 border border-sun-500/50 text-[9px] font-bold text-sun-400 shadow-sm font-mono whitespace-nowrap">
              Soleil (${sunPos.altitude > 0 ? '+' : ''}${sunPos.altitude}°)
            </div>
          </div>
        `;

        sunMarkerRef.current = new maplibregl.Marker({ element: el })
          .setLngLat([sunSourceLng, sunSourceLat])
          .addTo(map);
      } else {
        sunMarkerRef.current.setLngLat([sunSourceLng, sunSourceLat]);
      }
    } catch (err) {
      console.warn('Sun light layer render error:', err);
    }

    return () => {
      if (sunMarkerRef.current) {
        sunMarkerRef.current.remove();
        sunMarkerRef.current = null;
      }
    };
  }, [map, visible, sunSimulationEnabled, farm.centerCoordinates]);

  return null;
}
