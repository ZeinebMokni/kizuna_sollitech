'use client';

import { useEffect, useRef } from 'react';
import maplibregl, { type Map as MapLibreMap, Marker } from 'maplibre-gl';
import { DEMO_DEVICES } from '@/lib/mockData';
import type { Device } from '@/types';

/* ─────────────────────────── config ───────────────────────────────────────
 * SOLAR_PANELS   positions of each panel array on the farm (lng, lat)
 *                We generate a small grid of panels near the central inverter.
 * PANEL_ROWS / COLS  how many panel cells to draw inside each SVG marker
 * ────────────────────────────────────────────────────────────────────────── */

interface SolarPanelLayerProps {
  map: MapLibreMap | null;
  visible?: boolean;
}

/** Extended panel-array definition used to generate markers. */
interface PanelArray {
  id: string;
  coordinates: [number, number];
  capacityKw: number;
  currentKw: number;
  status: 'online' | 'offline' | 'warning';
  label: string;
  panels: number; // physical panel count
}

/** Build the list of panel-array positions from DEMO_DEVICES + a few extras. */
function buildPanelArrays(): PanelArray[] {
  const inverter = DEMO_DEVICES.find((d: Device) => d.type === 'solar_inverter');
  const pvKw = inverter ? (inverter.readings.pvGenerationKw as number) : 14.8;
  const status = (inverter?.status ?? 'online') as 'online' | 'offline' | 'warning';

  /* 
   * We place four panel-array clusters around the main station:
   *  - Main array (8 kW, 24 panels)  — east of pump station
   *  - Secondary array (5 kW, 16 panels) — south of main
   *  - Tracking array (4 kW, 12 panels) — north-east
   *  - Auxiliary / water-heater (1.5 kW, 4 panels) — west
   */
  return [
    {
      id: 'pv-main',
      coordinates: [9.7008, 36.9997],
      capacityKw: 8.0,
      currentKw: parseFloat(((pvKw * 0.52)).toFixed(1)),
      status,
      label: 'Array Principal',
      panels: 24,
    },
    {
      id: 'pv-south',
      coordinates: [9.7006, 36.9993],
      capacityKw: 5.0,
      currentKw: parseFloat(((pvKw * 0.33)).toFixed(1)),
      status,
      label: 'Array Sud',
      panels: 16,
    },
    {
      id: 'pv-track',
      coordinates: [9.7013, 37.0002],
      capacityKw: 4.0,
      currentKw: parseFloat(((pvKw * 0.26)).toFixed(1)),
      status: 'online',
      label: 'Tracker Solaire',
      panels: 12,
    },
    {
      id: 'pv-aux',
      coordinates: [9.6997, 36.9999],
      capacityKw: 1.5,
      currentKw: parseFloat(((pvKw * 0.10)).toFixed(1)),
      status: 'online',
      label: 'Array Auxiliaire',
      panels: 4,
    },
  ];
}

/** Returns a glowing sun burst SVG (string) for the shimmer effect ring. */
function sunBurstSVG(color: string, r = 18): string {
  const rays = 8;
  const paths: string[] = [];
  for (let i = 0; i < rays; i++) {
    const angle = (i / rays) * 2 * Math.PI;
    const x1 = r * Math.cos(angle);
    const y1 = r * Math.sin(angle);
    const x2 = (r + 7) * Math.cos(angle);
    const y2 = (r + 7) * Math.sin(angle);
    paths.push(`<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}" stroke="${color}" stroke-width="1.5" stroke-linecap="round" opacity="0.6"/>`);
  }
  return paths.join('');
}

/** Renders a mini grid of solar-panel cells inside the SVG badge. */
function panelGridSVG(cols: number, rows: number, x0: number, y0: number, cellW: number, cellH: number, gap: number, activeColor: string): string {
  const cells: string[] = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const cx = x0 + c * (cellW + gap);
      const cy = y0 + r * (cellH + gap);
      // Each cell = dark blue-grey frame + lighter inner fill + tiny cross lines
      cells.push(`
        <rect x="${cx}" y="${cy}" width="${cellW}" height="${cellH}" rx="1" fill="#1E3A5F" stroke="${activeColor}" stroke-width="0.5" opacity="0.9"/>
        <line x1="${cx}" y1="${cy + cellH / 2}" x2="${cx + cellW}" y2="${cy + cellH / 2}" stroke="${activeColor}" stroke-width="0.3" opacity="0.4"/>
        <line x1="${cx + cellW / 2}" y1="${cy}" x2="${cx + cellW / 2}" y2="${cy + cellH}" stroke="${activeColor}" stroke-width="0.3" opacity="0.4"/>
      `);
    }
  }
  return cells.join('');
}

/** Build the full HTML for a solar panel array marker. */
function buildMarkerHTML(array: PanelArray): string {
  const efficiency = array.capacityKw > 0 ? Math.round((array.currentKw / array.capacityKw) * 100) : 0;
  const isOffline = array.status === 'offline';
  const isWarning = array.status === 'warning';

  // Color theme
  const glowColor = isOffline ? '#6B7280' : isWarning ? '#F59E0B' : '#FCD34D';
  const panelColor = isOffline ? '#4B5563' : isWarning ? '#D97706' : '#60A5FA';
  const bgColor = isOffline ? '#1F2937' : '#0F172A';
  const statusRing = isOffline ? '#6B7280' : isWarning ? '#F59E0B' : '#FBBF24';

  // Panel grid layout: 3×2 for small, 4×3 for big
  const cols = array.panels >= 16 ? 4 : 3;
  const rows = array.panels >= 16 ? 3 : 2;
  const cellW = 7;
  const cellH = 6;
  const gap = 1.5;
  const gridW = cols * (cellW + gap) - gap;
  const gridH = rows * (cellH + gap) - gap;

  // SVG viewbox
  const svgW = 54;
  const svgH = 54;
  const gridX = (svgW - gridW) / 2;
  const gridY = 8;

  // Efficiency bar
  const barW = 32;
  const barFill = Math.round((barW * efficiency) / 100);
  const barX = (svgW - barW) / 2;
  const barY = gridY + gridH + 5;

  const svgContent = `
    <svg xmlns="http://www.w3.org/2000/svg" width="${svgW}" height="${svgH}" viewBox="0 0 ${svgW} ${svgH}">
      <defs>
        <radialGradient id="bgGrad-${array.id}" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="${bgColor}" stop-opacity="1"/>
          <stop offset="100%" stop-color="#020617" stop-opacity="1"/>
        </radialGradient>
        <filter id="glow-${array.id}" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="2" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>
      <!-- Badge background -->
      <rect x="1" y="1" width="${svgW - 2}" height="${svgH - 2}" rx="10" fill="url(#bgGrad-${array.id})" stroke="${statusRing}" stroke-width="1.5"/>
      <!-- Panel grid -->
      ${panelGridSVG(cols, rows, gridX, gridY, cellW, cellH, gap, panelColor)}
      <!-- Efficiency bar bg -->
      <rect x="${barX}" y="${barY}" width="${barW}" height="4" rx="2" fill="#1E293B"/>
      <!-- Efficiency bar fill -->
      <rect x="${barX}" y="${barY}" width="${barFill}" height="4" rx="2" fill="${glowColor}" filter="url(#glow-${array.id})"/>
      <!-- kW label -->
      <text x="${svgW / 2}" y="${barY + 13}" text-anchor="middle" font-family="monospace" font-size="7" fill="${glowColor}" font-weight="bold">${array.currentKw} kW</text>
    </svg>
  `;

  return `
    <div class="group relative cursor-pointer select-none" style="width:${svgW}px; height:${svgH}px;">
      <!-- Animated ring (online only) -->
      ${!isOffline ? `<div class="absolute inset-0 rounded-xl border-2 border-yellow-400/40 animate-ping" style="animation-duration:3s;"></div>` : ''}
      <!-- Main badge -->
      <div class="relative" style="filter: drop-shadow(0 0 8px ${glowColor}80);">
        ${svgContent}
      </div>
      <!-- Tooltip -->
      <div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:flex flex-col z-50 pointer-events-none" style="min-width:160px;">
        <div style="background: rgba(2,6,23,0.95); border: 1px solid ${statusRing}50; border-radius:12px; padding:8px 10px; box-shadow:0 8px 32px rgba(0,0,0,0.5);">
          <p style="color:${glowColor}; font-weight:700; font-size:11px; font-family:Inter,sans-serif; margin:0 0 2px;">${array.label}</p>
          <p style="color:#94A3B8; font-size:9px; font-family:monospace; margin:0 0 4px;">${array.id.toUpperCase()}</p>
          <div style="display:flex;align-items:center;gap:6px;margin-bottom:3px;">
            <div style="width:8px;height:8px;border-radius:50%;background:${statusRing};box-shadow:0 0 6px ${statusRing};flex-shrink:0;"></div>
            <span style="color:#CBD5E1;font-size:9px;font-family:Inter,sans-serif;">
              ${array.status === 'online' ? 'En ligne' : array.status === 'warning' ? 'Avertissement' : 'Hors ligne'}
            </span>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;">
            <div style="background:#1E293B;border-radius:6px;padding:4px 6px;">
              <p style="color:#64748B;font-size:8px;margin:0;">Production</p>
              <p style="color:${glowColor};font-size:11px;font-weight:700;margin:0;font-family:monospace;">${array.currentKw} kW</p>
            </div>
            <div style="background:#1E293B;border-radius:6px;padding:4px 6px;">
              <p style="color:#64748B;font-size:8px;margin:0;">Capacité</p>
              <p style="color:#94A3B8;font-size:11px;font-weight:700;margin:0;font-family:monospace;">${array.capacityKw} kW</p>
            </div>
            <div style="background:#1E293B;border-radius:6px;padding:4px 6px;">
              <p style="color:#64748B;font-size:8px;margin:0;">Rendement</p>
              <p style="color:${efficiency > 70 ? '#4ADE80' : efficiency > 40 ? '#FBBF24' : '#F87171'};font-size:11px;font-weight:700;margin:0;font-family:monospace;">${efficiency}%</p>
            </div>
            <div style="background:#1E293B;border-radius:6px;padding:4px 6px;">
              <p style="color:#64748B;font-size:8px;margin:0;">Panneaux</p>
              <p style="color:#94A3B8;font-size:11px;font-weight:700;margin:0;font-family:monospace;">${array.panels}</p>
            </div>
          </div>
        </div>
        <!-- Arrow -->
        <div style="width:0;height:0;border-left:6px solid transparent;border-right:6px solid transparent;border-top:6px solid ${statusRing}50;align-self:center;"></div>
      </div>
    </div>
  `;
}

/**
 * SolarPanelLayer — renders photovoltaic panel-array markers on the farm map.
 *
 * Each marker is a custom SVG badge showing:
 *  - A miniature grid of solar-panel cells (blue, metallic look)
 *  - A live efficiency bar
 *  - Current power output (kW)
 *  - On hover: a detailed tooltip with production, capacity, efficiency
 *  - Animated glow ring when online
 */
export function SolarPanelLayer({ map, visible = true }: SolarPanelLayerProps) {
  const markersRef = useRef<Marker[]>([]);

  useEffect(() => {
    if (!map) return;

    // Remove existing markers
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    if (!visible) return;

    const arrays = buildPanelArrays();

    arrays.forEach((array) => {
      const el = document.createElement('div');
      el.innerHTML = buildMarkerHTML(array);

      try {
        const marker = new maplibregl.Marker({ element: el, anchor: 'center' })
          .setLngLat(array.coordinates)
          .addTo(map);

        markersRef.current.push(marker);
      } catch (err) {
        console.warn('Solar panel marker error:', err);
      }
    });

    return () => {
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
    };
  }, [map, visible]);

  return null;
}
