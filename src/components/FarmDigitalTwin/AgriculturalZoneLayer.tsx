'use client';

import { useEffect } from 'react';
import type { Map as MapLibreMap, MapMouseEvent } from 'maplibre-gl';
import { useFarmStore } from '@/stores/useFarmStore';
import { FarmZone, MapLayerMode } from '@/types';
import { moistureColor } from '@/lib/geo/moisture';

interface AgriculturalZoneLayerProps {
  map: MapLibreMap | null;
}

export function AgriculturalZoneLayer({ map }: AgriculturalZoneLayerProps) {
  const { farm, selectedZoneId, selectZone, mapLayerMode } = useFarmStore();

  const getZoneFillColor = (zone: FarmZone, mode: MapLayerMode, isSelected: boolean) => {
    // Satellite (default), irrigation and moisture views: each zone is tinted by
    // its live soil moisture, from dry coral to deep water blue. While a zone is
    // irrigated, the simulation raises its moisture and the colour shifts to blue.
    if (mode === 'satellite' || mode === 'irrigation' || mode === 'moisture') {
      return moistureColor(zone.soilMoisturePercent, mode === 'moisture' ? 1.25 : isSelected ? 1.1 : 1);
    }

    if (zone.status === 'irrigating') {
      return 'rgba(50, 156, 150, 0.7)';
    }

    switch (mode) {
      case 'health':
        if (zone.status === 'healthy') return 'rgba(154, 180, 122, 0.55)';
        if (zone.status === 'warning') return 'rgba(239, 180, 71, 0.6)';
        return 'rgba(226, 116, 99, 0.7)';

      case 'temperature':
        if (zone.temperatureC > 34) return 'rgba(176, 62, 46, 0.65)';
        if (zone.temperatureC > 29) return 'rgba(212, 109, 63, 0.55)';
        return 'rgba(86, 184, 178, 0.55)';

      case 'crop':
        if (zone.cropType.includes('Olivier')) return 'rgba(170, 190, 100, 0.6)';
        if (zone.cropType.includes('Tomate')) return 'rgba(196, 72, 64, 0.6)';
        if (zone.cropType.includes('Grenadier')) return 'rgba(140, 70, 96, 0.6)';
        if (zone.cropType.includes('Piment')) return 'rgba(204, 78, 60, 0.6)';
        return 'rgba(124, 152, 91, 0.6)';

      case 'alerts':
        return zone.status === 'critical' ? 'rgba(204, 78, 60, 0.7)' : 'rgba(255, 255, 255, 0.1)';

      default:
        return 'rgba(124, 152, 91, 0.5)';
    }
  };

  useEffect(() => {
    if (!map) return;

    const sourceId = 'qatra-zones-source';
    const fillLayerId = 'qatra-zones-fill';
    const lineLayerId = 'qatra-zones-line';
    const labelLayerId = 'qatra-zones-labels';

    const features = farm.zones.map((zone) => {
      const isSelected = zone.id === selectedZoneId;
      const fillColor = getZoneFillColor(zone, mapLayerMode, isSelected);
      const strokeColor = isSelected ? '#FFFFFF' : zone.status === 'critical' ? '#D9573F' : '#9AB47A';
      const strokeWidth = isSelected ? 3.5 : 1.5;

      return {
        type: 'Feature' as const,
        geometry: zone.polygon,
        properties: {
          id: zone.id,
          name: zone.name,
          cropType: zone.cropType,
          areaHa: zone.areaHa,
          moisture: zone.soilMoisturePercent,
          status: zone.status,
          fillColor,
          strokeColor,
          strokeWidth,
          centerLng: zone.center[0],
          centerLat: zone.center[1],
        },
      };
    });

    const geojsonData: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features,
    };

    try {
      if (map.getSource(sourceId)) {
        (map.getSource(sourceId) as any).setData(geojsonData);
      } else {
        map.addSource(sourceId, {
          type: 'geojson',
          data: geojsonData,
        });

        map.addLayer({
          id: fillLayerId,
          type: 'fill',
          source: sourceId,
          paint: {
            'fill-color': ['get', 'fillColor'],
            'fill-opacity': mapLayerMode === 'ndvi' ? 0.0 : 0.85,
          },
        });

        map.addLayer({
          id: lineLayerId,
          type: 'line',
          source: sourceId,
          paint: {
            'line-color': ['get', 'strokeColor'],
            'line-width': ['get', 'strokeWidth'],
          },
        });
      }

      // Update fill colors dynamically
      if (map.getLayer(fillLayerId)) {
        map.setPaintProperty(fillLayerId, 'fill-color', ['get', 'fillColor']);
        map.setPaintProperty(fillLayerId, 'fill-opacity', mapLayerMode === 'ndvi' ? 0.0 : 0.85);
      }
      if (map.getLayer(lineLayerId)) {
        map.setPaintProperty(lineLayerId, 'line-color', ['get', 'strokeColor']);
        map.setPaintProperty(lineLayerId, 'line-width', ['get', 'strokeWidth']);
      }
    } catch (err) {
      console.warn('Agricultural zone layer update error:', err);
    }
  }, [map, farm.zones, selectedZoneId, mapLayerMode]);

  // Click on zone to select
  useEffect(() => {
    if (!map) return;

    const handleLayerClick = (e: MapMouseEvent) => {
      const features = map.queryRenderedFeatures(e.point, {
        layers: ['qatra-zones-fill'],
      });

      if (features.length > 0 && features[0].properties?.id) {
        selectZone(features[0].properties.id);
      }
    };

    map.on('click', 'qatra-zones-fill', handleLayerClick);
    return () => {
      map.off('click', 'qatra-zones-fill', handleLayerClick);
    };
  }, [map, selectZone]);

  return null;
}
