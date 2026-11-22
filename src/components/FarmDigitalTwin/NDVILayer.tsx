'use client';

import { useEffect, useRef } from 'react';
import type { Map as MapLibreMap, MapMouseEvent } from 'maplibre-gl';
import { useFarmStore } from '@/stores/useFarmStore';
import { getNDVIColor } from '@/lib/geo/ndvi';
import { useSentinelStore, farmGeometry } from '@/stores/useSentinelStore';
import { getNdviImage, getNdviStats, type NdviImage } from '@/lib/sentinel/client';

interface NDVILayerProps {
  map: MapLibreMap | null;
  visible: boolean;
  opacity: number;
}

const REAL_SOURCE = 'qatra-ndvi-real-source';
const REAL_LAYER = 'qatra-ndvi-real-layer';

export function NDVILayer({ map, visible, opacity }: NDVILayerProps) {
  const { farm, setSampledPixel } = useFarmStore();
  const { link, selectedDate, imageError, setLoadingImage, setImageError, setDateStats } = useSentinelStore();
  const imageCache = useRef<Map<string, NdviImage>>(new Map());

  // Real Sentinel-2 data when the backend is connected; otherwise the simulation below.
  const useReal = link === 'live' && !!selectedDate && !imageError;

  // ── Real NDVI image (Copernicus Sentinel-2 L2A, clouds masked, clipped to the farm) ──
  useEffect(() => {
    if (!map) return;
    const remove = () => {
      if (map.getLayer(REAL_LAYER)) map.removeLayer(REAL_LAYER);
      if (map.getSource(REAL_SOURCE)) map.removeSource(REAL_SOURCE);
    };
    if (!visible || !useReal || !selectedDate) {
      remove();
      return;
    }

    let cancelled = false;
    const show = (img: NdviImage) => {
      if (cancelled) return;
      const [minX, minY, maxX, maxY] = img.bbox;
      const coordinates: [[number, number], [number, number], [number, number], [number, number]] = [
        [minX, maxY],
        [maxX, maxY],
        [maxX, minY],
        [minX, minY],
      ];
      try {
        remove();
        map.addSource(REAL_SOURCE, { type: 'image', url: img.url, coordinates });
        const before = map.getStyle().layers?.find((l) => l.id.startsWith('qatra-zones') || l.id.startsWith('qatra-irr'))?.id;
        map.addLayer({ id: REAL_LAYER, type: 'raster', source: REAL_SOURCE, paint: { 'raster-opacity': opacity, 'raster-resampling': 'nearest' } }, before);
      } catch (err) {
        console.warn('Real NDVI layer error:', err);
      }
    };

    const geometry = farmGeometry();
    const cached = imageCache.current.get(selectedDate);
    if (cached) show(cached);
    else {
      setLoadingImage(true);
      getNdviImage(geometry, selectedDate)
        .then((img) => {
          imageCache.current.set(selectedDate, img);
          show(img);
        })
        .catch((err: Error) => {
          if (!cancelled) setImageError(err.message);
        })
        .finally(() => {
          if (!cancelled) setLoadingImage(false);
        });
    }
    getNdviStats(geometry, selectedDate)
      .then((s) => !cancelled && setDateStats(s))
      .catch(() => !cancelled && setDateStats(null));

    return () => {
      cancelled = true;
    };
  }, [map, visible, useReal, selectedDate, setLoadingImage, setImageError, setDateStats]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (map?.getLayer(REAL_LAYER)) map.setPaintProperty(REAL_LAYER, 'raster-opacity', opacity);
  }, [map, opacity]);

  useEffect(() => {
    const cache = imageCache.current;
    return () => cache.forEach((img) => URL.revokeObjectURL(img.url));
  }, []);

  // ── Simulated NDVI pixels (fallback when the backend is not connected) ──
  useEffect(() => {
    if (!map) return;

    const sourceId = 'qatra-ndvi-source';
    const fillLayerId = 'qatra-ndvi-fill-layer';
    const outlineLayerId = 'qatra-ndvi-outline-layer';

    if (!visible || useReal) {
      if (map.getLayer(fillLayerId)) map.removeLayer(fillLayerId);
      if (map.getLayer(outlineLayerId)) map.removeLayer(outlineLayerId);
      if (map.getSource(sourceId)) map.removeSource(sourceId);
      return;
    }

    // Generate high-density simulated Sentinel-2 10m raster pixels inside each parcel
    // to give an authentic remote sensing pixel grid rather than flat monochrome polygons
    const features: GeoJSON.Feature[] = [];

    farm.zones.forEach((zone) => {
      const baseNdvi = zone.ndviStats?.mean || 0.45;
      const coords = zone.polygon.coordinates[0];

      // Bounding box of zone
      let minLng = 180, maxLng = -180, minLat = 90, maxLat = -90;
      coords.forEach(([lng, lat]) => {
        if (lng < minLng) minLng = lng;
        if (lng > maxLng) maxLng = lng;
        if (lat < minLat) minLat = lat;
        if (lat > maxLat) maxLat = lat;
      });

      // 10m grid step (~0.00010 degrees)
      const stepLng = 0.00018;
      const stepLat = 0.00016;

      let pixelIndex = 0;
      for (let lng = minLng; lng <= maxLng; lng += stepLng) {
        for (let lat = minLat; lat <= maxLat; lat += stepLat) {
          // Synthetic spatial variation across pixel matrix (Sentinel-2 10m resolution)
          const seed = Math.sin(pixelIndex * 12.9898 + lng * 78.233 + lat * 37.719) * 43758.5453;
          const noise = (seed - Math.floor(seed)) * 0.16 - 0.08;
          const pixelNdvi = Math.max(0.08, Math.min(0.85, Number((baseNdvi + noise).toFixed(2))));
          const pixelColor = getNDVIColor(pixelNdvi);

          features.push({
            type: 'Feature',
            geometry: {
              type: 'Polygon',
              coordinates: [
                [
                  [lng, lat],
                  [lng + stepLng * 0.95, lat],
                  [lng + stepLng * 0.95, lat + stepLat * 0.95],
                  [lng, lat + stepLat * 0.95],
                  [lng, lat],
                ],
              ],
            },
            properties: {
              id: `${zone.id}-px-${pixelIndex}`,
              zoneName: zone.name,
              ndvi: pixelNdvi,
              color: pixelColor,
              nir: Number((0.25 + pixelNdvi * 0.35).toFixed(3)),
              red: Number((0.25 - pixelNdvi * 0.15).toFixed(3)),
            },
          });
          pixelIndex++;
        }
      }
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
            'fill-color': ['get', 'color'],
            'fill-opacity': opacity,
          },
        });

        map.addLayer({
          id: outlineLayerId,
          type: 'line',
          source: sourceId,
          paint: {
            'line-color': '#FFFFFF',
            'line-width': 0.5,
            'line-opacity': 0.35,
          },
        });
      }

      if (map.getLayer(fillLayerId)) {
        map.setPaintProperty(fillLayerId, 'fill-opacity', opacity);
      }
    } catch (err) {
      console.warn('NDVI raster layer update error:', err);
    }
  }, [map, visible, opacity, farm.zones, useReal]);

  // Click on pixel to inspect live values
  useEffect(() => {
    if (!map || !visible) return;

    const handleMapClick = (e: MapMouseEvent) => {
      const features = map.queryRenderedFeatures(e.point, {
        layers: ['qatra-ndvi-fill-layer'],
      });

      if (features.length > 0 && features[0].properties) {
        const props = features[0].properties;
        setSampledPixel({
          lng: Number(e.lngLat.lng.toFixed(5)),
          lat: Number(e.lngLat.lat.toFixed(5)),
          ndvi: props.ndvi,
          nir: props.nir,
          red: props.red,
          zoneName: props.zoneName,
        });
      }
    };

    map.on('click', handleMapClick);
    return () => {
      map.off('click', handleMapClick);
    };
  }, [map, visible, setSampledPixel]);

  return null;
}
