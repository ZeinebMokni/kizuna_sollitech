'use client';

import React from 'react';
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
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { useFarmStore } from '@/stores/useFarmStore';
import { DEMO_HOURLY_ENERGY, DEMO_ENERGY_TELEMETRY } from '@/lib/mockData';
import { cn } from '@/lib/utils';

export default function EnergyPage() {
  const { farm, isPowerOutage, togglePowerOutage } = useFarmStore();

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
