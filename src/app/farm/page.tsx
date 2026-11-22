'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import {
  Layers,
  Droplets,
  Sun,
  MapPin,
  Compass,
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
  Play
  ,Satellite, X, CalendarDays, Cloud, TrendingUp
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { useFarmStore } from '@/stores/useFarmStore';
import { cn, formatNumber, formatCurrencyTND } from '@/lib/utils';
import type { Farm } from '@/types';

export default function FarmPage() {
  const { farm, selectZone, startIrrigation } = useFarmStore();
  const [selectedZoneId, setSelectedZoneId] = useState<string | null>(null);
  const selectedZone = farm.zones.find((zone) => zone.id === selectedZoneId) ?? null;

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-line gap-4">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-brand-400">
              Gestion de l'Exploitation
            </span>
            <h1 className="text-2xl font-black text-ink">{farm.name}</h1>
            <p className="text-xs text-earth-400 mt-0.5">
              {farm.governorate} ({farm.delegation}) · {farm.totalAreaHa} Hectares au total
            </p>
          </div>

          <Link
            href="/farm/map"
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-accent to-accent-deep hover:from-accent-hover hover:to-accent-deep text-on-accent font-bold text-xs flex items-center gap-2 border border-brand-500/30 qa-shine"
          >
            <Compass className="h-4 w-4" />
            <span>Basculer sur le Jumeau Numérique (Map)</span>
          </Link>
        </div>

        {/* Zones List Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {farm.zones.map((zone) => {
            const isCritical = zone.status === 'critical';
            const isIrrigating = zone.status === 'irrigating';

            return (
              <div
                key={zone.id}
                onClick={() => setSelectedZoneId(zone.id)}
                role="button"
                tabIndex={0}
                onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') setSelectedZoneId(zone.id); }}
                className={cn(
                  "p-5 rounded-2xl border transition-all flex flex-col justify-between bg-surface cursor-pointer hover:-translate-y-0.5 hover:border-water-500/50",
                  isCritical ? "border-alert-500/40 bg-alert-950/10 shadow-lg shadow-shade/20" : "border-line",
                  isIrrigating && "border-water-500/40 bg-water-950/10"
                )}
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono font-bold text-earth-400">{zone.areaHa} Ha</span>
                    <span
                      className={cn(
                        "px-2.5 py-0.5 rounded-full text-[11px] font-bold capitalize border",
                        zone.status === 'healthy' && "bg-brand-500/20 text-brand-300 border-brand-500/30",
                        zone.status === 'warning' && "bg-sun-500/20 text-sun-300 border-sun-500/30",
                        zone.status === 'critical' && "bg-alert-500/20 text-alert-300 border-alert-500/30 animate-pulse",
                        zone.status === 'irrigating' && "bg-water-500/20 text-water-300 border-water-500/30"
                      )}
                    >
                      {isIrrigating ? 'Arrosage Actif' : zone.status}
                    </span>
                  </div>

                  <h3 className="text-lg font-bold text-ink mt-2">{zone.name}</h3>
                  <p className="text-xs text-brand-400 font-medium">{zone.cropType} ({zone.variety})</p>

                  <div className="grid grid-cols-2 gap-2 mt-4 text-xs">
                    <div className="bg-sunken p-2.5 rounded-xl border border-line">
                      <span className="text-[10px] text-earth-400">Humidité Sol</span>
                      <p className="text-base font-black text-ink mt-0.5">{zone.soilMoisturePercent}%</p>
                    </div>

                    <div className="bg-sunken p-2.5 rounded-xl border border-line">
                      <span className="text-[10px] text-earth-400">Température</span>
                      <p className="text-base font-black text-ink mt-0.5">{zone.temperatureC}°C</p>
                    </div>
                  </div>

                  <div className="mt-4 space-y-1.5 text-xs text-earth-300">
                    <div className="flex justify-between">
                      <span className="text-earth-500">Irrigation :</span>
                      <span>{zone.irrigationMethod}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-earth-500">Sol :</span>
                      <span className="truncate max-w-[150px]">{zone.soilType}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-earth-500">Récolte estimée :</span>
                      <span className="font-semibold text-brand-400">{zone.predictedHarvestDate}</span>
                    </div>
                  </div>
                </div>

                <div className="pt-4 border-t border-line mt-4 flex items-center justify-between gap-2">
                  <Link
                    href={`/farm/zones/${zone.id}`}
                    className="text-xs font-semibold text-brand-400 hover:text-brand-300 flex items-center gap-1"
                  >
                    <span>Détails & Capteurs</span>
                    <ArrowRight className="h-3 w-3" />
                  </Link>

                  {zone.status === 'critical' && (
                    <button
                      onClick={() => startIrrigation(zone.id)}
                      className="px-3 py-1 rounded-lg bg-alert-600 hover:bg-alert-500 text-on-accent font-bold text-[11px] flex items-center gap-1"
                    >
                      <Play className="h-3 w-3 fill-current" />
                      <span>Arroser</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {selectedZone && <SatelliteCapturePanel zone={selectedZone} onClose={() => setSelectedZoneId(null)} />}
      </div>
    </AppShell>
  );
}

function SatelliteCapturePanel({ zone, onClose }: { zone: Farm['zones'][number]; onClose: () => void }) {
  const growth = Math.max(0, Math.min(100, Math.round(zone.soilMoisturePercent * 0.72 + (zone.status === 'critical' ? 8 : 20))));
  const ndvi = (0.42 + growth / 250).toFixed(2);
  const nextCapture = zone.status === 'critical' ? 'dans 4 jours' : 'dans 5 jours';
  const health = zone.status === 'critical' ? 'Stress détecté' : zone.status === 'irrigating' ? 'Évolution à surveiller' : 'Croissance stable';
  const points = [Math.max(18, growth - 18), Math.max(25, growth - 10), Math.max(32, growth - 4), growth].map((value, index) => `${index * 31 + 8},${88 - value * 0.62}`).join(' ');

  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#061d24]/55 p-4 backdrop-blur-sm" onClick={onClose}>
    <section className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-water-500/30 bg-surface shadow-2xl" onClick={(event) => event.stopPropagation()}>
      <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4"><div><p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider text-water-400"><Satellite className="h-3.5 w-3.5" /> Capture satellite · Sentinel-2</p><h2 className="mt-1 text-lg font-black text-ink">{zone.name}</h2><p className="mt-1 text-xs text-earth-400">Suivi de croissance par images multispectrales de la parcelle.</p></div><button onClick={onClose} className="rounded-lg p-2 text-earth-400 hover:bg-raised hover:text-ink" aria-label="Fermer"><X className="h-4 w-4" /></button></div>
      <div className="grid gap-4 p-5 lg:grid-cols-[1.1fr_.9fr]">
        <div className="rounded-xl border border-line bg-[#d5e7d7] p-3"><div className="relative h-56 overflow-hidden rounded-lg bg-[linear-gradient(135deg,#8cad72_0%,#d6c58e_42%,#739d75_43%,#b4c98a_68%,#789e72_69%)]"><div className="absolute inset-5 rotate-[-7deg] rounded-[35%] border-2 border-white/70 bg-emerald-500/10" /><div className="absolute inset-x-12 bottom-10 h-20 rotate-[8deg] rounded-[30%] border-2 border-white/60 bg-lime-300/20" /><div className="absolute left-3 top-3 rounded-md bg-[#06252b]/85 px-2 py-1 text-[9px] font-semibold text-white">Image reçue · 18 nov. 2026</div><div className="absolute bottom-3 right-3 rounded-md bg-white/85 px-2 py-1 text-[9px] font-bold text-[#16424b]">NDVI {ndvi}</div></div><div className="mt-3 flex items-center justify-between text-[10px] text-earth-500"><span>Résolution 10 m · couverture nuageuse 8%</span><span className="font-semibold text-brand-400">Capture exploitable</span></div></div>
        <div className="space-y-3"><div className="grid grid-cols-2 gap-2"><Metric icon={CalendarDays} label="Dernière capture" value="18 nov. 2026" /><Metric icon={Satellite} label="Prochaine capture" value={nextCapture} /><Metric icon={TrendingUp} label="Croissance" value={`${growth}%`} tone="success" /><Metric icon={Cloud} label="Qualité image" value="Bonne · 8% nuages" /></div><div className="rounded-xl border border-line bg-raised p-3"><div className="flex items-center justify-between"><p className="text-xs font-bold text-ink">Évolution observée</p><span className="text-[10px] font-semibold text-brand-400">{health}</span></div><svg viewBox="0 0 110 92" className="mt-2 h-24 w-full"><path d="M 8 88 L 102 88" stroke="currentColor" strokeOpacity=".15" /><polyline points={points} fill="none" stroke={zone.status === 'critical' ? '#EE7B6B' : '#4DBF98'} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />{points.split(' ').map((point) => { const [cx, cy] = point.split(','); return <circle key={point} cx={cx} cy={cy} r="3" fill={zone.status === 'critical' ? '#EE7B6B' : '#4DBF98'} />; })}</svg><p className="text-[10px] leading-4 text-earth-400">Le système compare chaque nouvelle capture avec les précédentes pour repérer densité végétale, stress et progression de la culture.</p></div></div>
      </div>
      <div className="border-t border-line bg-raised/60 px-5 py-3 text-[10px] text-earth-400"><strong className="text-ink">Prochaine analyse :</strong> l’image est vérifiée dès sa disponibilité, puis comparée aux capteurs sol, à la météo et à l’historique d’irrigation. Intervalle attendu : 4 à 5 jours selon la couverture nuageuse.</div>
    </section>
  </div>;
}

function Metric({ icon: Icon, label, value, tone = 'default' }: { icon: React.ElementType; label: string; value: string; tone?: 'default' | 'success' }) {
  return <div className="rounded-lg border border-line bg-raised p-2.5"><div className="flex items-center gap-1 text-[9px] text-earth-500"><Icon className="h-3 w-3 text-water-400" />{label}</div><p className={cn('mt-1 text-[11px] font-bold', tone === 'success' ? 'text-brand-400' : 'text-ink')}>{value}</p></div>;
}
