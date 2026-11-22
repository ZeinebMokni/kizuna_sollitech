'use client';

import React, { useState } from 'react';
import {
  Droplets,
  Play,
  Square,
  ShieldAlert,
  Clock,
  Activity,
  Layers,
  Settings2,
  CheckCircle2,
  AlertTriangle,
  Sliders
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { useFarmStore } from '@/stores/useFarmStore';
import { cn, formatNumber } from '@/lib/utils';

export default function IrrigationPage() {
  const { farm, startIrrigation, stopIrrigation, emergencyStopActive, toggleEmergencyStop } = useFarmStore();

  const [autoMode, setAutoMode] = useState(true);
  const [maxRuntimeMinutes, setMaxRuntimeMinutes] = useState(60);

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-line gap-4">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-brand-400">
              Automatisation Hydrique & Philosophie Mottainai
            </span>
            <h1 className="text-2xl font-black text-ink">Gestion & Contrôle de l'Irrigation</h1>
            <p className="text-xs text-earth-400 mt-0.5">
              Asservissement en boucle fermée : Données hygrométriques sol × Ensoleillement solaire
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* Auto Mode Switch */}
            <button
              onClick={() => setAutoMode(!autoMode)}
              className={cn(
                "px-4 py-2 rounded-xl text-xs font-bold border transition-colors flex items-center gap-2",
                autoMode
                  ? "bg-brand-600/30 border-brand-500 text-brand-300"
                  : "bg-earth-800 border-earth-700 text-earth-400"
              )}
            >
              <Activity className="h-4 w-4" />
              <span>Mode Automatique {autoMode ? 'ACTIF' : 'MANUEL'}</span>
            </button>

            {/* Emergency Stop Button */}
            <button
              onClick={toggleEmergencyStop}
              className={cn(
                "px-4 py-2 rounded-xl text-xs font-black uppercase tracking-wider border transition-all flex items-center gap-1.5",
                emergencyStopActive
                  ? "bg-alert-600 text-on-accent border-alert-400 animate-bounce"
                  : "bg-alert-950/60 border-alert-500 text-alert-300 hover:bg-alert-900"
              )}
            >
              <ShieldAlert className="h-4 w-4" />
              <span>{emergencyStopActive ? 'DÉVERROUILLER ARRÊT' : 'ARRÊT D\'URGENCE'}</span>
            </button>
          </div>
        </div>

        {/* Water Storage & Infrastructure Status */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-surface p-5 rounded-2xl border border-line shadow-md qa-card">
            <span className="text-xs text-earth-400 flex items-center gap-1.5">
              <Droplets className="h-4 w-4 text-water-400" /> Bassin de Stockage Tampon
            </span>
            <div className="flex items-baseline gap-2 mt-2">
              <p className="text-3xl font-black text-ink">{farm.currentTankLevelPercent}%</p>
              <span className="text-xs text-earth-400 font-mono">
                ({Math.round((farm.storageTankVolumeM3 * farm.currentTankLevelPercent) / 100)} / {farm.storageTankVolumeM3} m³)
              </span>
            </div>
            <div className="w-full bg-earth-800 h-2 rounded-full overflow-hidden mt-3">
              <div
                className="bg-water-500 h-full rounded-full transition-all duration-700"
                style={{ width: `${farm.currentTankLevelPercent}%` }}
              />
            </div>
          </div>

          <div className="bg-surface p-5 rounded-2xl border border-line shadow-md qa-card">
            <span className="text-xs text-earth-400 flex items-center gap-1.5">
              <Activity className="h-4 w-4 text-brand-400" /> Pompe Submersible Forage
            </span>
            <p className="text-3xl font-black text-brand-400 mt-2">26.4 m³/h</p>
            <p className="text-xs text-earth-400 mt-1">Pression de refoulement : 3.8 bars · Puissance 6.8 kW</p>
          </div>

          <div className="bg-surface p-5 rounded-2xl border border-line shadow-md qa-card">
            <span className="text-xs text-earth-400 flex items-center gap-1.5">
              <Clock className="h-4 w-4 text-sun-400" /> Sécurité Durée Maximale (Watchdog)
            </span>
            <div className="flex items-center gap-2 mt-2">
              <input
                type="number"
                value={maxRuntimeMinutes}
                onChange={(e) => setMaxRuntimeMinutes(Number(e.target.value))}
                className="w-20 bg-sunken border border-line rounded-lg px-2.5 py-1 text-sm font-mono font-bold text-ink focus:outline-none focus:border-brand-500"
              />
              <span className="text-xs text-earth-400">minutes consécutives max</span>
            </div>
            <p className="text-[10px] text-earth-500 mt-2">Coupure automatique si vanne bloquée ouverte</p>
          </div>
        </div>

        {/* Zones Irrigation Matrix */}
        <div className="bg-surface border border-line rounded-2xl p-5 shadow-xl qa-card">
          <h2 className="text-base font-bold text-ink mb-4">Matrice des Vannes Parcellaires</h2>

          <div className="divide-y divide-line">
            {farm.zones.map((zone) => {
              const isIrrigating = zone.irrigationStatus === 'active';
              const isCritical = zone.status === 'critical';

              return (
                <div key={zone.id} className="py-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="flex items-start gap-3">
                    <div className={cn(
                      "h-10 w-10 rounded-xl flex items-center justify-center font-bold flex-shrink-0 mt-0.5",
                      isIrrigating ? "bg-water-500/20 text-water-400 animate-pulse border border-water-500/30" : "bg-earth-800 text-earth-400"
                    )}>
                      <Droplets className="h-5 w-5" />
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-ink">{zone.name}</h4>
                      <p className="text-xs text-earth-400">{zone.cropType} · {zone.areaHa} Ha · {zone.irrigationMethod}</p>
                    </div>
                  </div>

                  {/* Soil moisture gauge & limits */}
                  <div className="flex items-center gap-4 text-xs">
                    <div>
                      <span className="text-earth-400 block text-[10px]">Humidité Actuelle</span>
                      <span className={cn(
                        "font-mono font-bold text-sm",
                        isCritical ? "text-alert-400" : "text-ink"
                      )}>
                        {zone.soilMoisturePercent}%
                      </span>
                    </div>

                    <div className="h-6 w-px bg-earth-700 hidden sm:block" />

                    <div>
                      <span className="text-earth-400 block text-[10px]">Seuils Autorisés</span>
                      <span className="font-mono text-earth-300">
                        {zone.targetMoistureMin}% à {zone.targetMoistureMax}%
                      </span>
                    </div>

                    <div className="h-6 w-px bg-earth-700 hidden sm:block" />

                    <div>
                      <span className="text-earth-400 block text-[10px]">Consommation 24h</span>
                      <span className="font-mono text-water-400 font-semibold">
                        {formatNumber(zone.dailyWaterLiters)} L
                      </span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2">
                    {isIrrigating ? (
                      <button
                        onClick={() => stopIrrigation(zone.id)}
                        className="px-4 py-2 rounded-xl bg-earth-800 hover:bg-earth-700 text-alert-400 border border-alert-500/30 text-xs font-bold flex items-center gap-1.5 transition-colors"
                      >
                        <Square className="h-3.5 w-3.5 fill-current" />
                        <span>Fermer Vanne</span>
                      </button>
                    ) : (
                      <button
                        disabled={emergencyStopActive}
                        onClick={() => startIrrigation(zone.id)}
                        className={cn(
                          "px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-1.5 transition-all shadow-md",
                          emergencyStopActive
                            ? "bg-earth-800 text-earth-500 cursor-not-allowed"
                            : isCritical
                            ? "bg-alert-600 hover:bg-alert-500 text-on-accent shadow-shade/20"
                            : "bg-accent hover:bg-accent-hover text-on-accent shadow-shade/20"
                        )}
                      >
                        <Play className="h-3.5 w-3.5 fill-current" />
                        <span>Ouvrir Vanne</span>
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
