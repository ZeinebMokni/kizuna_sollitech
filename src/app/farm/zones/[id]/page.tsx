'use client';

import React from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Droplets,
  Sun,
  Thermometer,
  ShieldAlert,
  Play,
  Square,
  Sparkles,
  Layers,
  MapPin,
  Clock,
  Compass
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { useFarmStore } from '@/stores/useFarmStore';
import { cn, formatNumber } from '@/lib/utils';

export default function ZoneDetailPage() {
  const params = useParams();
  const zoneId = params?.id as string;
  const { farm, startIrrigation, stopIrrigation, emergencyStopActive } = useFarmStore();

  const zone = farm.zones.find((z) => z.id === zoneId) || farm.zones[0];

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center gap-3 pb-3 border-b border-line">
          <Link
            href="/farm"
            className="p-2 rounded-xl bg-surface border border-line text-earth-300 hover:text-ink qa-card"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-brand-400">
              Parcelle Agricole · {zone.areaHa} Hectares
            </span>
            <h1 className="text-2xl font-black text-ink">{zone.name}</h1>
          </div>
        </div>

        {/* Status & Immediate Action Banner */}
        <div className={cn(
          "p-5 rounded-2xl border flex flex-col sm:flex-row sm:items-center justify-between gap-4",
          zone.status === 'critical' ? "bg-alert-950/20 border-alert-500/40" : "bg-surface border-line"
        )}>
          <div className="flex items-center gap-4">
            <div className={cn(
              "h-12 w-12 rounded-xl flex items-center justify-center font-bold text-lg",
              zone.status === 'healthy' && "bg-brand-500/20 text-brand-400 border border-brand-500/30",
              zone.status === 'warning' && "bg-sun-500/20 text-sun-400 border border-sun-500/30",
              zone.status === 'critical' && "bg-alert-500/20 text-alert-400 border border-alert-500/30 animate-pulse",
              zone.status === 'irrigating' && "bg-water-500/20 text-water-400 border border-water-500/30"
            )}>
              <Droplets className="h-6 w-6" />
            </div>
            <div>
              <span className="text-xs text-earth-400">Statut Physiologique</span>
              <h3 className="text-lg font-bold text-ink capitalize">
                {zone.status === 'irrigating' ? 'Irrigation Solaire en cours' : zone.status}
              </h3>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {zone.status === 'irrigating' ? (
              <button
                onClick={() => stopIrrigation(zone.id)}
                className="px-5 py-2.5 rounded-xl bg-earth-800 hover:bg-earth-700 text-alert-400 border border-alert-500/30 font-bold text-xs flex items-center gap-2"
              >
                <Square className="h-4 w-4 fill-current" />
                <span>Arrêter l'arrosage</span>
              </button>
            ) : (
              <button
                disabled={emergencyStopActive}
                onClick={() => startIrrigation(zone.id)}
                className={cn(
                  "px-5 py-2.5 rounded-xl font-bold text-xs flex items-center gap-2 transition-all shadow-lg",
                  emergencyStopActive
                    ? "bg-earth-800 text-earth-500 cursor-not-allowed"
                    : "bg-accent hover:bg-accent-hover text-on-accent shadow-shade/20"
                )}
              >
                <Play className="h-4 w-4 fill-current" />
                <span>Déclencher Cycle d'Irrigation</span>
              </button>
            )}

            <Link
              href="/farm/map"
              className="px-4 py-2.5 rounded-xl bg-raised hover:bg-highlight text-brand-300 font-semibold text-xs border border-brand-500/30 flex items-center gap-1.5"
            >
              <Compass className="h-4 w-4 text-brand-400" />
              <span>Voir sur la Carte</span>
            </Link>
          </div>
        </div>

        {/* Detailed Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-surface p-4 rounded-xl border border-line qa-card">
            <span className="text-xs text-earth-400 flex items-center gap-1">
              <Droplets className="h-3.5 w-3.5 text-water-400" /> Humidité du Sol
            </span>
            <p className="text-2xl font-black text-ink mt-1">{zone.soilMoisturePercent}%</p>
            <span className="text-[10px] text-earth-500">Cible : {zone.targetMoistureMin}% - {zone.targetMoistureMax}%</span>
          </div>

          <div className="bg-surface p-4 rounded-xl border border-line qa-card">
            <span className="text-xs text-earth-400 flex items-center gap-1">
              <Thermometer className="h-3.5 w-3.5 text-sun-400" /> Température Canopée
            </span>
            <p className="text-2xl font-black text-ink mt-1">{zone.temperatureC}°C</p>
            <span className="text-[10px] text-earth-500">Humidité de l'air : {zone.humidityPercent}%</span>
          </div>

          <div className="bg-surface p-4 rounded-xl border border-line qa-card">
            <span className="text-xs text-earth-400 flex items-center gap-1">
              <Droplets className="h-3.5 w-3.5 text-water-400" /> Eau Consommée (24h)
            </span>
            <p className="text-2xl font-black text-water-300 mt-1">{formatNumber(zone.dailyWaterLiters)} L</p>
            <span className="text-[10px] text-earth-500">{zone.irrigationMethod}</span>
          </div>

          <div className="bg-surface p-4 rounded-xl border border-line qa-card">
            <span className="text-xs text-earth-400 flex items-center gap-1">
              <Sun className="h-3.5 w-3.5 text-sun-400" /> Énergie Pompage
            </span>
            <p className="text-2xl font-black text-sun-300 mt-1">{zone.dailyEnergyKwh} kWh</p>
            <span className="text-[10px] text-brand-400">100% Solaire Hybride</span>
          </div>
        </div>

        {/* Agronomic profile */}
        <div className="bg-surface border border-line p-5 rounded-2xl space-y-4 qa-card">
          <h3 className="text-base font-bold text-ink">Fiche Technique Parcellaire</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            <div className="bg-sunken p-3.5 rounded-xl border border-line">
              <span className="text-earth-400 block mb-1">Culture & Variété</span>
              <p className="font-bold text-ink">{zone.cropType}</p>
              <p className="text-earth-400 text-[11px] mt-0.5">{zone.variety}</p>
            </div>

            <div className="bg-sunken p-3.5 rounded-xl border border-line">
              <span className="text-earth-400 block mb-1">Type de Sol & Salinité</span>
              <p className="font-bold text-ink">{zone.soilType}</p>
              <p className="text-earth-400 text-[11px] mt-0.5">Tolérance saline : Modérée à Élevée</p>
            </div>

            <div className="bg-sunken p-3.5 rounded-xl border border-line">
              <span className="text-earth-400 block mb-1">Date Prévisionnelle de Récolte</span>
              <p className="font-bold text-brand-400">{zone.predictedHarvestDate}</p>
              <p className="text-earth-400 text-[11px] mt-0.5">Rendement estimé : {zone.yieldEstimateTons} Tonnes</p>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
