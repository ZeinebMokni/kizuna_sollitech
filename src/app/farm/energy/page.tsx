'use client';

import React, { useEffect, useState } from 'react';
import {
  Sun,
  BatteryCharging,
  Zap,
  Power,
  TrendingUp,
  Activity,
  ShieldCheck,
  AlertTriangle,
  Clock,
  Sparkles
  ,ArrowDown, ArrowUpRight, Droplets, Gauge
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { useFarmStore } from '@/stores/useFarmStore';
import { DEMO_HOURLY_ENERGY, DEMO_ENERGY_TELEMETRY } from '@/lib/mockData';
import { cn } from '@/lib/utils';

export default function EnergyPage() {
  const { farm, isPowerOutage, togglePowerOutage } = useFarmStore();
  const [liveStep, setLiveStep] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => setLiveStep((value) => value + 1), 5000);
    return () => window.clearInterval(timer);
  }, []);
  const solarKw = Math.max(0, DEMO_ENERGY_TELEMETRY.solarProductionKw + ((liveStep % 3) - 1) * 0.2);
  const usageKw = DEMO_ENERGY_TELEMETRY.pumpConsumptionKw + DEMO_ENERGY_TELEMETRY.auxiliaryConsumptionKw;
  const batteryChargeKw = Math.max(0, DEMO_ENERGY_TELEMETRY.batteryPowerKw);
  const exportKw = isPowerOutage ? 0 : Math.max(0, solarKw - usageKw - batteryChargeKw);
  const deficitKw = Math.max(0, usageKw + batteryChargeKw - solarKw);

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-line gap-4">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-brand-400">
              Autonomie Énergétique & Décarbonation
            </span>
            <h1 className="text-2xl font-black text-ink">Supervision Énergie & Micro-Réseau Solaire</h1>
            <p className="text-xs text-earth-400 mt-0.5">
              Centrale Photovoltaïque 18.5 kWp · Stockage LiFePO4 24 kWh · Pilotage de Charge Dynamique
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* Outage simulation trigger */}
            <button
              onClick={togglePowerOutage}
              className={cn(
                "px-4 py-2 rounded-xl text-xs font-bold border transition-all flex items-center gap-2",
                isPowerOutage
                  ? "bg-sun-600/30 border-sun-500 text-sun-300 animate-pulse"
                  : "bg-earth-800 border-earth-700 text-earth-300 hover:text-ink"
              )}
            >
              <Power className="h-4 w-4" />
              <span>{isPowerOutage ? 'Réseau STEG COUPÉ (Îlotage Actif)' : 'Simuler Coupure Réseau STEG'}</span>
            </button>
          </div>
        </div>

        {/* Live Power Flow Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-surface p-5 rounded-2xl border border-line shadow-md qa-card">
            <span className="text-xs text-earth-400 flex items-center gap-1.5">
              <Sun className="h-4 w-4 text-sun-400" /> Production Solaire (Live)
            </span>
            <p className="text-3xl font-black text-sun-400 mt-2">
              {DEMO_ENERGY_TELEMETRY.solarProductionKw} <span className="text-sm font-normal text-earth-400">kW</span>
            </p>
            <span className="text-[10px] text-brand-400">Rendement onduleur : 97.4%</span>
          </div>

          <div className="bg-surface p-5 rounded-2xl border border-line shadow-md qa-card">
            <span className="text-xs text-earth-400 flex items-center gap-1.5">
              <Activity className="h-4 w-4 text-water-400" /> Charge Pompe Forage
            </span>
            <p className="text-3xl font-black text-water-300 mt-2">
              {DEMO_ENERGY_TELEMETRY.pumpConsumptionKw} <span className="text-sm font-normal text-earth-400">kW</span>
            </p>
            <span className="text-[10px] text-earth-400">Variateur de fréquence 48.5 Hz</span>
          </div>

          <div className="bg-surface p-5 rounded-2xl border border-line shadow-md qa-card">
            <span className="text-xs text-earth-400 flex items-center gap-1.5">
              <BatteryCharging className="h-4 w-4 text-brand-400" /> Stockage Batterie LiFePO4
            </span>
            <p className="text-3xl font-black text-brand-400 mt-2">
              {DEMO_ENERGY_TELEMETRY.batterySoCPercent}%
            </p>
            <span className="text-[10px] text-brand-300">+4.5 kW en cours de charge</span>
          </div>

          <div className="bg-surface p-5 rounded-2xl border border-line shadow-md qa-card">
            <span className="text-xs text-earth-400 flex items-center gap-1.5">
              <Zap className="h-4 w-4 text-earth-300" /> Réseau National (STEG)
            </span>
            <p className={cn(
              "text-3xl font-black mt-2",
              isPowerOutage ? "text-sun-400" : "text-ink"
            )}>
              {isPowerOutage ? "Hors Ligne" : "0.0 kW"}
            </p>
            <span className="text-[10px] text-brand-400">
              {isPowerOutage ? "100% Autonomie par Solaire & Batterie" : "Autoconsommation pure (Zéro facture)"}
            </span>
          </div>
        </div>

        {/* Resilience Banner during Power Outage */}
        {isPowerOutage && (
          <div className="bg-sun-950/40 border border-sun-500/50 p-4 rounded-2xl flex items-start gap-3 text-xs shadow-xl">
            <AlertTriangle className="h-5 w-5 text-sun-400 flex-shrink-0 mt-0.5 animate-pulse" />
            <div>
              <p className="font-bold text-sun-200">Mode Îloté Automatique Activé (Zero-Blackout Architecture)</p>
              <p className="text-sun-300/80 mt-1 leading-relaxed">
                Le réseau électrique public est déconnecté. QATRA a automatiquement basculé l'alimentation des pompes submersibles sur la génération solaire hybride et la réserve batterie de 24 kWh. Les cultures continuent d'être irriguées sans perturbation.
              </p>
            </div>
          </div>
        )}

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_250px]">
          <EnergyFlow3D solarKw={solarKw} usageKw={usageKw} batteryChargeKw={batteryChargeKw} exportKw={exportKw} deficitKw={deficitKw} isPowerOutage={isPowerOutage} />
          <EnergyNextSteps waterLiters={farm.zones.reduce((total, zone) => total + zone.dailyWaterLiters, 0)} usageKw={usageKw} exportKw={exportKw} />
        </div>

        {/* 24h Hourly Profile */}
        <div className="bg-surface border border-line rounded-2xl p-6 shadow-xl qa-card">
          <h3 className="text-base font-bold text-ink mb-4">Profil Énergétique Journalier (Production vs Pompage)</h3>
          
          <div className="grid grid-cols-4 sm:grid-cols-8 gap-3">
            {DEMO_HOURLY_ENERGY.map((h, i) => (
              <div key={i} className="bg-sunken p-3 rounded-xl border border-line text-center">
                <span className="text-[10px] font-mono text-earth-400 block mb-1">{h.hour}</span>
                <p className="text-xs font-bold text-sun-400">{h.solarKw} kW</p>
                <p className="text-[10px] font-semibold text-water-400 mt-0.5">
                  {h.pumpKw > 0 ? `${h.pumpKw} kW` : 'Veille'}
                </p>
                <div className="mt-2 text-[9px] text-earth-500">SoC {h.batterySoC}%</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}

function EnergyFlow3D({ solarKw, usageKw, batteryChargeKw, exportKw, deficitKw, isPowerOutage }: { solarKw: number; usageKw: number; batteryChargeKw: number; exportKw: number; deficitKw: number; isPowerOutage: boolean }) {
  return <section className="overflow-hidden rounded-2xl border border-line bg-surface p-4 shadow-xl"><div className="flex items-center justify-between gap-2"><div><p className="text-[10px] font-bold uppercase tracking-wider text-brand-400">Flux énergétique 3D</p><h2 className="mt-1 text-sm font-bold text-ink">Production → usage → stockage → export</h2></div><span className="rounded-full bg-brand-500/10 px-2 py-1 text-[10px] font-semibold text-brand-400">Live</span></div><div className="mt-3 grid gap-2 sm:grid-cols-5"><EnergyNumber icon={Sun} label="Produit" value={`${solarKw.toFixed(1)} kW`} color="sun" /><EnergyNumber icon={Activity} label="Utilisé" value={`${usageKw.toFixed(1)} kW`} color="water" /><EnergyNumber icon={BatteryCharging} label="Batterie" value={`${batteryChargeKw.toFixed(1)} kW`} color="green" /><EnergyNumber icon={ArrowUpRight} label="Exporté" value={`${exportKw.toFixed(1)} kW`} color="gold" /><EnergyNumber icon={Zap} label="Reste / manque" value={deficitKw ? `-${deficitKw.toFixed(1)} kW` : '0.0 kW'} color={deficitKw ? 'red' : 'green'} /></div><div className="relative mt-4 h-[285px] overflow-hidden rounded-xl border border-line bg-[#e9f4f4] [perspective:900px]"><div className="absolute inset-0 opacity-40" style={{ backgroundImage: 'linear-gradient(rgba(35,117,132,.16) 1px, transparent 1px), linear-gradient(90deg, rgba(35,117,132,.16) 1px, transparent 1px)', backgroundSize: '34px 34px' }} /><div className="absolute left-1/2 top-1/2 h-48 w-[90%] -translate-x-1/2 -translate-y-1/2 rotate-x-[58deg] rotate-z-[-8deg] rounded-[25%] border-2 border-water-400/40 bg-water-400/5 shadow-[0_25px_35px_rgba(18,86,96,.18)]" /><div className="absolute inset-x-0 top-1/2 h-px bg-water-400/30" /><div className="absolute left-1/2 top-1/2 h-px w-[70%] -translate-x-1/2 bg-sun-400/70" /><FlowNode className="left-[7%] top-[31%]" icon={Sun} title="PV 18.5 kWp" value={`${solarKw.toFixed(1)} kW`} tone="sun" /><FlowNode className="left-[39%] top-[16%]" icon={Zap} title="Onduleur" value="97.4% rendement" tone="gold" /><FlowNode className="left-[39%] top-[64%]" icon={Activity} title="Pompe forage" value={`${usageKw.toFixed(1)} kW utilisé`} tone="water" /><FlowNode className="right-[7%] top-[31%]" icon={BatteryCharging} title="Batterie" value={`${batteryChargeKw.toFixed(1)} kW charge`} tone="green" /><FlowNode className="right-[7%] top-[65%]" icon={ArrowUpRight} title={isPowerOutage ? 'STEG isolé' : 'Export réseau'} value={`${exportKw.toFixed(1)} kW`} tone={isPowerOutage ? 'red' : 'gold'} /><div className="absolute left-[27%] top-[42%] flex items-center gap-1 text-[9px] font-bold text-sun-500"><ArrowRightFlow /> production</div><div className="absolute left-[52%] top-[46%] flex items-center gap-1 text-[9px] font-bold text-water-500"><ArrowRightFlow /> consommation</div></div><div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-earth-400"><span>Export = production - usage - charge batterie</span><span>{deficitKw ? 'Appoint nécessaire' : 'Autoconsommation suffisante'}</span></div></section>;
}

function FlowNode({ className, icon: Icon, title, value, tone }: { className: string; icon: React.ElementType; title: string; value: string; tone: 'sun' | 'gold' | 'water' | 'green' | 'red' }) {
  const toneClass = tone === 'sun' ? 'border-sun-400/50 bg-sun-50 text-sun-700' : tone === 'gold' ? 'border-[#c88a29]/50 bg-[#fff7e5] text-[#8b5b13]' : tone === 'water' ? 'border-water-400/50 bg-water-50 text-water-700' : tone === 'red' ? 'border-alert-400/50 bg-alert-50 text-alert-700' : 'border-brand-400/50 bg-brand-50 text-brand-700';
  return <div className={cn('absolute z-10 w-[135px] rounded-xl border p-2 shadow-lg [transform:translateZ(30px)]', toneClass, className)}><div className="flex items-center gap-1.5"><Icon className="h-4 w-4" /><span className="truncate text-[10px] font-black">{title}</span></div><p className="mt-1 text-[9px] font-semibold">{value}</p></div>;
}

function ArrowRightFlow() { return <span className="inline-block h-1.5 w-8 rounded-full bg-current" />; }

function EnergyNumber({ icon: Icon, label, value, color }: { icon: React.ElementType; label: string; value: string; color: 'sun' | 'water' | 'green' | 'gold' | 'red' }) {
  const text = color === 'sun' || color === 'gold' ? 'text-sun-500' : color === 'red' ? 'text-alert-500' : color === 'green' ? 'text-brand-500' : 'text-water-500';
  return <div className="rounded-lg border border-line bg-raised p-2.5"><Icon className={cn('h-4 w-4', text)} /><p className="mt-1 text-[9px] text-earth-500">{label}</p><p className={cn('text-xs font-black', text)}>{value}</p></div>;
}

function EnergyNextSteps({ waterLiters, usageKw, exportKw }: { waterLiters: number; usageKw: number; exportKw: number }) {
  const steps = [
    { title: 'Déplacer le pompage', detail: 'Utiliser le pic solaire pour réduire l appel réseau.', impact: `${Math.max(0.4, usageKw * 0.12).toFixed(1)} kW évitables`, icon: Sun },
    { title: 'Réduire les cycles stables', detail: 'Ne pas irriguer une zone déjà au-dessus de son seuil.', impact: `${Math.round(waterLiters * 0.08).toLocaleString('fr-FR')} L potentiels`, icon: Droplets },
    { title: 'Valoriser le surplus', detail: 'Prioriser la batterie avant l export du surplus.', impact: `${exportKw.toFixed(1)} kW disponibles`, icon: Gauge },
  ];
  return <aside className="rounded-2xl border border-brand-500/25 bg-surface p-4 shadow-xl"><div className="flex items-center gap-2 border-b border-line pb-3"><Sparkles className="h-4 w-4 text-brand-400" /><div><h2 className="text-sm font-bold text-ink">Prochaines étapes</h2><p className="text-[10px] text-earth-400">Réduire la consommation</p></div></div><div className="mt-3 space-y-2">{steps.map((step, index) => { const Icon = step.icon; return <div key={step.title} className="rounded-lg border border-line bg-raised p-2.5"><div className="flex items-start gap-2"><span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-500/10 text-[9px] font-black text-brand-400">{index + 1}</span><div><p className="flex items-center gap-1 text-[11px] font-bold text-ink"><Icon className="h-3 w-3 text-brand-400" />{step.title}</p><p className="mt-1 text-[10px] leading-4 text-earth-400">{step.detail}</p><p className="mt-1 text-[10px] font-semibold text-brand-400">Impact : {step.impact}</p></div></div></div>; })}</div><p className="mt-3 text-[9px] leading-4 text-earth-500">Chaque action doit être mesurée avant généralisation : kWh, litres, rendement et coût.</p></aside>;
}
