'use client';

import React from 'react';
import Link from 'next/link';
import {
  Droplets,
  Sun,
  TrendingUp,
  Cpu,
  ArrowRight,
  Sparkles,
  Clock,
  Play,
  Compass,
  Waves,
  Gauge,
  TrendingDown,
  AlertTriangle,
  CheckCircle2,
  BatteryCharging,
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { useFarmStore } from '@/stores/useFarmStore';
import { DEMO_MARKET_FORECASTS, DEMO_DEVICES, DEMO_ENERGY_TELEMETRY, DEMO_WATER_BASELINE } from '@/lib/mockData';
import { cn, formatNumber, formatCurrencyTND } from '@/lib/utils';
import { GlassCard, ReservoirLevel } from '@/components/ui/glass';
import { AnimatedNumber } from '@/components/ui/AnimatedNumber';
import type { FarmZone } from '@/types';

// Status → fill/stroke for the mini twin (color + label text, never color alone)
const ZONE_TONE: Record<FarmZone['status'], { shape: string; label: string }> = {
  healthy: { shape: 'fill-brand-500/30 stroke-brand-500', label: 'Sain' },
  warning: { shape: 'fill-sun-500/30 stroke-sun-500', label: 'Vigilance' },
  critical: { shape: 'fill-alert-500/35 stroke-alert-500', label: 'Critique' },
  irrigating: { shape: 'fill-water-500/35 stroke-water-500', label: 'Irrigation' },
  nodata: { shape: 'fill-earth-500/20 stroke-earth-500', label: 'Sans donnée' },
};

const MINI_TWIN_SHAPES = [
  { points: '80,80 280,70 270,190 70,180', label: [110, 130] },
  { points: '300,65 520,55 510,180 290,185', label: [330, 120] },
  { points: '300,200 530,195 520,330 310,335', label: [340, 260] },
  { points: '80,200 270,205 280,340 100,345', label: [110, 265] },
] as const;

export default function DashboardPage() {
  const { farm, startIrrigation, emergencyStopActive, isPowerOutage } = useFarmStore();

  // ── Derived metrics (store + mockData, nothing hard-coded in JSX) ──
  const usedLiters = farm.zones.reduce((sum, z) => sum + z.dailyWaterLiters, 0);
  const baselineLiters = DEMO_WATER_BASELINE.classicIrrigationLitersPerDay;
  const savedLiters = Math.max(0, baselineLiters - usedLiters);
  const savedPct = Math.round((savedLiters / baselineLiters) * 100);

  const tankPct = farm.currentTankLevelPercent;
  const tankM3 = (farm.storageTankVolumeM3 * tankPct) / 100;

  const pump = DEMO_DEVICES.find((d) => d.type === 'irrigation_pump');
  const pumpReadings = (pump?.readings ?? {}) as Record<string, number | string>;
  const flowM3H = emergencyStopActive ? 0 : Number(pumpReadings.flowRateM3H ?? 0);
  const dailyPumpedM3 = Number(pumpReadings.dailyPumpingM3 ?? 0);

  const solarKw = DEMO_ENERGY_TELEMETRY.solarProductionKw;
  const batteryPct = DEMO_ENERGY_TELEMETRY.batterySoCPercent;
  const solarSharePct = Math.round((solarKw / farm.solarCapacityKw) * 100);

  const criticalZone = farm.zones.find((z) => z.status === 'critical');
  const activeIrrigationCount = farm.zones.filter((z) => z.irrigationStatus === 'active').length;

  // Sparkline geometry for the 7-day water trend
  const series = DEMO_WATER_BASELINE.last7DaysLiters;
  const max = Math.max(...series, baselineLiters);
  const min = Math.min(...series) * 0.85;
  const sx = (i: number) => (i / (series.length - 1)) * 240;
  const sy = (v: number) => 64 - ((v - min) / (max - min)) * 56;
  const line = series.map((v, i) => `${i === 0 ? 'M' : 'L'}${sx(i).toFixed(1)} ${sy(v).toFixed(1)}`).join(' ');
  const area = `${line} L240 72 L0 72 Z`;
  const baseY = sy(baselineLiters);

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Page header */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div>
            <p className="text-xs text-earth-400">
              <span className="font-mono text-water-400">{farm.governorate} · {farm.delegation}</span>
              <span className="mx-2 text-earth-600">|</span>
              Puits {farm.wellDepthMeters} m · Salinité {formatNumber(farm.waterSalinityGPerL)} g/L
            </p>
            <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-ink mt-1">{farm.name}</h1>
          </div>
          <Link
            href="/farm/map"
            className="qa-shine self-start sm:self-auto px-4 py-2.5 rounded-xl text-on-accent font-semibold text-sm flex items-center gap-2"
          >
            <Compass className="h-4 w-4" />
            <span>Ouvrir le Jumeau Numérique</span>
          </Link>
        </div>

        {/* Hero insight */}
        <section className="qa-card rounded-glass bg-surface border border-line p-6 grid gap-6 md:grid-cols-[1fr_280px] items-center overflow-hidden">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-water-400">Aujourd'hui</p>
            <h2 className="mt-2 text-2xl sm:text-4xl font-black tracking-tight text-ink leading-tight">
              <AnimatedNumber value={savedPct} prefix="−" suffix=" %" className="text-water-400 tabular-nums" /> d'eau
              <span className="text-earth-300 font-semibold"> vs irrigation classique</span>
            </h2>
            <p className="mt-3 text-sm text-earth-300 max-w-xl">
              {formatNumber(usedLiters, 0)} L utilisés au lieu de {formatNumber(baselineLiters, 0)} L : les capteurs d'humidité
              n'ont déclenché l'arrosage que là où le sol en avait besoin.
            </p>
          </div>
          <figure className="w-full">
            <svg viewBox="0 -4 240 80" className="w-full h-24" role="img" aria-label="Consommation d'eau sur 7 jours, en baisse">
              <line x1="0" x2="240" y1={baseY} y2={baseY} className="stroke-earth-500" strokeDasharray="4 4" strokeWidth="1" />
              <text x="0" y={baseY - 4} className="fill-earth-400" fontSize="9">Classique {formatNumber(baselineLiters / 1000)} m³</text>
              <path d={area} className="fill-water-500/15" />
              <path d={line} className="stroke-water-500" fill="none" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
              <circle cx={sx(series.length - 1)} cy={sy(series[series.length - 1])} r="3.5" className="fill-water-500 stroke-surface" strokeWidth="2" />
            </svg>
            <figcaption className="mt-1 flex justify-between text-[11px] text-earth-400">
              <span>J−6</span>
              <span>Consommation réelle · 7 jours</span>
              <span>Auj.</span>
            </figcaption>
          </figure>
        </section>

        {/* KPI glass cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          {/* Water saved */}
          <GlassCard index={0} className="p-5">
            <KpiHeader icon={Droplets} label="Eau économisée (jour)" />
            <p className="mt-4 flex items-baseline gap-1.5">
              <AnimatedNumber value={savedLiters} className="text-3xl font-black tracking-tight text-glass-title tabular-nums" />
              <span className="text-sm font-medium text-glass-label">L</span>
            </p>
            <p className="mt-2 text-xs font-medium text-glass-label flex items-center gap-1.5">
              <TrendingDown className="h-3.5 w-3.5 text-water-400" />
              −{savedPct} % vs {formatNumber(baselineLiters, 0)} L en irrigation classique
            </p>
          </GlassCard>

          {/* Reservoir */}
          <GlassCard index={1} className="p-5">
            <KpiHeader icon={Waves} label="Réservoir tampon" />
            <div className="mt-4 flex items-end gap-4">
              <div className="flex-1">
                <p className="flex items-baseline gap-1.5">
                  <AnimatedNumber value={tankPct} className="text-3xl font-black tracking-tight text-glass-title tabular-nums" />
                  <span className="text-sm font-medium text-glass-label">%</span>
                </p>
                <p className="mt-2 text-xs font-medium text-glass-label tabular-nums">
                  {formatNumber(tankM3, 0)} m³ / {formatNumber(farm.storageTankVolumeM3, 0)} m³
                </p>
              </div>
              <ReservoirLevel percent={tankPct} className="h-16 w-14 flex-shrink-0" />
            </div>
          </GlassCard>

          {/* Flow */}
          <GlassCard index={2} className="p-5">
            <KpiHeader icon={Gauge} label="Débit de pompage" />
            <p className="mt-4 flex items-baseline gap-1.5">
              <AnimatedNumber value={flowM3H} decimals={1} className="text-3xl font-black tracking-tight text-glass-title tabular-nums" />
              <span className="text-sm font-medium text-glass-label">m³/h</span>
            </p>
            <p className={cn('mt-2 text-xs font-medium flex items-center gap-1.5', emergencyStopActive ? 'text-alert-400' : 'text-glass-label')}>
              {emergencyStopActive ? (
                <><AlertTriangle className="h-3.5 w-3.5" /> Pompe arrêtée (arrêt d'urgence)</>
              ) : (
                <><CheckCircle2 className="h-3.5 w-3.5 text-brand-400" /> {formatNumber(dailyPumpedM3)} m³ pompés aujourd'hui</>
              )}
            </p>
          </GlassCard>

          {/* Solar */}
          <GlassCard index={3} className="p-5">
            <KpiHeader icon={Sun} label="Production solaire" />
            <p className="mt-4 flex items-baseline gap-1.5">
              <AnimatedNumber value={solarKw} decimals={1} className="text-3xl font-black tracking-tight text-glass-title tabular-nums" />
              <span className="text-sm font-medium text-glass-label">kW</span>
            </p>
            <div className="mt-2 flex items-center gap-2 text-xs font-medium text-glass-label">
              <BatteryCharging className="h-3.5 w-3.5 text-brand-400 flex-shrink-0" />
              <div className="h-1.5 flex-1 rounded-full bg-earth-800 overflow-hidden">
                <div className="h-full rounded-full bg-water-500 transition-[width] duration-700 ease-out-soft" style={{ width: `${batteryPct}%` }} />
              </div>
              <span className="tabular-nums">{batteryPct} %</span>
            </div>
            <p className="mt-1.5 text-[11px] text-glass-label">
              {isPowerOutage ? 'Réseau coupé : secours solaire actif' : `${solarSharePct} % de la capacité (${formatNumber(farm.solarCapacityKw)} kWc)`}
            </p>
          </GlassCard>
        </div>

        {/* Recommended actions + live mini twin */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <section className="lg:col-span-5 qa-card rounded-glass bg-surface border border-line p-5 flex flex-col">
            <div className="flex items-center gap-2 pb-3 border-b border-line">
              <Sparkles className="h-4 w-4 text-water-400" />
              <h3 className="text-sm font-bold text-ink">Actions recommandées</h3>
            </div>

            <div className="space-y-3 mt-4 flex-1">
              {criticalZone && (
                <div className="p-4 rounded-glass-sm bg-alert-950/60 ring-1 ring-inset ring-alert-500/30 space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[11px] font-bold text-alert-400 uppercase tracking-wide flex items-center gap-1.5">
                      <AlertTriangle className="h-3.5 w-3.5" /> Urgent · {criticalZone.name.split(' - ')[0]}
                    </span>
                    <span className="text-[11px] text-earth-400">Confiance 96 %</span>
                  </div>
                  <p className="text-sm text-earth-200">
                    L'humidité du sol est à {criticalZone.soilMoisturePercent} % (seuil {criticalZone.targetMoistureMin} %).
                    Le solaire couvre la pompe : lancer un cycle de 45 min maintenant.
                  </p>
                  <button
                    onClick={() => startIrrigation(criticalZone.id)}
                    disabled={emergencyStopActive}
                    className="w-full py-2 rounded-xl bg-accent hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed text-on-accent font-semibold text-xs flex items-center justify-center gap-1.5 transition-colors"
                  >
                    <Play className="h-3 w-3 fill-current" />
                    <span>Lancer l'irrigation solaire</span>
                  </button>
                </div>
              )}

              <div className="p-4 rounded-glass-sm bg-raised ring-1 ring-inset ring-line space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold text-water-400 uppercase tracking-wide">Opportunité commerciale</span>
                  <span className="text-[11px] text-earth-400">Marché de gros</span>
                </div>
                <p className="text-sm text-earth-200">
                  Déficit national projeté de 29 % sur le piment Baklouti. Prix attendu à 4,200 TND/kg au premier trimestre 2027.
                </p>
                <Link href="/intelligence/forecast" className="text-xs text-water-400 font-semibold hover:underline inline-flex items-center gap-1 pt-1">
                  Voir l'analyse des cours <ArrowRight className="h-3 w-3 rtl:rotate-180" />
                </Link>
              </div>
            </div>

            <div className="pt-4 border-t border-line mt-4 flex justify-between items-center text-xs">
              <span className="text-earth-400">Philosophie Mottainai active</span>
              <span className="text-water-400 font-semibold">Zéro goutte perdue</span>
            </div>
          </section>

          <section className="lg:col-span-7 qa-card rounded-glass bg-surface border border-line p-5 flex flex-col">
            <div className="flex items-center justify-between pb-3 border-b border-line">
              <div className="flex items-center gap-2">
                <span className="qa-live-dot !bg-water-500" />
                <h3 className="text-sm font-bold text-ink">Jumeau numérique en direct</h3>
              </div>
              <Link href="/farm/map" className="text-xs text-water-400 hover:underline flex items-center gap-1">
                Plein écran <ArrowRight className="h-3.5 w-3.5 rtl:rotate-180" />
              </Link>
            </div>

            <Link
              href="/farm/map"
              className="my-4 h-64 rounded-glass-sm bg-sunken ring-1 ring-inset ring-line relative overflow-hidden group block"
              aria-label="Ouvrir le jumeau numérique"
            >
              <div className="absolute inset-0 qa-grid-bg opacity-70" />
              <svg viewBox="55 45 490 310" className="relative w-full h-full p-2">
                {MINI_TWIN_SHAPES.map((shape, i) => {
                  const zone = farm.zones[i];
                  if (!zone) return null;
                  const tone = ZONE_TONE[zone.status];
                  return (
                    <g key={zone.id}>
                      <polygon points={shape.points} className={cn(tone.shape, 'transition-colors duration-500')} strokeWidth="1.5" />
                      <text x={shape.label[0]} y={shape.label[1]} className="fill-ink" fontSize="17" fontWeight="700">
                        {zone.cropType.split(' ')[0]}
                      </text>
                      <text x={shape.label[0]} y={shape.label[1] + 22} className="fill-earth-300" fontSize="14">
                        {zone.soilMoisturePercent} % · {tone.label}
                      </text>
                    </g>
                  );
                })}
                <circle cx="285" cy="195" r="8" className="fill-water-500 stroke-surface" strokeWidth="2" />
              </svg>
              <span className="absolute bottom-3 end-3 px-3 py-1.5 rounded-xl glass-panel text-xs font-semibold text-ink flex items-center gap-1.5 opacity-0 translate-y-1 group-hover:opacity-100 group-hover:translate-y-0 transition-all duration-300 ease-out-soft">
                Interagir avec le jumeau <ArrowRight className="h-3.5 w-3.5 rtl:rotate-180" />
              </span>
            </Link>

            <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-earth-400">
              <span>{activeIrrigationCount} vanne{activeIrrigationCount > 1 ? 's' : ''} d'irrigation ouverte{activeIrrigationCount > 1 ? 's' : ''}</span>
              <span className="text-earth-300 font-medium">Passerelle ESP32-S3 connectée (LoRa 868 MHz)</span>
            </div>
          </section>
        </div>

        {/* Market signals + live journal */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <section className="lg:col-span-6 qa-card rounded-glass bg-surface border border-line p-5">
            <div className="flex items-center justify-between pb-3 border-b border-line">
              <div className="flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-water-400" />
                <h3 className="text-sm font-bold text-ink">Signaux de marché & pénuries</h3>
              </div>
              <Link href="/intelligence" className="text-xs text-water-400 hover:underline">Observatoire complet</Link>
            </div>

            <div className="divide-y divide-line mt-1">
              {DEMO_MARKET_FORECASTS.slice(0, 3).map((item) => {
                const deficit = item.balanceStatus.includes('Déficit');
                const surplus = item.balanceStatus.includes('Surproduction');
                return (
                  <div key={item.id} className="py-3 flex items-center justify-between gap-3 text-xs">
                    <div className="min-w-0">
                      <p className="font-bold text-ink truncate">{item.cropName}</p>
                      <p className="text-[11px] text-earth-400 mt-0.5">{item.season}</p>
                    </div>
                    <div className="text-end flex-shrink-0">
                      <span
                        className={cn(
                          'px-2 py-0.5 rounded-md text-[11px] font-semibold inline-block',
                          deficit ? 'bg-water-500/10 text-water-400' : surplus ? 'bg-alert-500/10 text-alert-400' : 'bg-earth-800 text-earth-300'
                        )}
                      >
                        {item.balanceStatus.split(' ')[0]}
                      </span>
                      <span className="text-xs font-mono font-bold text-ink mt-1 block tabular-nums">
                        {formatCurrencyTND(item.projectedPriceTnd)}/kg
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          <section className="lg:col-span-6 qa-card rounded-glass bg-surface border border-line p-5">
            <div className="flex items-center justify-between pb-3 border-b border-line">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-water-400" />
                <h3 className="text-sm font-bold text-ink">Journal des événements</h3>
              </div>
              <span className="text-[11px] text-earth-400">Mise à jour en direct</span>
            </div>

            <ul className="space-y-2 mt-3 text-xs">
              <JournalItem
                icon={Droplets}
                title="Cycle d'arrosage Zone E (Luzerne) en cours"
                detail={`Débit : ${formatNumber(Number(pumpReadings.flowRateM3H ?? 0))} m³/h via la pompe solaire submersible`}
                time="14:15"
              />
              <JournalItem
                icon={Sun}
                title="Pic de production photovoltaïque atteint"
                detail={`${formatNumber(solarKw)} kW produits · ${DEMO_ENERGY_TELEMETRY.gridImportKw === 0 ? '100 % autoconsommation, sans recours STEG' : 'appoint réseau STEG'}`}
                time="12:30"
              />
              <JournalItem
                icon={Cpu}
                title="Ping passerelle ESP32 centrale"
                detail={`${DEMO_DEVICES.filter((d) => d.status === 'online').length} appareils en ligne · signal LoRa −58 dBm`}
                time="Il y a 30 s"
              />
            </ul>
          </section>
        </div>
      </div>
    </AppShell>
  );
}

function KpiHeader({ icon: Icon, label }: { icon: React.ElementType; label: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-xs font-semibold text-glass-label">{label}</span>
      <span className="h-9 w-9 rounded-glass-sm bg-white/50 dark:bg-white/10 ring-1 ring-inset ring-white/60 dark:ring-white/10 flex items-center justify-center text-water-400">
        <Icon className="h-4 w-4" />
      </span>
    </div>
  );
}

function JournalItem({ icon: Icon, title, detail, time }: { icon: React.ElementType; title: string; detail: string; time: string }) {
  return (
    <li className="flex items-start gap-3 p-3 rounded-glass-sm bg-sunken ring-1 ring-inset ring-line">
      <span className="h-7 w-7 rounded-full bg-water-500/10 flex items-center justify-center text-water-400 flex-shrink-0">
        <Icon className="h-3.5 w-3.5" />
      </span>
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-ink">{title}</p>
        <p className="text-[11px] text-earth-400 mt-0.5">{detail}</p>
      </div>
      <span className="text-[11px] text-earth-400 font-mono flex-shrink-0">{time}</span>
    </li>
  );
}
