'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import {
  X,
  Droplets,
  Sun,
  Thermometer,
  ShieldAlert,
  Play,
  Square,
  Sparkles,
  Layers,
  ChevronRight,
  Info,
  Calendar,
  Satellite,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { useFarmStore } from '@/stores/useFarmStore';
import { getNDVIInterpretation } from '@/lib/geo/ndvi';
import { cn, formatNumber } from '@/lib/utils';

export function ZoneDetailsPanel() {
  const {
    farm,
    selectedZoneId,
    selectZone,
    startIrrigation,
    stopIrrigation,
    emergencyStopActive,
    selectedScene
  } = useFarmStore();

  const [isMinimized, setIsMinimized] = useState(false);

  const zone = farm.zones.find((z) => z.id === selectedZoneId);
  if (!zone) return null;

  const ndviStats = zone.ndviStats || {
    min: 0.18,
    mean: 0.48,
    max: 0.65,
    standardDeviation: 0.07,
    acquisitionDate: selectedScene.acquisitionDate,
    cloudCoverPercent: selectedScene.cloudCoverPercent,
    sensor: 'Sentinel-2 L2A MSI' as const,
    resolutionMeters: 10 as const,
  };

  const ndviInterp = getNDVIInterpretation(ndviStats.mean);
  const isCritical = zone.status === 'critical';
  const isIrrigating = zone.status === 'irrigating';

  return (
    <div
      className={cn(
        "absolute top-20 right-4 z-30 transition-all duration-300 w-80 sm:w-88 rounded-2xl glass-panel border flex flex-col text-xs overflow-hidden",
        isMinimized ? "max-h-14" : "max-h-[calc(100vh-14rem)]"
      )}
    >
      {/* Header */}
      <div className="p-3 border-b border-line flex items-center justify-between bg-raised">
        <div className="flex-1 pr-2 truncate">
          <span className="text-[9px] font-bold uppercase tracking-wider text-brand-400 block">
            Inspection Parcellaire SIG
          </span>
          <h3 className="text-sm font-bold text-ink truncate">{zone.name}</h3>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setIsMinimized(!isMinimized)}
            className="p-1 rounded-lg text-earth-400 hover:text-ink hover:bg-earth-800 transition-colors"
            title={isMinimized ? "Agrandir le panneau" : "Réduire le panneau"}
          >
            {isMinimized ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
          </button>
          <button
            onClick={() => selectZone(null)}
            className="p-1 rounded-lg text-earth-400 hover:text-ink hover:bg-earth-800 transition-colors"
            title="Fermer"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Body Content */}
      {!isMinimized && (
        <div className="p-3.5 space-y-3 overflow-y-auto flex-1">
          {/* Status Pill & Area */}
          <div className="flex items-center justify-between bg-sunken p-2.5 rounded-xl border border-line">
            <div>
              <span className="text-[10px] text-earth-400">Culture</span>
              <p className="font-bold text-ink text-xs">{zone.cropType}</p>
              <span className="text-[10px] text-brand-400 font-mono">{zone.areaHa} Hectares</span>
            </div>
            <span
              className={cn(
                "px-2.5 py-1 text-[11px] font-bold rounded-full capitalize border",
                zone.status === 'healthy' && "bg-brand-500/20 text-brand-300 border-brand-500/30",
                zone.status === 'warning' && "bg-sun-500/20 text-sun-300 border-sun-500/30",
                zone.status === 'critical' && "bg-alert-500/20 text-alert-300 border-alert-500/30 animate-pulse",
                zone.status === 'irrigating' && "bg-water-500/20 text-water-300 border-water-500/30"
              )}
            >
              {isIrrigating ? 'Irrigation Active' : zone.status}
            </span>
          </div>

          {/* Sentinel-2 NDVI Card */}
          <div className="bg-sunken p-3 rounded-xl border border-brand-500/30 space-y-2">
            <div className="flex items-center justify-between pb-1 border-b border-line">
              <span className="text-[10px] font-bold uppercase tracking-wider text-brand-400 flex items-center gap-1.5">
                <Satellite className="h-3.5 w-3.5" /> Indice NDVI Sentinel-2
              </span>
              <span className="text-[9px] font-mono text-earth-400 bg-earth-800 px-1.5 py-0.5 rounded">
                B08 NIR × B04 RED
              </span>
            </div>

            <div className="grid grid-cols-3 gap-1.5 text-center">
              <div className="bg-surface p-1.5 rounded-lg border border-line">
                <span className="text-[9px] text-earth-400 block">Min</span>
                <span className="font-mono font-bold text-earth-200">{ndviStats.min}</span>
              </div>
              <div className="bg-surface p-1.5 rounded-lg border border-brand-500/40">
                <span className="text-[9px] text-brand-400 block font-semibold">Moyen</span>
                <span className="font-mono font-black text-brand-300 text-xs">{ndviStats.mean}</span>
              </div>
              <div className="bg-surface p-1.5 rounded-lg border border-line">
                <span className="text-[9px] text-earth-400 block">Max</span>
                <span className="font-mono font-bold text-earth-200">{ndviStats.max}</span>
              </div>
            </div>

            <p className="text-[10px] text-earth-300 leading-tight">
              {ndviInterp.category}. {ndviInterp.explanation}
            </p>
          </div>

          {/* ESP32 Sensor Telemetry Card */}
          <div className="bg-sunken p-3 rounded-xl border border-line space-y-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-water-400 block">
              Télémétrie Capteurs Sol (ESP32 Live)
            </span>

            <div className="grid grid-cols-2 gap-2">
              <div className="bg-surface p-2 rounded-lg border border-line">
                <span className="text-[10px] text-earth-400 flex items-center gap-1">
                  <Droplets className="h-3 w-3 text-water-400" /> Humidité Sol
                </span>
                <p className={cn("text-base font-black mt-0.5", isCritical ? "text-alert-400" : "text-ink")}>
                  {zone.soilMoisturePercent}%
                </p>
                <div className="w-full bg-earth-800 h-1.5 rounded-full overflow-hidden mt-1">
                  <div
                    className={cn("h-full rounded-full transition-all duration-500", isCritical ? "bg-alert-500" : "bg-brand-500")}
                    style={{ width: `${zone.soilMoisturePercent}%` }}
                  />
                </div>
              </div>

              <div className="bg-surface p-2 rounded-lg border border-line">
                <span className="text-[10px] text-earth-400 flex items-center gap-1">
                  <Thermometer className="h-3 w-3 text-sun-400" /> Température
                </span>
                <p className="text-base font-black text-ink mt-0.5">{zone.temperatureC}°C</p>
                <span className="text-[9px] text-earth-500">{zone.humidityPercent}% Humidité Air</span>
              </div>
            </div>
          </div>

          {/* Critical Stress Alert */}
          {isCritical && (
            <div className="bg-alert-950/40 border border-alert-500/40 p-2.5 rounded-xl flex gap-2 text-xs">
              <ShieldAlert className="h-4 w-4 text-alert-400 flex-shrink-0 mt-0.5 animate-pulse" />
              <div>
                <p className="font-bold text-alert-200">Stress Hydrique Sévère</p>
                <p className="text-alert-300/80 text-[10px] mt-0.5 leading-snug">
                  Humidité sol à {zone.soilMoisturePercent}% (seuil critique &lt; 20%).
                </p>
              </div>
            </div>
          )}

          {/* Valve Action */}
          <div className="bg-sunken p-3 rounded-xl border border-line space-y-1.5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-earth-400 block">
              Contrôle Vanne d'Irrigation
            </span>
            {isIrrigating ? (
              <button
                onClick={() => stopIrrigation(zone.id)}
                className="w-full py-2 rounded-xl bg-earth-800 hover:bg-earth-700 text-alert-400 border border-alert-500/30 font-bold text-xs flex items-center justify-center gap-2 transition-colors"
              >
                <Square className="h-3.5 w-3.5 fill-current" />
                <span>Fermer Vanne</span>
              </button>
            ) : (
              <button
                disabled={emergencyStopActive}
                onClick={() => startIrrigation(zone.id)}
                className={cn(
                  "w-full py-2 rounded-xl font-bold text-xs flex items-center justify-center gap-2 transition-all shadow-lg",
                  emergencyStopActive
                    ? "bg-earth-800 text-earth-500 cursor-not-allowed border border-earth-700"
                    : isCritical
                    ? "bg-alert-600 hover:bg-alert-500 text-on-accent shadow-shade/20"
                    : "bg-accent hover:bg-accent-hover text-on-accent shadow-shade/20"
                )}
              >
                <Play className="h-3.5 w-3.5 fill-current" />
                <span>{emergencyStopActive ? "Arrêt d'Urgence Actif" : "Ouvrir Vanne Solaire (45 min)"}</span>
              </button>
            )}
          </div>

          <Link
            href={`/farm/zones/${zone.id}`}
            className="w-full py-2 rounded-xl bg-highlight hover:bg-highlight text-brand-300 text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors border border-brand-500/20"
          >
            <span>Fiche Technique Complète</span>
            <ChevronRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      )}
    </div>
  );
}
