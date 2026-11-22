'use client';

import { useEffect } from 'react';
import type { Map as MapLibreMap } from 'maplibre-gl';
import { useFarmStore } from '@/stores/useFarmStore';

interface ElevationLayerProps {
  map: MapLibreMap | null;
  visible: boolean;
  opacity: number;
}

export function ElevationLayer({ map, visible, opacity }: ElevationLayerProps) {
  const { farm } = useFarmStore();

  useEffect(() => {
    if (!map) return;

    const sourceId = 'qatra-elevation-farm-source';
    const fillLayerId = 'qatra-elevation-farm-fill';
    const contourLayerId = 'qatra-elevation-farm-contours';

    if (!visible) {
      if (map.getLayer(contourLayerId)) map.removeLayer(contourLayerId);
      if (map.getLayer(fillLayerId)) map.removeLayer(fillLayerId);
      if (map.getSource(sourceId)) map.removeSource(sourceId);
      return;
    }

    // Sidi Bouzid / Regueb plain elevation varies smoothly around 340m - 375m above sea level
    // We generate micro-topography contours inside the farm boundary
    const [centerLng, centerLat] = farm.centerCoordinates;

    // Create 5 elevation contour bands across the farm
    // Lowest: 342m (North-West depression/drainage) -> Highest: 368m (South-East crest)
    const contours: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: {
            type: 'Polygon',
            coordinates: [
              [
                [9.6957, 37.0008],
                [9.6992, 37.0043],
                [9.6977, 37.0043],
                [9.6957, 37.0008],
              ],
            ],
          },
          properties: { elevation: 342, label: '342 m (Point bas / Drainage)', color: '#56B8B2' }, // Blue
        },
        {
          type: 'Feature',
          geometry: {
            type: 'Polygon',
            coordinates: [
              [
                [9.6962, 36.9968],
                [9.7012, 37.0013],
                [9.6992, 37.0043],
                [9.6957, 37.0008],
                [9.6962, 36.9968],
              ],
            ],
          },
          properties: { elevation: 350, label: '350 m', color: '#9AB47A' }, // Green
        },
        {
          type: 'Feature',
          geometry: {
            type: 'Polygon',
            coordinates: [
              [
                [9.6997, 36.997],
                [9.7037, 37.0013],
                [9.7012, 37.0013],
                [9.6962, 36.9968],
                [9.6997, 36.997],
              ],
            ],
          },
          properties: { elevation: 358, label: '358 m (Pente moyenne 1.8%)', color: '#EFB447' }, // Yellow
        },
        {
          type: 'Feature',
          geometry: {
            type: 'Polygon',
            coordinates: [
              [
                [9.7032, 36.9972],
                [9.7062, 37.0038],
                [9.7037, 37.0013],
                [9.6997, 36.997],
                [9.7032, 36.9972],
              ],
            ],
          },
          properties: { elevation: 364, label: '364 m', color: '#E68660' }, // Orange
        },
        {
          type: 'Feature',
          geometry: {
            type: 'Polygon',
            coordinates: [
              [
                [9.7052, 36.9973],
                [9.7062, 37.0038],
                [9.7032, 36.9972],
                [9.7052, 36.9973],
              ],
            ],
          },
          properties: { elevation: 368, label: '368 m (Sommet / Crête réservoir)', color: '#E27463' }, // Red-orange
        },
      ],
    };

    try {
      if (map.getSource(sourceId)) {
        (map.getSource(sourceId) as any).setData(contours);
      } else {
        map.addSource(sourceId, {
          type: 'geojson',
          data: contours,
        });

        map.addLayer({
          id: fillLayerId,
          type: 'fill',
          source: sourceId,
          paint: {
            'fill-color': ['get', 'color'],
            'fill-opacity': opacity * 0.7,
          },
        });

        map.addLayer({
          id: contourLayerId,
          type: 'line',
          source: sourceId,
          paint: {
            'line-color': '#FFFFFF',
            'line-width': 1.5,
            'line-opacity': 0.8,
            'line-dasharray': [4, 2],
          },
        });
      }

      if (map.getLayer(fillLayerId)) {
        map.setPaintProperty(fillLayerId, 'fill-opacity', opacity * 0.7);
      }
    } catch (err) {
      console.warn('Elevation layer render error:', err);
    }
  }, [map, visible, opacity, farm.centerCoordinates]);

  return null;
}
