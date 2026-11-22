'use client';

import React from 'react';
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
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { useFarmStore } from '@/stores/useFarmStore';
import { cn, formatNumber, formatCurrencyTND } from '@/lib/utils';

export default function FarmPage() {
  const { farm, selectZone, startIrrigation } = useFarmStore();

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
                className={cn(
                  "p-5 rounded-2xl border transition-all flex flex-col justify-between bg-surface",
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
      </div>
    </AppShell>
  );
}
