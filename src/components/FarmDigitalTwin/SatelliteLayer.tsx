'use client';

import { useEffect } from 'react';
import type { Map as MapLibreMap } from 'maplibre-gl';
import { TILE_PROVIDERS } from '@/lib/geo/providers';

interface SatelliteLayerProps {
  map: MapLibreMap | null;
  providerId: 'sentinel2Cloudless' | 'esriWorldImagery' | 'osmStandard';
  /** When false the satellite layer is hidden — the agri terrain base shows through */
  visible?: boolean;
}

export function SatelliteLayer({ map, providerId, visible = true }: SatelliteLayerProps) {
  // Add / swap the tile source when provider changes
  useEffect(() => {
    if (!map) return;

    const sourceId = 'qatra-satellite-source';
    const layerId  = 'qatra-satellite-layer';
    const provider = TILE_PROVIDERS[providerId] ?? TILE_PROVIDERS.esriWorldImagery;

    try {
      if (map.getLayer(layerId))   map.removeLayer(layerId);
      if (map.getSource(sourceId)) map.removeSource(sourceId);

      map.addSource(sourceId, {
        type: 'raster',
        tiles: provider.tiles,
        tileSize: provider.tileSize,
        attribution: provider.attribution,
        maxzoom: provider.maxZoom,
      });

      // Insert below any qatra-* overlay layers so our GIS data stays on top
      const existingLayers = map.getStyle().layers ?? [];
      const firstOverlay = existingLayers.find(
        (l) => l.id.startsWith('qatra-') && l.id !== layerId,
      );

      map.addLayer(
        {
          id: layerId,
          type: 'raster',
          source: sourceId,
          paint: {
            // Fully opaque: real satellite imagery of the farmland. 3D relief still comes
            // from the terrain DEM; the procedural base is only an offline fallback.
            'raster-opacity': visible ? 1 : 0,
            'raster-fade-duration': 400,
          },
        },
        firstOverlay?.id,
      );
    } catch (err) {
      console.warn('SatelliteLayer update error:', err);
    }
  }, [map, providerId]);   // only re-add when provider changes

  // Smoothly fade in/out without re-adding the layer
  useEffect(() => {
    if (!map) return;
    const layerId = 'qatra-satellite-layer';
    try {
      if (map.getLayer(layerId)) {
        map.setPaintProperty(layerId, 'raster-opacity', visible ? 1 : 0);
      }
    } catch (err) {
      console.warn('SatelliteLayer opacity update error:', err);
    }
  }, [map, visible]);

  return null;
}
