'use client';

import React, { useEffect } from 'react';
import { Cloud, Sun, Satellite, Loader2 } from 'lucide-react';
import { SENTINEL2_TUNISIA_SCENES } from '@/lib/geo/providers';
import { useFarmStore } from '@/stores/useFarmStore';
import { useSentinelStore } from '@/stores/useSentinelStore';
import { cn } from '@/lib/utils';

const dateFmt = new Intl.DateTimeFormat('fr-TN', { day: 'numeric', month: 'short', year: 'numeric' });

/**
 * Sentinel-2 acquisition picker. With the backend connected it lists the real
 * passes over the farm (Copernicus catalog); otherwise it keeps the demo list
 * and says the NDVI is simulated.
 */
export function SatelliteDateSelector() {
  const { selectedScene, setSelectedScene } = useFarmStore();
  const { link, scenes, selectedDate, setSelectedDate, connect, loadingImage, imageError } = useSentinelStore();

  useEffect(() => {
    void connect();
  }, [connect]);

  const live = link === 'live' && scenes.length > 0;
  const current = live ? scenes.find((s) => s.date === selectedDate) ?? scenes[0] : null;

  return (
    <div className="glass-panel px-3 py-2 rounded-2xl border flex items-center gap-3 text-xs">
      <div className="flex items-center gap-2">
        <div className="h-7 w-7 rounded-lg bg-brand-500/10 border border-brand-500/30 flex items-center justify-center text-brand-400">
          {loadingImage ? <Loader2 className="h-4 w-4 animate-spin" /> : <Satellite className="h-4 w-4" />}
        </div>
        <div>
          <span className="text-[10px] text-earth-400 block -mb-0.5">Passage Satellite Sentinel-2</span>
          {live ? (
            <select
              aria-label="Date du passage Sentinel-2"
              value={current?.date ?? ''}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="bg-transparent font-bold text-ink focus:outline-none cursor-pointer pr-4"
            >
              {scenes.map((s) => (
                <option key={s.date} value={s.date} className="bg-surface text-ink">
                  {dateFmt.format(new Date(s.date))} ({s.cloud_cover ?? '?'} % nuages)
                </option>
              ))}
            </select>
          ) : (
            <select
              aria-label="Date du passage Sentinel-2 (démo)"
              value={selectedScene.id}
              onChange={(e) => {
                const scene = SENTINEL2_TUNISIA_SCENES.find((s) => s.id === e.target.value);
                if (scene) setSelectedScene(scene);
              }}
              className="bg-transparent font-bold text-ink focus:outline-none cursor-pointer pr-4"
            >
              {SENTINEL2_TUNISIA_SCENES.map((scene) => (
                <option key={scene.id} value={scene.id} className="bg-surface text-ink">
                  {scene.acquisitionDate} ({scene.cloudCoverPercent}% nuages)
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      <div className="hidden sm:flex items-center gap-3 text-[11px] text-earth-400 pl-3 border-l border-line">
        <span className="flex items-center gap-1 text-earth-300">
          <Cloud className="h-3 w-3 text-water-400" />
          {live ? `${current?.cloud_cover ?? '?'} %` : `${selectedScene.cloudCoverPercent}%`} Nuages
        </span>
        {!live && (
          <span className="flex items-center gap-1 text-earth-300">
            <Sun className="h-3 w-3 text-sun-400" />
            Élévation {selectedScene.sunElevationAngle}°
          </span>
        )}
        <DataBadge live={live && !imageError} title={imageError ?? undefined} />
      </div>
    </div>
  );
}

/** "Données réelles" vs "Simulation" pill, with the reason on hover. */
export function DataBadge({ live, title }: { live: boolean; title?: string }) {
  const { link, message } = useSentinelStore();
  const reason = title ?? message ?? undefined;
  return (
    <span
      title={live ? 'Copernicus Data Space · Sentinel-2 L2A, nuages masqués' : reason}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ring-inset',
        live ? 'bg-brand-500/15 text-brand-400 ring-brand-500/30' : 'bg-sun-500/15 text-sun-400 ring-sun-500/30'
      )}
    >
      <span className={cn('h-1.5 w-1.5 rounded-full', live ? 'bg-brand-500' : 'bg-sun-500')} />
      {live ? 'Données réelles' : link === 'checking' ? 'Connexion…' : 'Simulation'}
    </span>
  );
}
