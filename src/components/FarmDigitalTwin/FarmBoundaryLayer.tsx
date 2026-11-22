'use client';

import { useEffect } from 'react';
import type { Map as MapLibreMap } from 'maplibre-gl';
import { useFarmStore } from '@/stores/useFarmStore';

interface FarmBoundaryLayerProps {
  map: MapLibreMap | null;
}

export function FarmBoundaryLayer({ map }: FarmBoundaryLayerProps) {
  const { farm } = useFarmStore();

  useEffect(() => {
    if (!map || !farm.boundary) return;

    const sourceId = 'qatra-farm-boundary-source';
    const lineLayerId = 'qatra-farm-boundary-line';
    const fillLayerId = 'qatra-farm-boundary-fill';

    const geojsonData: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: farm.boundary,
          properties: {
            name: farm.name,
            areaHa: farm.totalAreaHa,
          },
        },
      ],
    };

    try {
      if (map.getSource(sourceId)) {
        (map.getSource(sourceId) as any).setData(geojsonData);
      } else {
        map.addSource(sourceId, {
          type: 'geojson',
          data: geojsonData,
        });

        // Subtle shaded interior
        map.addLayer({
          id: fillLayerId,
          type: 'fill',
          source: sourceId,
          paint: {
            'fill-color': '#3A4C2A',
            'fill-opacity': 0.08,
          },
        });

        // Crisp dashed perimeter line
        map.addLayer({
          id: lineLayerId,
          type: 'line',
          source: sourceId,
          paint: {
            'line-color': '#F2E3C6',
            'line-width': 2.5,
            'line-dasharray': [4, 3],
          },
        });
      }
    } catch (err) {
      console.warn('Farm boundary layer update error:', err);
    }
  }, [map, farm.boundary, farm.name, farm.totalAreaHa]);

  return null;
}
