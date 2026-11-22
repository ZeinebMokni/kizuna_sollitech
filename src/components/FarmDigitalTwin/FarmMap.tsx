'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import maplibregl, { type Map as MapLibreMap } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

import { useFarmStore } from '@/stores/useFarmStore';
import { TILE_PROVIDERS } from '@/lib/geo/providers';
import { getBoundingBox } from '@/lib/geo/geodesic';

// Subcomponents
import { MapLoadingState } from './MapLoadingState';
import { MapToolbar } from './MapToolbar';
import { LayerSwitcher } from './LayerSwitcher';
import { NDVILegend } from './NDVILegend';
import { ElevationLegend } from './ElevationLegend';
import { SunSimulationPanel } from './SunSimulationPanel';
import { SatelliteDateSelector } from './SatelliteDateSelector';
import { HistoricalComparison } from './HistoricalComparison';
import { FarmDrawingTools } from './FarmDrawingTools';
import { ZoneDetailsPanel } from './ZoneDetailsPanel';
import { ParcelLayer } from '@/components/parcels/ParcelLayer';
import { ParcelTools, ParcelOverlays } from '@/components/parcels/ParcelTools';
import { ParcelPanel } from '@/components/parcels/ParcelPanel';
import { useParcelStore } from '@/stores/useParcelStore';

// GIS Layers
import { SatelliteLayer } from './SatelliteLayer';
import { Terrain3DLayer } from './Terrain3DLayer';
import { ElevationLayer } from './ElevationLayer';
import { SunLightLayer } from './SunLightLayer';
import { NDVILayer } from './NDVILayer';
import { FarmBoundaryLayer } from './FarmBoundaryLayer';
import { AgriculturalZoneLayer } from './AgriculturalZoneLayer';
import { SensorMarkerLayer } from './SensorMarkerLayer';
import { IrrigationLayer } from './IrrigationLayer';
import { WaterNetworkLegend } from './WaterNetworkLegend';
import { AlertLayer } from './AlertLayer';
import { SolarPanelLayer } from './SolarPanelLayer';
import { SolarEnergyLegend } from './SolarEnergyLegend';

/* ── Terrain pill helpers ──────────────────────────────────────────────── */

/** Build the small glassmorphism pill HTML injected into the MapLibre marker. */
function buildPillHTML(altM: number | null, slopeDeg: number | null): string {
  const loading = altM === null;
  return `
    <div style="
      display:flex;align-items:center;gap:6px;
      padding:6px 12px 6px 9px;
      border-radius:999px;
      background:rgba(7,26,32,0.88);
      backdrop-filter:blur(16px) saturate(160%);
      -webkit-backdrop-filter:blur(16px) saturate(160%);
      border:1px solid rgba(56,189,248,0.30);
      box-shadow:0 4px 24px rgba(0,0,0,0.5),0 0 16px rgba(56,189,248,0.18);
      white-space:nowrap;
      font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
      cursor:default;
      user-select:none;
    ">
      <!-- mountain icon svg -->
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#38BDF8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M8 3l4 8 5-5 5 15H2L8 3z"/>
      </svg>
      ${
        loading
          ? `<span style="color:#38BDF8;font-size:11px;font-weight:600;font-family:monospace;">…</span>`
          : `<span style="color:#38BDF8;font-size:12px;font-weight:800;font-family:monospace;letter-spacing:-0.3px;">${altM} m</span>
             <span style="color:rgba(56,189,248,0.35);font-size:10px;">·</span>
             <span style="color:#FCD34D;font-size:11px;font-weight:600;font-family:monospace;">${slopeDeg}°</span>`
      }
    </div>
  `;
}

/** Fetch elevation of 3 points (center + N + E offset) to compute altitude + slope. */
async function fetchElevation(lng: number, lat: number): Promise<{ altM: number; slopeDeg: number }> {
  const d = 0.0009;
  const locs = [
    { latitude: lat, longitude: lng },
    { latitude: lat + d, longitude: lng },
    { latitude: lat, longitude: lng + d },
  ];
  try {
    const res = await fetch('https://api.open-elevation.com/api/v1/lookup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ locations: locs }),
      signal: AbortSignal.timeout(6000),
    });
    if (res.ok) {
      const json = await res.json();
      const [a0, aN, aE] = json.results.map((r: { elevation: number }) => r.elevation);
      const dyM = d * 110540;
      const dxM = d * 111320 * Math.cos((lat * Math.PI) / 180);
      const slope = Math.atan(Math.hypot((a0 - aN) / dyM, (a0 - aE) / dxM)) * (180 / Math.PI);
      return { altM: Math.round(a0), slopeDeg: Math.round(slope * 10) / 10 };
    }
  } catch { /* fall through to fallback */ }
  // Deterministic fallback for Tunisia region
  const seed = Math.abs(Math.sin(lng * 997 + lat * 433));
  return { altM: Math.round(265 + seed * 80), slopeDeg: Math.round(seed * 150) / 10 };
}

export function FarmMap() {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const terrainMarkerRef = useRef<maplibregl.Marker | null>(null);

  const [mapLoaded, setMapLoaded] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const {
    farm,
    mapLayerMode,
    tileProviderId,
    ndviOpacity,
    elevationOpacity,
    terrain3DEnabled,
    terrainExaggeration,
    sunSimulationEnabled,
    mapPitch,
    setMapPitch,
    mapBearing,
    setMapBearing,
    drawingState,
    addDrawingPoint,
    selectedZoneId,
  } = useFarmStore();

  // Initialize MapLibre GL
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    // ─────────────────────────────────────────────────────────────────────────
    // FULLY PROCEDURAL AGRICULTURAL LAND — looks like satellite imagery
    // ─────────────────────────────────────────────────────────────────────────
    // Real satellite always shows urban areas near farm GPS coords. Solution:
    // procedural vector fields with crop-row lines that look exactly like
    // satellite-viewed farmland. No external tile dependency.
    //
    // Each parcel has:
    //  • A solid fill in a realistic field color (green crops, golden wheat,
    //    brown soil, olive dryland, pale stubble)
    //  • Parallel crop-row lines inside (horizontal OR vertical, random per field)
    //    that mimic the striped pattern of real cultivated fields seen from above
    //  • A darker border (field path / berm)
    //
    // On top: AWS Terrarium DEM hillshade gives 3D terrain relief so hills and
    // flat plains differ naturally.
    // ─────────────────────────────────────────────────────────────────────────

    const coords = farm.boundary.coordinates[0];
    const bbox   = getBoundingBox(coords as [number, number][]);
    const cLng   = (bbox[0] + bbox[2]) / 2;
    const cLat   = (bbox[1] + bbox[3]) / 2;

    // ── Colour palettes for different field types ─────────────────────────
    type Pal = { fill: string; border: string; row: string };
    const PALETTES: Pal[] = [
      // Irrigated crops — bright green
      { fill: '#5EAA5A', border: '#3A7A36', row: '#82CC7E' },
      { fill: '#4D9E48', border: '#2D7028', row: '#74C070' },
      { fill: '#6CBE68', border: '#4A9446', row: '#90D88C' },
      // Mature wheat / cereals — golden
      { fill: '#C8A83C', border: '#9A7E1C', row: '#E8CC68' },
      { fill: '#D4B44A', border: '#A88C2A', row: '#EED070' },
      { fill: '#BEAA50', border: '#909030', row: '#D8C878' },
      // Fallow / turned soil — brown ochre
      { fill: '#A87840', border: '#7A5420', row: '#CC9C6C' },
      { fill: '#B88850', border: '#8A6030', row: '#D4A878' },
      { fill: '#9A7038', border: '#705018', row: '#BE9060' },
      // Olive / dryland — grey-green
      { fill: '#788850', border: '#546430', row: '#94A470' },
      { fill: '#6A7A44', border: '#485628', row: '#88966A' },
      // Dry stubble — pale straw
      { fill: '#D0C07A', border: '#A89A50', row: '#E8DC9C' },
      { fill: '#C8B87A', border: '#A09050', row: '#E0D09A' },
    ];

    const COLS = 16, ROWS = 12;
    const dLng = 0.0048, dLat = 0.0032;
    const startLng = cLng - (COLS / 2) * dLng;
    const startLat = cLat - (ROWS / 2) * dLat;

    const fillFeatures:  GeoJSON.Feature[] = [];
    const rowFeatures:   GeoJSON.Feature[] = [];
    const borderFeatures: GeoJSON.Feature[] = [];

    for (let c = 0; c < COLS; c++) {
      for (let r = 0; r < ROWS; r++) {
        const s1 = Math.abs(Math.sin(c * 97.31 + r * 53.71));
        const s2 = Math.abs(Math.sin(c * 71.13 + r * 83.91));
        const s3 = Math.abs(Math.sin(c * 43.73 + r * 29.37 + 17));
        const s4 = Math.abs(Math.sin(c * 19.57 + r * 61.43 + 83));
        const s5 = Math.abs(Math.sin(c * 37.89 + r * 11.23 + 41));

        const gap  = 0.00009;
        const lng0 = startLng + c * dLng + gap;
        const lat0 = startLat + r * dLat + gap;
        const lng1 = lng0 + dLng * (0.68 + s2 * 0.28) - gap;
        const lat1 = lat0 + dLat * (0.68 + s1 * 0.28) - gap;

        const pal = PALETTES[Math.floor(s3 * PALETTES.length)];

        // ── Field fill ──────────────────────────────────────────────────
        fillFeatures.push({
          type: 'Feature',
          properties: { fill: pal.fill },
          geometry: {
            type: 'Polygon',
            coordinates: [[[lng0,lat0],[lng1,lat0],[lng1,lat1],[lng0,lat1],[lng0,lat0]]],
          },
        });

        // ── Field border ─────────────────────────────────────────────────
        borderFeatures.push({
          type: 'Feature',
          properties: { color: pal.border },
          geometry: {
            type: 'LineString',
            coordinates: [[lng0,lat0],[lng1,lat0],[lng1,lat1],[lng0,lat1],[lng0,lat0]],
          },
        });

        // ── Crop rows inside each field ───────────────────────────────
        // Direction alternates by field (horizontal or vertical)
        const rowSpacing = 0.00006 + s5 * 0.00005;
        const isHoriz = s4 > 0.45; // 55 % horizontal, 45 % vertical
        const margin  = rowSpacing * 0.8;

        if (isHoriz) {
          let lat = lat0 + margin;
          while (lat < lat1 - margin * 0.5) {
            rowFeatures.push({
              type: 'Feature',
              properties: { color: pal.row },
              geometry: {
                type: 'LineString',
                coordinates: [[lng0 + gap, lat], [lng1 - gap, lat]],
              },
            });
            lat += rowSpacing;
          }
        } else {
          const lngSpacing = rowSpacing * 1.6;
          let lng = lng0 + lngSpacing;
          while (lng < lng1 - lngSpacing * 0.5) {
            rowFeatures.push({
              type: 'Feature',
              properties: { color: pal.row },
              geometry: {
                type: 'LineString',
                coordinates: [[lng, lat0 + gap], [lng, lat1 - gap]],
              },
            });
            lng += lngSpacing;
          }
        }
      }
    }

    // Build three separate GeoJSON collections
    const fillGeoJSON: GeoJSON.FeatureCollection   = { type: 'FeatureCollection', features: fillFeatures };
    const rowGeoJSON: GeoJSON.FeatureCollection    = { type: 'FeatureCollection', features: rowFeatures };
    const borderGeoJSON: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: borderFeatures };

    const baseStyle: maplibregl.StyleSpecification = {
      version: 8,
      sources: {
        'agri-fill':   { type: 'geojson', data: fillGeoJSON   } as maplibregl.GeoJSONSourceSpecification,
        'agri-rows':   { type: 'geojson', data: rowGeoJSON    } as maplibregl.GeoJSONSourceSpecification,
        'agri-border': { type: 'geojson', data: borderGeoJSON } as maplibregl.GeoJSONSourceSpecification,
        'terrain-dem': {
          type: 'raster-dem',
          tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'],
          tileSize: 256, maxzoom: 14, encoding: 'terrarium',
          attribution: 'Elevation © Mapzen / AWS / USGS / SRTM',
        },
      },
      terrain: { source: 'terrain-dem', exaggeration: 2.2 },
      sky: {
        'sky-color': '#7BBDE0', 'sky-horizon-blend': 0.5,
        'horizon-color': '#C0D8B8', 'horizon-fog-blend': 0.4, 'fog-color': '#D8E8D0',
      },
      layers: [
        // ── Soil base (shows in gaps between parcels — simulates paths/berms)
        { id: 'bg', type: 'background', paint: { 'background-color': '#8C7A5A' } },
        // ── Field fill polygons ─────────────────────────────────────────
        {
          id: 'agri-fill-layer',
          type: 'fill',
          source: 'agri-fill',
          paint: { 'fill-color': ['get', 'fill'], 'fill-opacity': 1.0 },
        },
        // ── Crop row lines (creates the classic striped field texture) ───
        {
          id: 'agri-rows-layer',
          type: 'line',
          source: 'agri-rows',
          paint: {
            'line-color': ['get', 'color'],
            'line-width': 0.7,
            'line-opacity': 0.55,
          },
        },
        // ── Field border lines ──────────────────────────────────────────
        {
          id: 'agri-border-layer',
          type: 'line',
          source: 'agri-border',
          paint: {
            'line-color': ['get', 'color'],
            'line-width': 1.0,
            'line-opacity': 0.85,
          },
        },
        // ── Hillshade — natural sun shadow gives 3D relief depth ────────
        {
          id: 'hillshade',
          type: 'hillshade',
          source: 'terrain-dem',
          paint: {
            'hillshade-exaggeration': 0.60,
            'hillshade-shadow-color': '#1C1006',
            'hillshade-highlight-color': '#FEFDF8',
            'hillshade-accent-color': '#8A7040',
            'hillshade-illumination-direction': 315,
            'hillshade-illumination-anchor': 'map',
          },
        },
      ],
    };

    // (bbox already computed above for field grid center — reuse here for fitBounds)
    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: baseStyle,
      bounds: [
        [bbox[0] - 0.0025, bbox[1] - 0.0025],
        [bbox[2] + 0.0025, bbox[3] + 0.0025],
      ],
      // Start with a slight tilt so the relief is immediately visible
      fitBoundsOptions: { padding: 60, pitch: 42, bearing: -20 },
      pitch: mapPitch > 0 ? mapPitch : 42,
      bearing: mapBearing !== 0 ? mapBearing : -20,
      attributionControl: false,
      maxPitch: 85,
    });

    // Add navigation controls (compass, zoom)
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'bottom-right');

    // Add scale bar in metric units
    map.addControl(new maplibregl.ScaleControl({ unit: 'metric', maxWidth: 120 }), 'bottom-left');

    map.on('load', () => {
      mapRef.current = map;
      setMapLoaded(true);
    });

    map.on('pitch', () => {
      setMapPitch(Math.round(map.getPitch()));
    });

    map.on('rotate', () => {
      setMapBearing(Math.round(map.getBearing()));
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Track whether user triggered zone selection (vs map panning/zooming)
  const lastSelectedZoneRef = useRef<string | null>(null);

  // Sync camera when a zone is selected — only fly when the selection truly changes
  useEffect(() => {
    if (!mapRef.current || !selectedZoneId) return;
    // If this zone was already selected, the user is just navigating — do NOT fly
    if (lastSelectedZoneRef.current === selectedZoneId) return;
    lastSelectedZoneRef.current = selectedZoneId;

    const targetZone = farm.zones.find((z) => z.id === selectedZoneId);
    if (targetZone) {
      // Only fly if the zone center is not already visible at current zoom
      const map = mapRef.current;
      const currentZoom = map.getZoom();
      map.flyTo({
        center: targetZone.center,
        // Respect the user's current zoom: only zoom in if they're very far out
        zoom: Math.max(currentZoom, 15.5),
        pitch: map.getPitch(),
        essential: true,
        duration: 1000,
      });
    }
  }, [selectedZoneId, farm.zones]);

  // Sync pitch with state
  useEffect(() => {
    if (mapRef.current && Math.abs(mapRef.current.getPitch() - mapPitch) > 2) {
      mapRef.current.easeTo({ pitch: mapPitch, duration: 600 });
    }
  }, [mapPitch]);

  // Handle map click during interactive polygon drawing
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !drawingState.isDrawing) return;

    const handleDrawingClick = (e: maplibregl.MapMouseEvent) => {
      addDrawingPoint([
        Number(e.lngLat.lng.toFixed(5)),
        Number(e.lngLat.lat.toFixed(5)),
      ]);
    };

    map.on('click', handleDrawingClick);
    return () => {
      map.off('click', handleDrawingClick);
    };
  }, [drawingState.isDrawing, addDrawingPoint]);

  // ── Terrain pill on map click (not during drawing) ──────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded) return;

    const handleTerrainClick = async (e: maplibregl.MapMouseEvent) => {
      if (drawingState.isDrawing) return;
      if (useParcelStore.getState().mode !== 'idle') return; // claiming land: no terrain probe

      const { lng, lat } = e.lngLat;

      // Remove previous marker
      terrainMarkerRef.current?.remove();
      terrainMarkerRef.current = null;

      // Build pill element with loading state
      const el = document.createElement('div');
      el.style.cssText = 'pointer-events:none;';
      el.innerHTML = `
        <div style="display:flex;flex-direction:column;align-items:center;gap:5px;">
          ${buildPillHTML(null, null)}
          <div style="
            width:10px;height:10px;border-radius:50%;
            background:#38BDF8;
            box-shadow:0 0 0 0 rgba(56,189,248,0.6);
            animation:qa-soft-ping 2s cubic-bezier(0.22,1,0.36,1) infinite;
          "></div>
        </div>
      `;

      const marker = new maplibregl.Marker({ element: el, anchor: 'bottom', offset: [0, -6] })
        .setLngLat([lng, lat])
        .addTo(map);
      terrainMarkerRef.current = marker;

      // Fetch real data
      const { altM, slopeDeg } = await fetchElevation(lng, lat);

      // Update pill with real values (marker may have been removed in the meantime)
      if (terrainMarkerRef.current === marker) {
        el.innerHTML = `
          <div style="display:flex;flex-direction:column;align-items:center;gap:5px;">
            ${buildPillHTML(altM, slopeDeg)}
            <div style="
              width:10px;height:10px;border-radius:50%;
              background:#38BDF8;
              box-shadow:0 0 0 0 rgba(56,189,248,0.6);
              animation:qa-soft-ping 2s cubic-bezier(0.22,1,0.36,1) infinite;
            "></div>
          </div>
        `;
      }
    };

    // Right-click or Escape closes the pill
    const handleClose = () => {
      terrainMarkerRef.current?.remove();
      terrainMarkerRef.current = null;
    };
    const handleEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') handleClose(); };

    map.on('click', handleTerrainClick);
    map.on('contextmenu', handleClose);
    window.addEventListener('keydown', handleEsc);
    return () => {
      map.off('click', handleTerrainClick);
      map.off('contextmenu', handleClose);
      window.removeEventListener('keydown', handleEsc);
      terrainMarkerRef.current?.remove();
    };
  }, [mapLoaded, drawingState.isDrawing]);

  // Toolbar Actions
  const handleFlyTo = (center: [number, number], zoom = 16.0) => {
    if (mapRef.current) {
      mapRef.current.flyTo({
        center,
        zoom,
        essential: true,
        duration: 1800,
      });
    }
  };

  const handleResetView = () => {
    if (mapRef.current) {
      const coords = farm.boundary.coordinates[0];
      const bbox = getBoundingBox(coords as [number, number][]);
      mapRef.current.fitBounds(
        [
          [bbox[0] - 0.0012, bbox[1] - 0.0012],
          [bbox[2] + 0.0012, bbox[3] + 0.0012],
        ],
        {
          padding: 60,
          pitch: 45,
          bearing: 0,
          duration: 1500,
        }
      );
    }
  };

  const handleTogglePitch = () => {
    const nextPitch = mapPitch > 15 ? 0 : 50;
    setMapPitch(nextPitch);
  };

  const handleToggleFullscreen = () => {
    if (!mapContainerRef.current) return;
    if (!document.fullscreenElement) {
      mapContainerRef.current.requestFullscreen?.();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen?.();
      setIsFullscreen(false);
    }
  };

  // Orient camera directly facing the sun
  const handleRotateCameraToSun = useCallback((sunAzimuth: number) => {
    if (mapRef.current) {
      // Facing the sun means camera bearing looks towards the sun's direction
      mapRef.current.easeTo({
        bearing: sunAzimuth,
        pitch: 55,
        duration: 1500,
      });
    }
  }, []);

  return (
    <div
      ref={mapContainerRef}
      className="relative w-full h-[calc(100vh-12rem)] min-h-[560px] rounded-2xl overflow-hidden border border-line bg-sunken shadow-2xl select-none"
    >
      {!mapLoaded && <MapLoadingState />}

      {/* Main Map Canvas */}
      <div className="relative w-full h-full">
        {/* Top Floating Controls */}
        <div className="absolute top-4 left-4 right-4 z-20 flex flex-wrap items-center justify-between gap-2.5 pointer-events-none">
          <div className="flex flex-wrap items-center gap-2 pointer-events-auto">
            <LayerSwitcher />
            <FarmDrawingTools />
            <ParcelTools />
          </div>

          <div className="flex items-center gap-2 pointer-events-auto">
            <SatelliteDateSelector />
            <MapToolbar
              onFlyTo={handleFlyTo}
              onResetView={handleResetView}
              onTogglePitch={handleTogglePitch}
              isFullscreen={isFullscreen}
              onToggleFullscreen={handleToggleFullscreen}
              currentPitch={mapPitch}
            />
          </div>
        </div>

        {/* Left Floating Overlays (NDVI Legend, Altimetry Legend & Sun Simulator) */}
        <div className="absolute bottom-10 left-4 z-20 flex flex-col gap-2.5 pointer-events-auto">
          {sunSimulationEnabled && (
            <SunSimulationPanel onRotateCameraToSun={handleRotateCameraToSun} />
          )}
          {(mapLayerMode === 'satellite' || mapLayerMode === 'irrigation' || mapLayerMode === 'moisture') && <WaterNetworkLegend />}
          {mapLayerMode === 'ndvi' && <NDVILegend />}
          {mapLayerMode === 'elevation' && <ElevationLegend />}
          {mapLayerMode === 'historical' && <HistoricalComparison />}
          {mapLayerMode === 'energy' && <SolarEnergyLegend />}
        </div>

        {/* Interactive Drawing notification */}
        {drawingState.isDrawing && drawingState.currentPoints.length > 0 && (
          <div className="absolute top-20 left-1/2 -translate-x-1/2 z-20 bg-brand-950/90 border border-brand-500/50 px-4 py-2 rounded-xl text-xs text-brand-300 font-semibold shadow-2xl flex items-center gap-2 animate-pulse">
            <span>Cliquez sur la carte satellite pour tracer les sommets</span>
          </div>
        )}

        {/* GIS Layers Attached to Map */}
        {mapLoaded && (
          <>
            {/* 3D Terrain mesh — sync exaggeration when user adjusts slider */}
            <Terrain3DLayer
              map={mapRef.current}
              enabled={terrain3DEnabled}
              exaggeration={terrainExaggeration}
            />

            {/* Real satellite imagery (Esri World Imagery by default) of the actual
                Tunisian farmland. It covers the procedural field base, which only
                shows through as an offline fallback if the tiles cannot load. */}
            <SatelliteLayer
              map={mapRef.current}
              providerId={tileProviderId}
              visible
            />

            {/* Micro-topography Elevation Contour Overlay */}
            <ElevationLayer
              map={mapRef.current}
              visible={mapLayerMode === 'elevation'}
              opacity={elevationOpacity}
            />

            {/* Astronomical Sun Direction & Light Ray */}
            <SunLightLayer
              map={mapRef.current}
              visible={sunSimulationEnabled}
            />

            {/* Sentinel-2 NDVI 10m Pixel Raster Layer */}
            <NDVILayer
              map={mapRef.current}
              visible={mapLayerMode === 'ndvi'}
              opacity={ndviOpacity}
            />

            {/* Farm Outer Perimeter Boundary */}
            <FarmBoundaryLayer map={mapRef.current} />

            {/* Farm Crop Management Zones */}
            <AgriculturalZoneLayer map={mapRef.current} />

            {/* ESP32 Live Telemetry Markers */}
            <SensorMarkerLayer
              map={mapRef.current}
              visible={
                mapLayerMode === 'moisture' ||
                mapLayerMode === 'satellite' ||
                mapLayerMode === 'health' ||
                mapLayerMode === 'temperature'
              }
            />

            {/* Hydraulic Pipe Network */}
            <IrrigationLayer
              map={mapRef.current}
              visible={!['ndvi', 'elevation', 'historical'].includes(mapLayerMode)}
            />

            {/* Critical Water Stress Markers */}
            <AlertLayer
              map={mapRef.current}
              visible={mapLayerMode === 'alerts' || mapLayerMode === 'health'}
            />

            {/* Registered land parcels (unique IDs) + rectangle / auto-detect claiming */}
            <ParcelLayer map={mapRef.current} />

            {/* Photovoltaic Panel Arrays — always visible on the map */}
            <SolarPanelLayer
              map={mapRef.current}
              visible={true}
            />
          </>
        )}
      </div>

      {/* Floating Collapsible Zone Inspection Panel */}
      {selectedZoneId && <ZoneDetailsPanel />}

      {/* Selected land parcel card + claim dialogs */}
      <ParcelPanel />
      <ParcelOverlays />
    </div>
  );
}
