'use client';

import Link from 'next/link';
import {
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Droplets,
  Play,
  Satellite,
  ShieldAlert,
  Square,
  Thermometer,
  X,
} from 'lucide-react';
import { useState } from 'react';
import { useFarmStore } from '@/stores/useFarmStore';
import { getNDVIInterpretation } from '@/lib/geo/ndvi';
import { cn } from '@/lib/utils';

const STATUS_LABEL = {
  healthy: 'Saine',
  warning: 'À surveiller',
  critical: 'Critique',
  irrigating: 'Irrigation en cours',
  nodata: 'Sans données',
} as const;

export function ZoneDetailsPanel() {
  const {
    farm,
    selectedZoneId,
    selectZone,
    startIrrigation,
    stopIrrigation,
    emergencyStopActive,
    selectedScene,
  } = useFarmStore();
  const [showDetails, setShowDetails] = useState(false);

  const zone = farm.zones.find((item) => item.id === selectedZoneId);
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
    <aside className="absolute right-4 top-20 z-30 flex max-h-[calc(100vh-14rem)] w-80 flex-col overflow-hidden rounded-2xl border glass-panel text-xs transition-all duration-300 sm:w-88">
      <header className="flex items-center justify-between border-b border-line bg-raised p-3">
        <div className="min-w-0 pr-2">
          <span className="block text-[9px] font-bold uppercase tracking-wider text-brand-400">Inspection parcellaire</span>
          <h3 className="truncate text-sm font-bold text-ink">{zone.name}</h3>
        </div>
        <button onClick={() => selectZone(null)} className="rounded-lg p-1 text-earth-400 transition-colors hover:bg-earth-800 hover:text-ink" title="Fermer">
          <X className="h-4 w-4" />
        </button>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto p-3.5">
        <div className="flex items-center justify-between rounded-xl border border-line bg-sunken p-2.5">
          <div className="min-w-0">
            <span className="text-[10px] text-earth-400">Culture</span>
            <p className="truncate text-xs font-bold text-ink">{zone.cropType}</p>
            <span className="font-mono text-[10px] text-brand-400">{zone.areaHa} ha</span>
          </div>
          <span className={cn(
            'rounded-full border px-2.5 py-1 text-[10px] font-bold',
            zone.status === 'healthy' && 'border-brand-500/30 bg-brand-500/20 text-brand-300',
            zone.status === 'warning' && 'border-sun-500/30 bg-sun-500/20 text-sun-300',
            zone.status === 'critical' && 'animate-pulse border-alert-500/30 bg-alert-500/20 text-alert-300',
            zone.status === 'irrigating' && 'border-water-500/30 bg-water-500/20 text-water-300',
          )}>
            {STATUS_LABEL[zone.status]}
          </span>
        </div>

        <section className="rounded-xl border border-line bg-sunken p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-water-400">État actuel</span>
            <span className="text-[10px] text-earth-400">Capteurs live</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-lg border border-line bg-surface p-2">
              <span className="flex items-center gap-1 text-[10px] text-earth-400"><Droplets className="h-3 w-3 text-water-400" /> Humidité sol</span>
              <p className={cn('mt-0.5 text-xl font-black', isCritical ? 'text-alert-400' : 'text-ink')}>{zone.soilMoisturePercent}%</p>
              <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-earth-800">
                <div className={cn('h-full rounded-full transition-all', isCritical ? 'bg-alert-500' : 'bg-brand-500')} style={{ width: `${zone.soilMoisturePercent}%` }} />
              </div>
            </div>
            <div className="rounded-lg border border-line bg-surface p-2">
              <span className="flex items-center gap-1 text-[10px] text-earth-400"><Thermometer className="h-3 w-3 text-sun-400" /> Température</span>
              <p className="mt-0.5 text-xl font-black text-ink">{zone.temperatureC}°C</p>
              <span className="text-[9px] text-earth-500">{zone.humidityPercent}% humidité air</span>
            </div>
          </div>
          <p className="mt-2 text-[10px] text-earth-400">Cible d’humidité : {zone.targetMoistureMin}–{zone.targetMoistureMax}%</p>
        </section>

        {isCritical && (
          <div className="flex gap-2 rounded-xl border border-alert-500/40 bg-alert-950/40 p-2.5">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 animate-pulse text-alert-400" />
            <div>
              <p className="font-bold text-alert-200">Action recommandée</p>
              <p className="mt-0.5 text-[10px] leading-snug text-alert-300/80">Humidité sous le seuil : lancer un cycle de 45 min.</p>
            </div>
          </div>
        )}

        <section className="rounded-xl border border-line bg-sunken p-3">
          <span className="mb-2 block text-[10px] font-bold uppercase tracking-wider text-earth-400">Irrigation</span>
          {isIrrigating ? (
            <button onClick={() => stopIrrigation(zone.id)} className="flex w-full items-center justify-center gap-2 rounded-xl border border-alert-500/30 bg-earth-800 py-2 text-xs font-bold text-alert-400 transition-colors hover:bg-earth-700">
              <Square className="h-3.5 w-3.5 fill-current" /> Fermer la vanne
            </button>
          ) : (
            <button
              disabled={emergencyStopActive}
              onClick={() => startIrrigation(zone.id)}
              className={cn(
                'flex w-full items-center justify-center gap-2 rounded-xl py-2 text-xs font-bold shadow-lg transition-all',
                emergencyStopActive ? 'cursor-not-allowed border border-earth-700 bg-earth-800 text-earth-500' : isCritical ? 'bg-alert-600 text-on-accent hover:bg-alert-500' : 'bg-accent text-on-accent hover:bg-accent-hover',
              )}
            >
              <Play className="h-3.5 w-3.5 fill-current" />
              {emergencyStopActive ? 'Arrêt d’urgence actif' : 'Ouvrir la vanne · 45 min'}
            </button>
          )}
        </section>

        <button
          type="button"
          aria-expanded={showDetails}
          onClick={() => setShowDetails((current) => !current)}
          className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-line py-2 text-[11px] font-semibold text-water-400 transition-colors hover:bg-water-500/10"
        >
          {showDetails ? 'Voir moins' : 'Voir plus'}
          {showDetails ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        </button>

        {showDetails && (
          <div className="space-y-3">
            <section className="space-y-2 rounded-xl border border-brand-500/30 bg-sunken p-3">
              <div className="flex items-center justify-between border-b border-line pb-1">
                <span className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-brand-400"><Satellite className="h-3.5 w-3.5" /> Indice NDVI</span>
                <span className="rounded bg-earth-800 px-1.5 py-0.5 text-[9px] font-mono text-earth-400">Sentinel-2</span>
              </div>
              <div className="grid grid-cols-3 gap-1.5 text-center">
                <Metric label="Min" value={String(ndviStats.min)} />
                <Metric label="Moyen" value={String(ndviStats.mean)} highlight />
                <Metric label="Max" value={String(ndviStats.max)} />
              </div>
              <p className="text-[10px] leading-tight text-earth-300">{ndviInterp.category}. {ndviInterp.explanation}</p>
            </section>

            <section className="rounded-xl border border-line bg-sunken p-3">
              <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-earth-400">Détails de la parcelle</p>
              <div className="grid grid-cols-2 gap-x-3 gap-y-2 text-[10px]">
                <Detail label="Sol" value={zone.soilType} />
                <Detail label="Méthode" value={zone.irrigationMethod} />
                <Detail label="Récolte estimée" value={zone.predictedHarvestDate} />
                <Detail label="Variété" value={zone.variety || 'Non renseignée'} />
              </div>
            </section>

            <Link href={`/farm/zones/${zone.id}`} className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-brand-500/20 bg-highlight py-2 text-xs font-semibold text-brand-300 transition-colors hover:bg-brand-500/10">
              Ouvrir la fiche complète <ChevronRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        )}
      </div>
    </aside>
  );
}

function Metric({ label, value, highlight = false }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className={cn('rounded-lg border border-line bg-surface p-1.5', highlight && 'border-brand-500/40')}>
      <span className={cn('block text-[9px]', highlight ? 'font-semibold text-brand-400' : 'text-earth-400')}>{label}</span>
      <span className={cn('font-mono text-xs font-bold', highlight ? 'text-brand-300' : 'text-earth-200')}>{value}</span>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="block text-earth-500">{label}</span>
      <span className="font-semibold text-earth-200">{value}</span>
    </div>
  );
}
