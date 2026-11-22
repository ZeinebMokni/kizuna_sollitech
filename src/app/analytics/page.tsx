'use client';

import React, { useState, useRef, useEffect } from 'react';
import { motion, useInView, useAnimation } from 'framer-motion';
import {
  Droplets, Sun, TrendingUp, TrendingDown,
  FileSpreadsheet, BarChart3, Zap, Sprout,
  Battery, Activity
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { useFarmStore } from '@/stores/useFarmStore';
import { DEMO_HOURLY_ENERGY, DEMO_WATER_BASELINE } from '@/lib/mockData';
import { cn, formatNumber } from '@/lib/utils';

/* ─── Smooth bezier curve from points ─────────────────────────────────── */
function smoothPath(pts: [number, number][]): string {
  if (pts.length < 2) return '';
  let d = `M ${pts[0][0].toFixed(2)} ${pts[0][1].toFixed(2)}`;
  for (let i = 1; i < pts.length; i++) {
    const p0 = pts[Math.max(i - 2, 0)];
    const p1 = pts[i - 1];
    const p2 = pts[i];
    const p3 = pts[Math.min(i + 1, pts.length - 1)];
    const cp1x = p1[0] + (p2[0] - p0[0]) / 6;
    const cp1y = p1[1] + (p2[1] - p0[1]) / 6;
    const cp2x = p2[0] - (p3[0] - p1[0]) / 6;
    const cp2y = p2[1] - (p3[1] - p1[1]) / 6;
    d += ` C ${cp1x.toFixed(2)} ${cp1y.toFixed(2)}, ${cp2x.toFixed(2)} ${cp2y.toFixed(2)}, ${p2[0].toFixed(2)} ${p2[1].toFixed(2)}`;
  }
  return d;
}

function areaPath(pts: [number, number][], h: number): string {
  const line = smoothPath(pts);
  const last = pts[pts.length - 1];
  const first = pts[0];
  return `${line} L ${last[0].toFixed(2)} ${h} L ${first[0].toFixed(2)} ${h} Z`;
}

/* ─── Animated SVG line reveal ────────────────────────────────────────── */
function AnimatedPath({ d, stroke, strokeWidth = 2, delay = 0, className = '' }: {
  d: string; stroke: string; strokeWidth?: number; delay?: number; className?: string;
}) {
  const ref = useRef<SVGPathElement>(null);
  const inView = useInView(ref, { once: true, margin: '-40px' });
  const [len, setLen] = useState(0);

  useEffect(() => {
    if (ref.current) setLen(ref.current.getTotalLength());
  }, [d]);

  return (
    <path
      ref={ref}
      d={d}
      fill="none"
      stroke={stroke}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      style={{
        strokeDasharray: len || 2000,
        strokeDashoffset: inView ? 0 : (len || 2000),
        transition: `stroke-dashoffset ${1.2}s cubic-bezier(0.22,1,0.36,1) ${delay}s`,
      }}
    />
  );
}

/* ─── Tooltip hook ────────────────────────────────────────────────────── */
function useTooltip() {
  const [tooltip, setTooltip] = useState<{ x: number; y: number; content: React.ReactNode } | null>(null);
  return { tooltip, setTooltip };
}

/* ════════════════════════════════════════════════════════════════════════
   CHART 1 — Water Consumption 7-Day Trend
   ════════════════════════════════════════════════════════════════════════ */
function WaterTrendChart() {
  const W = 600; const H = 160; const PAD = { top: 16, right: 24, bottom: 32, left: 56 };
  const cW = W - PAD.left - PAD.right;
  const cH = H - PAD.top - PAD.bottom;

  const series = DEMO_WATER_BASELINE.last7DaysLiters;
  const baseline = DEMO_WATER_BASELINE.classicIrrigationLitersPerDay;
  const days = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Auj'];
  const allVals = [...series, baseline];
  const minV = Math.min(...allVals) * 0.88;
  const maxV = Math.max(...allVals) * 1.06;

  const toX = (i: number) => PAD.left + (i / (series.length - 1)) * cW;
  const toY = (v: number) => PAD.top + cH - ((v - minV) / (maxV - minV)) * cH;

  const pts = series.map((v, i) => [toX(i), toY(v)] as [number, number]);
  const baseY = toY(baseline);

  const { tooltip, setTooltip } = useTooltip();
  const gridLines = 4;

  return (
    <div className="relative w-full overflow-hidden">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: 160 }}>
        <defs>
          <linearGradient id="wg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#2BB3CB" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#2BB3CB" stopOpacity="0.02" />
          </linearGradient>
          <clipPath id="wclip"><rect x={PAD.left} y={PAD.top} width={cW} height={cH} /></clipPath>
        </defs>

        {/* Grid */}
        {Array.from({ length: gridLines }).map((_, i) => {
          const y = PAD.top + (i / (gridLines - 1)) * cH;
          const v = maxV - (i / (gridLines - 1)) * (maxV - minV);
          return (
            <g key={i}>
              <line x1={PAD.left} x2={W - PAD.right} y1={y} y2={y}
                stroke="currentColor" strokeOpacity="0.07" strokeWidth="1" />
              <text x={PAD.left - 6} y={y + 4} textAnchor="end" fontSize="8.5"
                fill="currentColor" fillOpacity="0.45">
                {(v / 1000).toFixed(0)}k
              </text>
            </g>
          );
        })}

        {/* Baseline dashed line */}
        <line x1={PAD.left} x2={W - PAD.right} y1={baseY} y2={baseY}
          stroke="#E06A5A" strokeDasharray="6 4" strokeWidth="1.2" strokeOpacity="0.6" />
        <text x={W - PAD.right + 4} y={baseY + 4} fontSize="8" fill="#E06A5A" fillOpacity="0.8">
          Réf.
        </text>

        {/* Area fill */}
        <path d={areaPath(pts, PAD.top + cH)} fill="url(#wg)" clipPath="url(#wclip)" />

        {/* Trend line */}
        <AnimatedPath d={smoothPath(pts)} stroke="#2BB3CB" strokeWidth={2.5} />

        {/* Data points */}
        {pts.map(([x, y], i) => (
          <g key={i}
            onMouseEnter={() => setTooltip({ x, y, content: <><b>{days[i]}</b><br />{formatNumber(series[i])} L</> })}
            onMouseLeave={() => setTooltip(null)}
            className="cursor-pointer"
          >
            <circle cx={x} cy={y} r="6" fill="transparent" />
            <motion.circle cx={x} cy={y} r="3.5" fill="#2BB3CB" stroke="#0E3C48" strokeWidth="1.5"
              initial={{ scale: 0 }} animate={{ scale: 1 }}
              transition={{ delay: 1.2 + i * 0.08, duration: 0.3, type: 'spring' }} />
          </g>
        ))}

        {/* X axis labels */}
        {days.map((d, i) => (
          <text key={i} x={toX(i)} y={H - 6} textAnchor="middle" fontSize="9"
            fill="currentColor" fillOpacity="0.5">{d}</text>
        ))}
      </svg>

      {/* Tooltip */}
      {tooltip && (
        <div className="absolute pointer-events-none z-10 px-2.5 py-1.5 rounded-xl text-[11px] font-semibold"
          style={{
            left: (tooltip.x / W * 100) + '%',
            top: tooltip.y / 160 * 100 + '%',
            transform: 'translate(-50%, -130%)',
            background: 'rgba(7,26,32,0.92)',
            border: '1px solid rgba(43,179,203,0.3)',
            color: '#E6F4F7',
            whiteSpace: 'nowrap',
            boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
          }}>
          {tooltip.content}
        </div>
      )}

      {/* Legend */}
      <div className="flex items-center gap-4 mt-2 text-[10px] text-earth-400 justify-end px-6">
        <span className="flex items-center gap-1.5">
          <span className="h-0.5 w-6 rounded bg-water-500 inline-block" />
          Consommation réelle
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-0.5 w-6 rounded border-t-2 border-dashed border-alert-500 inline-block" />
          Référence classique ({formatNumber(DEMO_WATER_BASELINE.classicIrrigationLitersPerDay)} L)
        </span>
      </div>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════════════
   CHART 2 — Hourly Energy Profile (Solar vs Pump vs Battery SoC)
   ════════════════════════════════════════════════════════════════════════ */
function EnergyProfileChart() {
  const W = 600; const H = 160; const PAD = { top: 16, right: 24, bottom: 32, left: 44 };
  const cW = W - PAD.left - PAD.right;
  const cH = H - PAD.top - PAD.bottom;

  const data = DEMO_HOURLY_ENERGY;
  const maxKw = Math.max(...data.map(d => d.solarKw)) * 1.1;
  const maxSoC = 100;

  const toX = (i: number) => PAD.left + (i / (data.length - 1)) * cW;
  const toY = (v: number, max: number) => PAD.top + cH - (v / max) * cH;

  const solarPts = data.map((d, i) => [toX(i), toY(d.solarKw, maxKw)] as [number, number]);
  const pumpPts = data.map((d, i) => [toX(i), toY(d.pumpKw, maxKw)] as [number, number]);
  const socPts = data.map((d, i) => [toX(i), toY(d.batterySoC, maxSoC)] as [number, number]);

  const { tooltip, setTooltip } = useTooltip();

  return (
    <div className="relative w-full overflow-hidden">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: 160 }}>
        <defs>
          <linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#E2AE48" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#E2AE48" stopOpacity="0.02" />
          </linearGradient>
          <linearGradient id="pg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#2BB3CB" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#2BB3CB" stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {/* Grid */}
        {[0, 25, 50, 75, 100].map((pct, i) => {
          const y = PAD.top + cH - (pct / 100) * cH;
          return (
            <g key={i}>
              <line x1={PAD.left} x2={W - PAD.right} y1={y} y2={y}
                stroke="currentColor" strokeOpacity="0.07" strokeWidth="1" />
              <text x={PAD.left - 5} y={y + 4} textAnchor="end" fontSize="8.5"
                fill="currentColor" fillOpacity="0.4">
                {Math.round(maxKw * pct / 100)}
              </text>
            </g>
          );
        })}

        {/* Solar area */}
        <path d={areaPath(solarPts, PAD.top + cH)} fill="url(#sg)" />
        {/* Pump area */}
        <path d={areaPath(pumpPts, PAD.top + cH)} fill="url(#pg)" />

        {/* Battery SoC dashed line (secondary axis) */}
        <AnimatedPath d={smoothPath(socPts)} stroke="#4DBF98" strokeWidth={1.5} delay={0.4} />

        {/* Solar line */}
        <AnimatedPath d={smoothPath(solarPts)} stroke="#E2AE48" strokeWidth={2.5} />
        {/* Pump line */}
        <AnimatedPath d={smoothPath(pumpPts)} stroke="#2BB3CB" strokeWidth={2} delay={0.2} />

        {/* Hover areas */}
        {data.map((d, i) => (
          <g key={i}
            onMouseEnter={() => setTooltip({
              x: toX(i), y: toY(d.solarKw, maxKw),
              content: <><b>{d.hour}</b><br />☀️ {d.solarKw} kW<br />💧 {d.pumpKw} kW<br />🔋 {d.batterySoC}%</>
            })}
            onMouseLeave={() => setTooltip(null)}
          >
            <rect x={toX(i) - cW / data.length / 2} y={PAD.top} width={cW / data.length}
              height={cH} fill="transparent" className="cursor-pointer" />
            <motion.circle cx={toX(i)} cy={toY(d.solarKw, maxKw)} r="3"
              fill="#E2AE48" stroke="#3A2604" strokeWidth="1.5"
              initial={{ scale: 0 }} animate={{ scale: 1 }}
              transition={{ delay: 1.4 + i * 0.07, type: 'spring' }} />
          </g>
        ))}

        {/* X labels */}
        {data.map((d, i) => (
          <text key={i} x={toX(i)} y={H - 5} textAnchor="middle" fontSize="9"
            fill="currentColor" fillOpacity="0.5">{d.hour}</text>
        ))}

        {/* kW label */}
        <text x={PAD.left - 12} y={PAD.top + 4} fontSize="8" fill="currentColor" fillOpacity="0.4"
          textAnchor="middle">kW</text>
      </svg>

      {tooltip && (
        <div className="absolute pointer-events-none z-10 px-2.5 py-1.5 rounded-xl text-[11px] font-semibold"
          style={{
            left: (tooltip.x / W * 100) + '%', top: 0,
            transform: 'translateX(-50%)',
            background: 'rgba(7,26,32,0.92)',
            border: '1px solid rgba(226,174,72,0.3)',
            color: '#E6F4F7', whiteSpace: 'nowrap',
            boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
          }}>
          {tooltip.content}
        </div>
      )}

      <div className="flex items-center gap-4 mt-2 text-[10px] text-earth-400 justify-end px-6">
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-sun-500 inline-block" />Solaire (kW)</span>
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-water-500 inline-block" />Pompage (kW)</span>
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-brand-500 inline-block" />Batterie SoC (%)</span>
      </div>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════════════
   CHART 3 — Zone Water Usage Horizontal Bars
   ════════════════════════════════════════════════════════════════════════ */
function ZoneWaterChart({ zones }: { zones: any[] }) {
  const max = Math.max(...zones.map(z => z.dailyWaterLiters));
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: '-30px' });

  const COLORS = ['#2BB3CB', '#4DBF98', '#E2AE48', '#EE7B6B', '#A78BFA'];

  return (
    <div ref={ref} className="space-y-3">
      {zones.map((zone, i) => {
        const pct = (zone.dailyWaterLiters / max) * 100;
        return (
          <div key={zone.id}>
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-earth-300 font-medium truncate max-w-[55%]">
                {zone.name.split(' - ')[0]}
              </span>
              <span className="font-mono font-bold" style={{ color: COLORS[i % COLORS.length] }}>
                {formatNumber(zone.dailyWaterLiters)} L
              </span>
            </div>
            <div className="h-5 bg-raised rounded-full overflow-hidden relative">
              <motion.div
                className="h-full rounded-full flex items-center justify-end pr-2"
                style={{ background: `linear-gradient(90deg, ${COLORS[i % COLORS.length]}80, ${COLORS[i % COLORS.length]})` }}
                initial={{ width: 0 }}
                animate={{ width: inView ? `${pct}%` : 0 }}
                transition={{ duration: 1, delay: i * 0.1, ease: [0.22, 1, 0.36, 1] }}
              >
                <span className="text-[9px] font-bold text-white/90 drop-shadow">
                  {zone.soilMoisturePercent}% 💧
                </span>
              </motion.div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════════════
   CHART 4 — Yield & Energy per Zone (grouped bars)
   ════════════════════════════════════════════════════════════════════════ */
function ZoneYieldChart({ zones }: { zones: any[] }) {
  const W = 580; const H = 160; const PAD = { top: 16, right: 16, bottom: 40, left: 40 };
  const cW = W - PAD.left - PAD.right;
  const cH = H - PAD.top - PAD.bottom;

  const maxYield = Math.max(...zones.map(z => z.yieldEstimateTons));
  const maxEnergy = Math.max(...zones.map(z => z.dailyEnergyKwh));

  const groupW = cW / zones.length;
  const barW = groupW * 0.28;
  const gap = barW * 0.3;

  const ref = useRef<SVGSVGElement>(null);
  const inView = useInView(ref as any, { once: true, margin: '-30px' });
  const { tooltip, setTooltip } = useTooltip();

  const YIELD_COLOR = '#4DBF98';
  const ENERGY_COLOR = '#E2AE48';

  return (
    <div className="relative">
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: 160 }}>
        <defs>
          <linearGradient id="yg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={YIELD_COLOR} />
            <stop offset="100%" stopColor={YIELD_COLOR} stopOpacity="0.5" />
          </linearGradient>
          <linearGradient id="eg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={ENERGY_COLOR} />
            <stop offset="100%" stopColor={ENERGY_COLOR} stopOpacity="0.5" />
          </linearGradient>
        </defs>

        {/* Grid */}
        {[0, 25, 50, 75, 100].map((pct, i) => {
          const y = PAD.top + cH - (pct / 100) * cH;
          return (
            <line key={i} x1={PAD.left} x2={W - PAD.right} y1={y} y2={y}
              stroke="currentColor" strokeOpacity="0.07" strokeWidth="1" />
          );
        })}

        {zones.map((zone, i) => {
          const cx = PAD.left + i * groupW + groupW / 2;
          const yH = (zone.yieldEstimateTons / maxYield) * cH;
          const eH = (zone.dailyEnergyKwh / maxEnergy) * cH;
          const baseY = PAD.top + cH;

          return (
            <g key={zone.id}>
              {/* Yield bar */}
              <motion.rect
                x={cx - barW - gap / 2}
                y={inView ? baseY - yH : baseY}
                width={barW}
                height={inView ? yH : 0}
                rx="3"
                fill="url(#yg)"
                initial={false}
                animate={{ y: inView ? baseY - yH : baseY, height: inView ? yH : 0 }}
                transition={{ duration: 0.9, delay: i * 0.1 + 0.3, ease: [0.22, 1, 0.36, 1] }}
                onMouseEnter={() => setTooltip({
                  x: cx, y: baseY - yH,
                  content: <><b>{zone.name.split(' - ')[0]}</b><br />🌾 {zone.yieldEstimateTons} T<br />⚡ {zone.dailyEnergyKwh} kWh</>
                })}
                onMouseLeave={() => setTooltip(null)}
                className="cursor-pointer"
              />

              {/* Energy bar */}
              <motion.rect
                x={cx + gap / 2}
                y={inView ? baseY - eH : baseY}
                width={barW}
                height={inView ? eH : 0}
                rx="3"
                fill="url(#eg)"
                initial={false}
                animate={{ y: inView ? baseY - eH : baseY, height: inView ? eH : 0 }}
                transition={{ duration: 0.9, delay: i * 0.1 + 0.45, ease: [0.22, 1, 0.36, 1] }}
                onMouseEnter={() => setTooltip({
                  x: cx, y: baseY - eH,
                  content: <><b>{zone.name.split(' - ')[0]}</b><br />⚡ {zone.dailyEnergyKwh} kWh</>
                })}
                onMouseLeave={() => setTooltip(null)}
                className="cursor-pointer"
              />

              {/* X label */}
              <text x={cx} y={H - 5} textAnchor="middle" fontSize="9"
                fill="currentColor" fillOpacity="0.5">
                {zone.name.split(' ')[1] ?? `Z${i + 1}`}
              </text>
            </g>
          );
        })}
      </svg>

      {tooltip && (
        <div className="absolute pointer-events-none z-10 px-2.5 py-1.5 rounded-xl text-[11px] font-semibold"
          style={{
            left: (tooltip.x / W * 100) + '%',
            top: '0%',
            transform: 'translateX(-50%)',
            background: 'rgba(7,26,32,0.92)',
            border: '1px solid rgba(77,191,152,0.3)',
            color: '#E6F4F7', whiteSpace: 'nowrap',
            boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
          }}>
          {tooltip.content}
        </div>
      )}

      <div className="flex items-center gap-4 mt-2 text-[10px] text-earth-400 justify-end px-4">
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-brand-500 inline-block" />Rendement (T)</span>
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-sun-500 inline-block" />Énergie (kWh/j)</span>
      </div>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════════════
   KPI STAT CARD
   ════════════════════════════════════════════════════════════════════════ */
function StatCard({ icon: Icon, label, value, sub, color, trend }: {
  icon: React.ElementType; label: string; value: string; sub: string;
  color: string; trend?: 'up' | 'down' | 'neutral';
}) {
  return (
    <div className="qa-card bg-surface border border-line rounded-2xl p-4 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-[11px] text-earth-400 font-semibold">{label}</span>
        <span className={cn('h-8 w-8 rounded-xl flex items-center justify-center', color)}>
          <Icon className="h-4 w-4 text-white" />
        </span>
      </div>
      <p className={cn('text-2xl font-black tracking-tight', color.replace('bg-', 'text-').replace('/20', '-400'))}>
        {value}
      </p>
      <div className="flex items-center gap-1 text-[11px] text-earth-400">
        {trend === 'down' && <TrendingDown className="h-3 w-3 text-brand-400" />}
        {trend === 'up' && <TrendingUp className="h-3 w-3 text-sun-400" />}
        {trend === 'neutral' && <Activity className="h-3 w-3 text-water-400" />}
        <span>{sub}</span>
      </div>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════════════
   CHART CONTAINER
   ════════════════════════════════════════════════════════════════════════ */
function ChartCard({ title, icon: Icon, iconColor, children }: {
  title: string; icon: React.ElementType; iconColor: string; children: React.ReactNode;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-40px' }}
      transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
      className="qa-card bg-surface border border-line rounded-2xl p-5"
    >
      <div className="flex items-center gap-2.5 mb-4 pb-3 border-b border-line">
        <span className={cn('h-7 w-7 rounded-lg flex items-center justify-center', iconColor)}>
          <Icon className="h-3.5 w-3.5 text-white" />
        </span>
        <h3 className="text-sm font-bold text-ink">{title}</h3>
      </div>
      {children}
    </motion.div>
  );
}

/* ════════════════════════════════════════════════════════════════════════
   PAGE
   ════════════════════════════════════════════════════════════════════════ */
export default function AnalyticsPage() {
  const { farm } = useFarmStore();
  const [exported, setExported] = useState(false);

  const totalWater = farm.zones.reduce((s, z) => s + z.dailyWaterLiters, 0);
  const totalEnergy = farm.zones.reduce((s, z) => s + z.dailyEnergyKwh, 0);
  const totalYield = farm.zones.reduce((s, z) => s + z.yieldEstimateTons, 0);
  const baseline = DEMO_WATER_BASELINE.classicIrrigationLitersPerDay;
  const savedPct = Math.round(((baseline - totalWater) / baseline) * 100);

  const handleExportCSV = () => {
    const rows = [
      ['Parcelle', 'Culture', 'Surface (Ha)', 'Humidité (%)', 'Eau (L/j)', 'Énergie (kWh)', 'Rendement (T)'],
      ...farm.zones.map(z => [z.name, z.cropType, z.areaHa, z.soilMoisturePercent, z.dailyWaterLiters, z.dailyEnergyKwh, z.yieldEstimateTons]),
    ];
    const csv = rows.map(r => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'katra-analytics.csv'; a.click();
    setExported(true); setTimeout(() => setExported(false), 3000);
  };

  return (
    <AppShell>
      <div className="space-y-6">

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-line gap-4">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-brand-400">
              Analytique Agronomique · Performance
            </span>
            <h1 className="text-2xl font-black text-ink mt-0.5">Rapports &amp; Historique des Ressources</h1>
            <p className="text-xs text-earth-400 mt-0.5">
              Eau · Énergie · Rendement · Comparatif zones · {farm.name}
            </p>
          </div>
          <button
            onClick={handleExportCSV}
            className="px-4 py-2.5 rounded-xl bg-raised hover:bg-highlight border border-brand-500/30 text-brand-300 font-bold text-xs flex items-center gap-2 transition-all shadow-lg"
          >
            <FileSpreadsheet className="h-4 w-4" />
            <span>{exported ? '✓ Téléchargé !' : 'Exporter CSV'}</span>
          </button>
        </div>



        {/* Row 1: Water trend + Energy profile */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <ChartCard title="Consommation Eau — Tendance 7 Jours" icon={Droplets} iconColor="bg-water-500">
            <WaterTrendChart />
          </ChartCard>
          <ChartCard title="Profil Énergétique Horaire — Aujourd'hui" icon={Zap} iconColor="bg-sun-500">
            <EnergyProfileChart />
          </ChartCard>
        </div>

        {/* Row 2: Zone bars + Yield bars */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <ChartCard title="Eau par Zone (L/jour) · Humidité Sol" icon={BarChart3} iconColor="bg-water-600">
            <ZoneWaterChart zones={farm.zones} />
          </ChartCard>
          <ChartCard title="Rendement vs Énergie par Zone" icon={TrendingUp} iconColor="bg-brand-500">
            <ZoneYieldChart zones={farm.zones} />
          </ChartCard>
        </div>

        {/* Detail table */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="bg-surface border border-line rounded-2xl overflow-hidden qa-card"
        >
          <div className="flex items-center gap-2 px-5 py-3.5 border-b border-line">
            <BarChart3 className="h-4 w-4 text-water-400" />
            <h3 className="text-sm font-bold text-ink">Tableau Comparatif Détaillé des Parcelles</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-sunken text-earth-400 border-b border-line">
                <tr>
                  {['Parcelle', 'Culture', 'Surface', 'Humidité', 'Eau/j', 'Énergie/j', 'Rendement', 'Statut'].map(h => (
                    <th key={h} className="px-4 py-3 font-semibold">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {farm.zones.map((z, i) => {
                  const statusColors: Record<string, string> = {
                    healthy: 'text-brand-400 bg-brand-500/10',
                    warning: 'text-sun-400 bg-sun-500/10',
                    critical: 'text-alert-400 bg-alert-500/10',
                    irrigating: 'text-water-400 bg-water-500/10',
                    nodata: 'text-earth-400 bg-earth-500/10',
                  };
                  return (
                    <motion.tr
                      key={z.id}
                      initial={{ opacity: 0, x: -10 }}
                      whileInView={{ opacity: 1, x: 0 }}
                      viewport={{ once: true }}
                      transition={{ delay: i * 0.07 }}
                      className="hover:bg-raised transition-colors"
                    >
                      <td className="px-4 py-3 font-semibold text-ink">{z.name.split(' - ')[0]}</td>
                      <td className="px-4 py-3 text-earth-300">{z.cropType}</td>
                      <td className="px-4 py-3 font-mono">{z.areaHa} Ha</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5">
                          <div className="h-1.5 w-14 bg-raised rounded-full overflow-hidden">
                            <div className="h-full bg-water-500 rounded-full" style={{ width: `${z.soilMoisturePercent}%` }} />
                          </div>
                          <span className="font-mono font-bold text-water-400">{z.soilMoisturePercent}%</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 font-mono text-water-400">{formatNumber(z.dailyWaterLiters)} L</td>
                      <td className="px-4 py-3 font-mono text-sun-400">{z.dailyEnergyKwh} kWh</td>
                      <td className="px-4 py-3 font-mono font-bold text-brand-400">{z.yieldEstimateTons} T</td>
                      <td className="px-4 py-3">
                        <span className={cn('px-2 py-0.5 rounded-lg text-[10px] font-bold capitalize', statusColors[z.status])}>
                          {z.status}
                        </span>
                      </td>
                    </motion.tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </motion.div>

      </div>
    </AppShell>
  );
}
