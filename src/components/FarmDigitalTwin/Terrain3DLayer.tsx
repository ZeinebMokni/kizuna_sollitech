'use client';

import { useEffect } from 'react';
import type { Map as MapLibreMap } from 'maplibre-gl';

interface Terrain3DLayerProps {
  map: MapLibreMap | null;
  enabled: boolean;
  exaggeration: number;
}

/**
 * Terrain3DLayer
 *
 * The DEM source ('terrain-dem') and initial terrain spec are baked into
 * the map's baseStyle in FarmMap.tsx (ESRI Terrain Base + AWS Terrarium).
 *
 * This component only:
 *  - Updates terrain exaggeration when the user moves the slider
 *  - Flattens (exaggeration → 0) when the user disables 3D mode
 *  - Adds an extra strong hillshade layer when 3D is explicitly enabled
 */
export function Terrain3DLayer({ map, enabled, exaggeration }: Terrain3DLayerProps) {
  useEffect(() => {
    if (!map) return;

    // The source id MUST match what is declared in baseStyle (FarmMap.tsx)
    const sourceId          = 'terrain-dem';
    const extraHillshadeId  = 'qatra-extra-hillshade';

    try {
      if (enabled) {
        // Adjust the exaggeration on the terrain already set in baseStyle
        if (typeof (map as any).setTerrain === 'function') {
          (map as any).setTerrain({ source: sourceId, exaggeration });
        }

        // Add an extra crisp hillshade when user has 3D on
        if (!map.getLayer(extraHillshadeId)) {
          map.addLayer({
            id: extraHillshadeId,
            type: 'hillshade',
            source: sourceId,
            paint: {
              'hillshade-exaggeration': 0.70,
              'hillshade-shadow-color': '#241A08',
              'hillshade-highlight-color': '#FEFDF5',
              'hillshade-accent-color': '#9A8248',
              'hillshade-illumination-direction': 310,
              'hillshade-illumination-anchor': 'map',
            },
          });
        }
      } else {
        // Flatten — keep DEM loaded for hillshade colors but no 3D mesh distortion
        if (typeof (map as any).setTerrain === 'function') {
          (map as any).setTerrain({ source: sourceId, exaggeration: 0.05 });
        }
        if (map.getLayer(extraHillshadeId)) {
          map.removeLayer(extraHillshadeId);
        }
      }
    } catch (err) {
      console.warn('[Terrain3DLayer] update error:', err);
    }
  }, [map, enabled, exaggeration]);

  return null;
}
