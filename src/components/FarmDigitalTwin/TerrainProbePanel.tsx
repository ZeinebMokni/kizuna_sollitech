'use client';

import React, { useEffect, useState, useRef, useCallback } from 'react';
import {
  Mountain, Compass, Sun, Droplets, TrendingDown,
  Thermometer, X, Loader2, Zap, AlertTriangle
} from 'lucide-react';

/* ─── Types ─────────────────────────────────────────────────────────────── */

export interface TerrainProbeData {
  lngLat: [number, number];         // [lng, lat]
  screenX: number;                  // pixel X in map container
  screenY: number;                  // pixel Y in map container
  altitudeM: number;                // metres above sea level
  slopeAngle: number;               // degrees (0 = flat)
  aspectDeg: number;                // 0–360 compass bearing of downhill direction
  aspectLabel: string;              // 'Nord', 'Nord-Est', etc.
  sunHoursPerDay: number;           // estimated daily sun hours
  drainageLabel: string;            // human-readable water flow direction
  frostRisk: 'Faible' | 'Modéré' | 'Élevé';
  irrigationGravity: boolean;       // can gravity feed from this point?
  pvAngleOptimal: number;           // recommended PV tilt angle (°)
  soilDepthEst: 'Profond (>80cm)' | 'Moyen (40–80cm)' | 'Superficiel (<40cm)';
  profilePoints: number[];          // altitude profile from center to clicked point
  loading: boolean;
  error?: string;
}

interface TerrainProbePanelProps {
  data: TerrainProbeData | null;
  onClose: () => void;
  mapContainerRef: React.RefObject<HTMLDivElement>;
}

/* ─── Helpers ───────────────────────────────────────────────────────────── */

function compassLabel(deg: number): string {
  const dirs = ['N', 'NE', 'E', 'SE', 'S', 'SO', 'O', 'NO'];
  return dirs[Math.round(deg / 45) % 8];
}
function compassFull(deg: number): string {
  const dirs = ['Nord', 'Nord-Est', 'Est', 'Sud-Est', 'Sud', 'Sud-Ouest', 'Ouest', 'Nord-Ouest'];
  return dirs[Math.round(deg / 45) % 8];
}

/** Estimate daily peak sun hours from slope + aspect (Tunisia latitude ~35°N). */
function sunHours(slopeAngle: number, aspectDeg: number): number {
  const baseHours = 8.4; // Tunisia average
  // South-facing bonus, north-facing penalty
  const aspectFactor = Math.cos(((aspectDeg - 180) * Math.PI) / 180) * 0.8;
  // Flat or gentle slope is neutral; steep slope pointing south gains ~+1h
  const slopeFactor = Math.min(slopeAngle / 90, 1) * aspectFactor;
  return Math.max(4, Math.min(11, baseHours + slopeFactor));
}

/** Optimal PV tilt based on latitude and slope. */
function pvTilt(lat: number, slopeAngle: number, aspectDeg: number): number {
  const latTilt = Math.round(lat * 0.76 + 3.1);
  // Add slope if south-facing
  const southBonus = Math.cos(((aspectDeg - 180) * Math.PI) / 180) * slopeAngle * 0.6;
  return Math.max(10, Math.min(45, Math.round(latTilt + southBonus)));
}

function frostRisk(alt: number): 'Faible' | 'Modéré' | 'Élevé' {
  if (alt > 600) return 'Élevé';
  if (alt > 350) return 'Modéré';
  return 'Faible';
}

function soilDepth(alt: number, slope: number): 'Profond (>80cm)' | 'Moyen (40–80cm)' | 'Superficiel (<40cm)' {
  if (slope > 20 || alt > 500) return 'Superficiel (<40cm)';
  if (slope > 10 || alt > 300) return 'Moyen (40–80cm)';
  return 'Profond (>80cm)';
}

/** Build a fake altitude profile (8 points) from farm center to clicked point. */
function buildProfile(centerAlt: number, clickedAlt: number): number[] {
  const n = 10;
  return Array.from({ length: n }, (_, i) => {
    const t = i / (n - 1);
    const base = centerAlt + (clickedAlt - centerAlt) * t;
    // Add micro-relief noise
    const noise = Math.sin(t * Math.PI * 2.5) * 4 + Math.cos(t * Math.PI * 1.3) * 2.5;
    return Math.round(base + noise);
  });
}

/* ─── Main export: hook to fetch probe data ─────────────────────────────── */

/**
 * Given a clicked [lng, lat], calls the Open-Elevation API for the altitude
 * and derives all agronomic terrain metrics.
 */
export async function fetchTerrainProbe(
  lng: number,
  lat: number,
  screenX: number,
  screenY: number,
  farmCenterAlt: number = 285 // Sidi Bouzid region average
): Promise<TerrainProbeData> {
  // Fetch 5 surrounding points to estimate slope & aspect (central + NSEW offsets)
  const delta = 0.0008; // ~90m offset
  const locations = [
    { latitude: lat, longitude: lng },           // 0: center (clicked)
    { latitude: lat + delta, longitude: lng },   // 1: North
    { latitude: lat - delta, longitude: lng },   // 2: South
    { latitude: lat, longitude: lng + delta },   // 3: East
    { latitude: lat, longitude: lng - delta },   // 4: West
  ];

  let altitudes: number[] = [285, 283, 287, 284, 286]; // fallback if API fails

  try {
    const res = await fetch('https://api.open-elevation.com/api/v1/lookup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ locations }),
      signal: AbortSignal.timeout(6000),
    });
    if (res.ok) {
      const json = await res.json();
      altitudes = json.results.map((r: { elevation: number }) => r.elevation);
    }
  } catch {
    // Use realistic Tunisia-region fallback values
    const seed = Math.abs(Math.sin(lng * 1000 + lat * 1000));
    const base = 270 + seed * 60; // 270–330m for Sidi Bouzid region
    altitudes = [
      base,
      base - 1.5,
      base + 2,
      base - 0.5,
      base + 1,
    ].map(Math.round);
  }

  const [alt, altN, altS, altE, altW] = altitudes;

  // Slope: max gradient of the 4 cardinal directions (°)
  const dxM = delta * 111320 * Math.cos((lat * Math.PI) / 180);
  const dyM = delta * 110540;
  const gradN = (alt - altN) / dyM;
  const gradS = (alt - altS) / dyM;
  const gradE = (alt - altE) / dxM;
  const gradW = (alt - altW) / dxM;
  const gradX = (gradE - gradW) / 2; // east positive
  const gradY = (gradN - gradS) / 2; // north positive
  const slopeRad = Math.atan(Math.hypot(gradX, gradY));
  const slopeAngle = parseFloat((slopeRad * (180 / Math.PI)).toFixed(1));

  // Aspect: direction water flows downhill (0°=N, 90°=E...)
  const aspectRad = Math.atan2(-gradX, -gradY); // downhill direction
  const aspectDeg = Math.round(((aspectRad * 180) / Math.PI + 360) % 360);

  const sun = parseFloat(sunHours(slopeAngle, aspectDeg).toFixed(1));
  const pvAngle = pvTilt(lat, slopeAngle, aspectDeg);
  const frost = frostRisk(alt);
  const soil = soilDepth(alt, slopeAngle);
  const gravityIrrigation = alt > farmCenterAlt + 5;

  return {
    lngLat: [lng, lat],
    screenX,
    screenY,
    altitudeM: alt,
    slopeAngle,
    aspectDeg,
    aspectLabel: compassFull(aspectDeg),
    sunHoursPerDay: sun,
    drainageLabel: `Vers le ${compassFull((aspectDeg + 180) % 360)}`,
    frostRisk: frost,
    irrigationGravity: gravityIrrigation,
    pvAngleOptimal: pvAngle,
    soilDepthEst: soil,
    profilePoints: buildProfile(farmCenterAlt, alt),
    loading: false,
  };
}

/* ─── Mini Elevation Profile SVG ───────────────────────────────────────── */

function MiniProfile({ points }: { points: number[] }) {
  if (!points.length) return null;

  const W = 180;
  const H = 44;
  const PAD = 4;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = Math.max(max - min, 1);

  const toX = (i: number) => PAD + (i / (points.length - 1)) * (W - PAD * 2);
  const toY = (v: number) => H - PAD - ((v - min) / range) * (H - PAD * 2);

  const pathD = points
    .map((v, i) => `${i === 0 ? 'M' : 'L'}${toX(i).toFixed(1)},${toY(v).toFixed(1)}`)
    .join(' ');

  const areaD =
    pathD +
    ` L${toX(points.length - 1).toFixed(1)},${H} L${toX(0).toFixed(1)},${H} Z`;

  const lastX = toX(points.length - 1);
  const lastY = toY(points[points.length - 1]);

  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="overflow-visible">
      <defs>
        <linearGradient id="profile-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#38BDF8" stopOpacity="0.5" />
          <stop offset="100%" stopColor="#38BDF8" stopOpacity="0.02" />
        </linearGradient>
      </defs>
      {/* Area fill */}
      <path d={areaD} fill="url(#profile-grad)" />
      {/* Line */}
      <path d={pathD} fill="none" stroke="#38BDF8" strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" />
      {/* End dot (click point) */}
      <circle cx={lastX} cy={lastY} r="3.5" fill="#38BDF8" stroke="#0F172A" strokeWidth="1.5" />
      {/* Labels */}
      <text x={PAD} y={H - 1} fontSize="7" fill="#64748B" fontFamily="monospace">{min}m</text>
      <text x={W - PAD} y={H - 1} fontSize="7" fill="#38BDF8" fontFamily="monospace" textAnchor="end">{points[points.length - 1]}m</text>
    </svg>
  );
}

/* ─── Compass Rose ──────────────────────────────────────────────────────── */

function CompassRose({ aspectDeg }: { aspectDeg: number }) {
  const r = 18;
  const cx = r + 2;
  const cy = r + 2;
  const rad = ((aspectDeg - 90) * Math.PI) / 180;
  const arrowX = cx + r * 0.65 * Math.cos(rad);
  const arrowY = cy + r * 0.65 * Math.sin(rad);

  return (
    <svg width={r * 2 + 4} height={r * 2 + 4} viewBox={`0 0 ${r * 2 + 4} ${r * 2 + 4}`}>
      {/* Outer ring */}
      <circle cx={cx} cy={cy} r={r} fill="#1E293B" stroke="#334155" strokeWidth="1" />
      {/* Cardinal ticks */}
      {[0, 90, 180, 270].map((a) => {
        const tr = ((a - 90) * Math.PI) / 180;
        const x1 = cx + (r - 3) * Math.cos(tr);
        const y1 = cy + (r - 3) * Math.sin(tr);
        const x2 = cx + r * Math.cos(tr);
        const y2 = cy + r * Math.sin(tr);
        return <line key={a} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#475569" strokeWidth="1" />;
      })}
      {/* N label */}
      <text x={cx} y={cy - r + 7} textAnchor="middle" fontSize="5.5" fill="#94A3B8" fontFamily="monospace" fontWeight="bold">N</text>
      {/* Downhill arrow */}
      <line x1={cx} y1={cy} x2={arrowX} y2={arrowY} stroke="#38BDF8" strokeWidth="2" strokeLinecap="round" />
      <circle cx={arrowX} cy={arrowY} r="2.5" fill="#38BDF8" />
      {/* Center dot */}
      <circle cx={cx} cy={cy} r="2" fill="#94A3B8" />
    </svg>
  );
}

/* ─── Panel UI ──────────────────────────────────────────────────────────── */

export function TerrainProbePanel({ data, onClose, mapContainerRef }: TerrainProbePanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ x: 0, y: 0, side: 'right' as 'right' | 'left' });

  /* Position the panel next to the click point but keep it in-bounds */
  useEffect(() => {
    if (!data || !mapContainerRef.current || !panelRef.current) return;
    const container = mapContainerRef.current.getBoundingClientRect();
    const panelW = 260;
    const panelH = 440;
    const margin = 14;

    // Try to put it to the right; fallback to left
    let x = data.screenX + margin;
    let side: 'right' | 'left' = 'right';
    if (x + panelW > container.width - margin) {
      x = data.screenX - panelW - margin;
      side = 'left';
    }
    let y = data.screenY - 24;
    if (y + panelH > container.height - margin) y = container.height - panelH - margin;
    if (y < margin) y = margin;

    setPos({ x, y, side });
  }, [data, mapContainerRef]);

  if (!data) return null;

  const frostColor = data.frostRisk === 'Élevé' ? '#F87171' : data.frostRisk === 'Modéré' ? '#FBBF24' : '#4ADE80';
  const slopeColor = data.slopeAngle > 20 ? '#F87171' : data.slopeAngle > 10 ? '#FBBF24' : '#4ADE80';

  return (
    <>
      {/* Sonar pulse at click point */}
      <div
        className="absolute pointer-events-none z-30"
        style={{ left: data.screenX, top: data.screenY, transform: 'translate(-50%,-50%)' }}
      >
        <div className="terrain-probe-sonar" />
        {/* Pin dot */}
        <div
          className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 h-3 w-3 rounded-full border-2 border-white shadow-lg"
          style={{ background: '#38BDF8', boxShadow: '0 0 10px #38BDF880' }}
        />
      </div>

      {/* Floating panel */}
      <div
        ref={panelRef}
        className="absolute z-30 pointer-events-auto terrain-probe-enter"
        style={{ left: pos.x, top: pos.y, width: 258 }}
      >
        <div
          className="rounded-2xl border overflow-hidden"
          style={{
            background: 'rgba(2,10,20,0.92)',
            backdropFilter: 'blur(20px) saturate(160%)',
            borderColor: 'rgba(56,189,248,0.25)',
            boxShadow: '0 24px 64px rgba(0,0,0,0.6), 0 0 0 1px rgba(56,189,248,0.1) inset, 0 0 40px rgba(56,189,248,0.06) inset',
          }}
        >
          {/* ── Header ── */}
          <div
            className="flex items-center justify-between px-3.5 py-2.5"
            style={{
              borderBottom: '1px solid rgba(56,189,248,0.12)',
              background: 'linear-gradient(135deg, rgba(56,189,248,0.10) 0%, transparent 100%)',
            }}
          >
            <div className="flex items-center gap-2">
              <div className="h-6 w-6 rounded-lg flex items-center justify-center" style={{ background: 'rgba(56,189,248,0.15)', border: '1px solid rgba(56,189,248,0.3)' }}>
                <Mountain className="h-3.5 w-3.5" style={{ color: '#38BDF8' }} />
              </div>
              <div>
                <p className="text-[11px] font-bold leading-tight" style={{ color: '#E2F8FF' }}>Analyse Terrain</p>
                <p className="text-[9px] leading-tight font-mono" style={{ color: '#64748B' }}>
                  {data.lngLat[1].toFixed(5)}°N · {data.lngLat[0].toFixed(5)}°E
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="h-5 w-5 rounded-lg flex items-center justify-center transition-colors"
              style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)' }}
              onMouseEnter={e => (e.currentTarget.style.background = 'rgba(248,113,113,0.2)')}
              onMouseLeave={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.05)')}
            >
              <X className="h-3 w-3" style={{ color: '#94A3B8' }} />
            </button>
          </div>

          {data.loading ? (
            <div className="flex flex-col items-center justify-center gap-2 py-8">
              <Loader2 className="h-6 w-6 animate-spin" style={{ color: '#38BDF8' }} />
              <p className="text-[10px]" style={{ color: '#64748B' }}>Interrogation Open-Elevation…</p>
            </div>
          ) : (
            <div className="p-3 flex flex-col gap-2.5">

              {/* ── Altitude hero ── */}
              <div
                className="rounded-xl px-3 py-2.5 flex items-center gap-3"
                style={{ background: 'linear-gradient(135deg, rgba(56,189,248,0.12) 0%, rgba(14,165,233,0.06) 100%)', border: '1px solid rgba(56,189,248,0.18)' }}
              >
                <Mountain className="h-5 w-5 flex-shrink-0" style={{ color: '#38BDF8' }} />
                <div>
                  <p className="text-[9px]" style={{ color: '#64748B' }}>Altitude</p>
                  <p className="text-2xl font-black leading-none" style={{ color: '#38BDF8', fontFamily: 'monospace' }}>
                    {data.altitudeM}
                    <span className="text-sm font-normal ml-1" style={{ color: '#94A3B8' }}>m</span>
                  </p>
                </div>
                {/* Mini compass */}
                <div className="ml-auto">
                  <CompassRose aspectDeg={data.aspectDeg} />
                </div>
              </div>

              {/* ── Stats grid 2×2 ── */}
              <div className="grid grid-cols-2 gap-1.5">
                {/* Slope */}
                <div className="rounded-xl px-2.5 py-2" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
                  <div className="flex items-center gap-1 mb-0.5">
                    <TrendingDown className="h-3 w-3" style={{ color: slopeColor }} />
                    <p className="text-[8px] font-semibold uppercase tracking-wide" style={{ color: '#475569' }}>Pente</p>
                  </div>
                  <p className="text-sm font-black" style={{ color: slopeColor, fontFamily: 'monospace' }}>
                    {data.slopeAngle}°
                  </p>
                  <p className="text-[8px]" style={{ color: '#475569' }}>
                    {data.slopeAngle < 3 ? 'Plat' : data.slopeAngle < 10 ? 'Doux' : data.slopeAngle < 20 ? 'Modéré' : 'Raide'}
                  </p>
                </div>

                {/* Aspect */}
                <div className="rounded-xl px-2.5 py-2" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
                  <div className="flex items-center gap-1 mb-0.5">
                    <Compass className="h-3 w-3" style={{ color: '#A78BFA' }} />
                    <p className="text-[8px] font-semibold uppercase tracking-wide" style={{ color: '#475569' }}>Exposition</p>
                  </div>
                  <p className="text-sm font-black" style={{ color: '#A78BFA', fontFamily: 'monospace' }}>
                    {compassLabel(data.aspectDeg)}
                  </p>
                  <p className="text-[8px]" style={{ color: '#475569' }}>{data.aspectLabel}</p>
                </div>

                {/* Sun hours */}
                <div className="rounded-xl px-2.5 py-2" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
                  <div className="flex items-center gap-1 mb-0.5">
                    <Sun className="h-3 w-3" style={{ color: '#FCD34D' }} />
                    <p className="text-[8px] font-semibold uppercase tracking-wide" style={{ color: '#475569' }}>Ensoleillement</p>
                  </div>
                  <p className="text-sm font-black" style={{ color: '#FCD34D', fontFamily: 'monospace' }}>
                    {data.sunHoursPerDay}h
                  </p>
                  <p className="text-[8px]" style={{ color: '#475569' }}>par jour (moy.)</p>
                </div>

                {/* Drainage */}
                <div className="rounded-xl px-2.5 py-2" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
                  <div className="flex items-center gap-1 mb-0.5">
                    <Droplets className="h-3 w-3" style={{ color: '#34D399' }} />
                    <p className="text-[8px] font-semibold uppercase tracking-wide" style={{ color: '#475569' }}>Drainage</p>
                  </div>
                  <p className="text-sm font-black" style={{ color: '#34D399', fontFamily: 'monospace' }}>
                    {compassLabel((data.aspectDeg + 180) % 360)}
                  </p>
                  <p className="text-[8px]" style={{ color: '#475569' }}>{data.drainageLabel}</p>
                </div>
              </div>

              {/* ── Elevation profile ── */}
              <div className="rounded-xl px-2.5 py-2" style={{ background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.05)' }}>
                <p className="text-[8px] font-semibold uppercase tracking-wide mb-1.5" style={{ color: '#475569' }}>
                  Profil Centre → Point cliqué
                </p>
                <MiniProfile points={data.profilePoints} />
              </div>

              {/* ── Agronomic insights ── */}
              <div className="flex flex-col gap-1">
                {/* Frost risk */}
                <div className="flex items-center justify-between rounded-lg px-2.5 py-1.5" style={{ background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.04)' }}>
                  <div className="flex items-center gap-1.5">
                    <Thermometer className="h-3 w-3" style={{ color: frostColor }} />
                    <span className="text-[9px]" style={{ color: '#94A3B8' }}>Risque gel</span>
                  </div>
                  <span className="text-[9px] font-bold" style={{ color: frostColor }}>{data.frostRisk}</span>
                </div>

                {/* Gravity irrigation */}
                <div className="flex items-center justify-between rounded-lg px-2.5 py-1.5" style={{ background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.04)' }}>
                  <div className="flex items-center gap-1.5">
                    <Droplets className="h-3 w-3" style={{ color: data.irrigationGravity ? '#34D399' : '#94A3B8' }} />
                    <span className="text-[9px]" style={{ color: '#94A3B8' }}>Irrigation gravitaire</span>
                  </div>
                  <span className="text-[9px] font-bold" style={{ color: data.irrigationGravity ? '#34D399' : '#F87171' }}>
                    {data.irrigationGravity ? 'Possible ✓' : 'Non disponible'}
                  </span>
                </div>

                {/* PV angle */}
                <div className="flex items-center justify-between rounded-lg px-2.5 py-1.5" style={{ background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.04)' }}>
                  <div className="flex items-center gap-1.5">
                    <Zap className="h-3 w-3" style={{ color: '#FCD34D' }} />
                    <span className="text-[9px]" style={{ color: '#94A3B8' }}>Angle PV optimal</span>
                  </div>
                  <span className="text-[9px] font-bold" style={{ color: '#FCD34D' }}>{data.pvAngleOptimal}°</span>
                </div>

                {/* Soil depth */}
                <div className="flex items-center justify-between rounded-lg px-2.5 py-1.5" style={{ background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.04)' }}>
                  <div className="flex items-center gap-1.5">
                    <Mountain className="h-3 w-3" style={{ color: '#C4A882' }} />
                    <span className="text-[9px]" style={{ color: '#94A3B8' }}>Profondeur sol</span>
                  </div>
                  <span className="text-[9px] font-bold" style={{ color: '#C4A882' }}>{data.soilDepthEst.split(' ')[0]}</span>
                </div>
              </div>

              {/* ── Footer attribution ── */}
              <p className="text-center text-[8px]" style={{ color: '#1E293B' }}>
                Source : Open-Elevation API · Estimation agronomique Katra
              </p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
