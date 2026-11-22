'use client';

import React, { useMemo, useState } from 'react';
import Link from 'next/link';
import {
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  Brain,
  ArrowRight,
  ShieldAlert,
  Coins
  ,Waves, Sprout, Activity
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { DEMO_MARKET_FORECASTS } from '@/lib/mockData';
import { cn, formatNumber, formatCurrencyTND } from '@/lib/utils';
import { useFarmStore } from '@/stores/useFarmStore';

export default function ForecastPage() {
  const { farm } = useFarmStore();
  const [selectedId, setSelectedId] = useState(DEMO_MARKET_FORECASTS[0].id);
  const selected = DEMO_MARKET_FORECASTS.find((item) => item.id === selectedId) ?? DEMO_MARKET_FORECASTS[0];
  const soilTypes = Array.from(new Set(farm.zones.map((zone) => zone.soilType))).filter(Boolean);
  const dominantSoil = soilTypes[0] ?? 'Sablo-limoneux';
  const soilFit = soilCompatibility(selected.cropName, dominantSoil);

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-line gap-4">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-brand-400">
              Modélisation Prédictive & Économique
            </span>
            <h1 className="text-2xl font-black text-ink">Prévisions de l'Offre & de la Demande Nationale</h1>
            <p className="text-xs text-earth-400 mt-0.5">
              Anticipation des déséquilibres de marché pour protéger les revenus agricoles tunisiens
            </p>
          </div>

          <Link
            href="/planning"
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-accent to-accent-deep hover:from-accent-hover text-on-accent font-bold text-xs flex items-center gap-2 border border-brand-500/30 qa-shine"
          >
            <Brain className="h-4 w-4" />
            <span>Planifier mes Prochaines Cultures avec l'IA</span>
          </Link>
        </div>

        <section className="rounded-2xl border border-water-500/25 bg-surface p-4 shadow-xl overflow-hidden">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider text-water-400"><Activity className="h-3.5 w-3.5" /> Courbe magique du marché</p>
              <h2 className="mt-1 text-base font-black text-ink">Offre, demande et prix évoluent ensemble</h2>
              <p className="mt-0.5 text-[11px] text-earth-400">Cliquez sur une culture pour animer sa trajectoire économique.</p>
            </div>
            <div className="flex items-center gap-3 text-[10px] font-semibold text-earth-400"><span className="flex items-center gap-1.5"><i className="h-2 w-6 rounded-full bg-water-400" /> Demande</span><span className="flex items-center gap-1.5"><i className="h-2 w-6 rounded-full bg-brand-400" /> Offre</span><span className="flex items-center gap-1.5"><i className="h-2 w-6 rounded-full bg-sun-400" /> Prix</span></div>
          </div>
          <MarketCurve forecast={selected} />
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded-lg bg-brand-500/5 px-3 py-2 text-[10px]">
            <span className="flex items-center gap-1.5 text-earth-300"><Sprout className="h-3.5 w-3.5 text-brand-400" /> Sol dominant détecté : <strong className="text-ink">{dominantSoil}</strong></span>
            <span className={cn('font-bold', soilFit >= 80 ? 'text-brand-400' : soilFit >= 60 ? 'text-sun-400' : 'text-alert-400')}>Adéquation sol : {soilFit}/100</span>
          </div>
        </section>

        {/* Forecasts List */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {DEMO_MARKET_FORECASTS.map((item) => {
            const isDeficit = item.balanceStatus.includes('Déficit');
            const isSurplus = item.balanceStatus.includes('Surproduction');

            return (
              <div
                key={item.id}
                onClick={() => setSelectedId(item.id)}
                className={cn(
                  "p-5 rounded-2xl border bg-surface flex flex-col justify-between space-y-4 shadow-xl cursor-pointer transition-all hover:-translate-y-1",
                  selectedId === item.id && "ring-2 ring-water-400/40 -translate-y-1",
                  isDeficit && "border-brand-500/40 bg-brand-950/10",
                  isSurplus && "border-alert-500/40 bg-alert-950/10",
                  !isDeficit && !isSurplus && "border-line"
                )}
              >
                <div>
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="text-[10px] font-mono text-earth-400 uppercase tracking-wider">
                        {item.category} · {item.season}
                      </span>
                      <h3 className="text-lg font-bold text-ink mt-0.5">{item.cropName}</h3>
                    </div>
                    <span
                      className={cn(
                        "px-2.5 py-1 text-xs font-bold rounded-lg border",
                        isDeficit && "bg-brand-500/20 text-brand-300 border-brand-500/30",
                        isSurplus && "bg-alert-500/20 text-alert-300 border-alert-500/30",
                        !isDeficit && !isSurplus && "bg-earth-800 text-earth-300 border-earth-700"
                      )}
                    >
                      {item.balanceStatus}
                    </span>
                  </div>

                  <p className="text-xs text-earth-300 mt-3 leading-relaxed">
                    {item.driverInsights}
                  </p>
                </div>

                <div className="bg-sunken p-3 rounded-xl border border-line grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <span className="text-[10px] text-earth-500">Demande Nationale</span>
                    <p className="font-mono font-bold text-ink mt-0.5">{formatNumber(item.nationalDemandTons)} T</p>
                  </div>
                  <div>
                    <span className="text-[10px] text-earth-500">Offre Projetée</span>
                    <p className="font-mono font-bold text-ink mt-0.5">{formatNumber(item.projectedSupplyTons)} T</p>
                  </div>
                  <div>
                    <span className="text-[10px] text-earth-500">Prix Attendu</span>
                    <p className="font-mono font-bold text-sun-300 mt-0.5">{formatCurrencyTND(item.projectedPriceTnd)}/kg</p>
                  </div>
                </div>

                <div className="flex items-center justify-between text-[11px] text-earth-400 pt-2 border-t border-line">
                  <span>Gouvernorats clés : {item.topProducingGovernorates.join(', ')}</span>
                  <span className="text-brand-400 font-mono">Indice Confiance {item.confidenceScore}%</span>
                </div>
                <div className="flex items-center justify-between rounded-lg bg-brand-500/5 px-2.5 py-2 text-[10px]">
                  <span className="flex items-center gap-1.5 text-earth-400"><Waves className="h-3 w-3 text-water-400" /> Sol : {soilCompatibility(item.cropName, dominantSoil)}/100</span>
                  <span className="font-semibold text-water-400">Voir la courbe →</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </AppShell>
  );
}

function soilCompatibility(cropName: string, soilType: string) {
  const soil = soilType.toLowerCase();
  const crop = cropName.toLowerCase();
  if (soil.includes('sablo') && (crop.includes('piment') || crop.includes('grenad') || crop.includes('fenouil'))) return crop.includes('piment') ? 96 : 88;
  if (soil.includes('argil') && crop.includes('past')) return 74;
  if (soil.includes('limon')) return crop.includes('past') ? 68 : 84;
  return 70;
}

function MarketCurve({ forecast }: { forecast: typeof DEMO_MARKET_FORECASTS[number] }) {
  const width = 900;
  const height = 220;
  const pad = { left: 28, right: 22, top: 18, bottom: 28 };
  const months = ['Nov', 'Déc', 'Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Août'];
  const demand = months.map((_, i) => forecast.nationalDemandTons * (0.86 + Math.sin(i * 0.65) * 0.045 + i * 0.012));
  const supply = months.map((_, i) => forecast.projectedSupplyTons * (0.82 + i * 0.024 + Math.cos(i * 0.72) * 0.035));
  const max = Math.max(...demand, ...supply) * 1.06;
  const x = (i: number) => pad.left + (i * (width - pad.left - pad.right)) / (months.length - 1);
  const y = (value: number) => pad.top + (1 - value / max) * (height - pad.top - pad.bottom);
  const path = (values: number[]) => values.map((value, i) => `${i ? 'L' : 'M'} ${x(i).toFixed(1)} ${y(value).toFixed(1)}`).join(' ');
  return <div className="relative mt-3 h-[230px] overflow-hidden rounded-xl border border-line bg-[#e9f7f6] dark:bg-[#08252b]">
    <div className="absolute inset-0 opacity-30" style={{ backgroundImage: 'linear-gradient(rgba(35,117,132,.18) 1px, transparent 1px), linear-gradient(90deg, rgba(35,117,132,.14) 1px, transparent 1px)', backgroundSize: '10% 25%' }} />
    <svg viewBox={`0 0 ${width} ${height}`} className="relative h-full w-full" role="img" aria-label={`Courbes de marché pour ${forecast.cropName}`}>
      <defs><linearGradient id="curveGlow" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#29b9ca" stopOpacity=".24" /><stop offset="1" stopColor="#29b9ca" stopOpacity="0" /></linearGradient></defs>
      <path d={`${path(demand)} L ${x(demand.length - 1)} ${height - pad.bottom} L ${x(0)} ${height - pad.bottom} Z`} fill="url(#curveGlow)" />
      <path d={path(demand)} fill="none" stroke="#29b9ca" strokeWidth="4" strokeLinecap="round" className="qa-chart-line" />
      <path d={path(supply)} fill="none" stroke="#4dbf98" strokeWidth="4" strokeLinecap="round" className="qa-chart-line qa-chart-line-delay" />
      {months.map((month, i) => <g key={month}><circle cx={x(i)} cy={y(demand[i])} r="4" fill="#29b9ca" stroke="#e9f7f6" strokeWidth="2" /><circle cx={x(i)} cy={y(supply[i])} r="4" fill="#4dbf98" stroke="#e9f7f6" strokeWidth="2" /><text x={x(i)} y={height - 8} textAnchor="middle" fontSize="11" fill="currentColor" opacity=".62">{month}</text></g>)}
    </svg>
    <div className="absolute right-3 top-3 rounded-lg bg-surface/80 px-2 py-1 text-[10px] font-bold text-sun-400 backdrop-blur">Prix attendu : {formatCurrencyTND(forecast.projectedPriceTnd)}/kg</div>
  </div>;
}
