'use client';

import React from 'react';
import { Info, Sliders, Eye, Sparkles } from 'lucide-react';
import { NDVI_COLOR_SCALE } from '@/lib/geo/ndvi';
import { useFarmStore } from '@/stores/useFarmStore';
import { useSentinelStore } from '@/stores/useSentinelStore';
import { DataBadge } from './SatelliteDateSelector';
import { cn } from '@/lib/utils';

export function NDVILegend() {
  const { ndviOpacity, setNdviOpacity, sampledPixel } = useFarmStore();
  const { link, selectedDate, dateStats, imageError, loadingImage, message } = useSentinelStore();
  const live = link === 'live' && !!selectedDate && !imageError;

  return (
    <div className="glass-panel p-3.5 rounded-2xl border text-xs space-y-3 max-w-xs">
      <div className="flex items-center justify-between pb-2 border-b border-line">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-brand-400 animate-pulse" />
          <span className="font-bold text-ink text-xs tracking-wide">
            Indice de Végétation (NDVI)
          </span>
        </div>
        <span className="text-[10px] font-mono text-brand-400 bg-brand-950/60 px-1.5 py-0.5 rounded border border-brand-500/30">
          (B08 - B04)/(B08 + B04)
        </span>
      </div>

      {/* Data source: real Copernicus data or simulation */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between gap-2">
          <DataBadge live={live} title={imageError ?? undefined} />
          {live && selectedDate && (
            <span className="text-[11px] text-earth-300">
              {loadingImage ? 'Chargement…' : `Passage du ${new Date(selectedDate).toLocaleDateString('fr-TN')}`}
            </span>
          )}
        </div>
        {live && dateStats && (
          <div className="grid grid-cols-3 gap-1.5 text-center">
            {([['Min', dateStats.min], ['Moyen', dateStats.mean], ['Max', dateStats.max]] as const).map(([label, v]) => (
              <div key={label} className="rounded-lg bg-white/40 dark:bg-white/5 ring-1 ring-inset ring-line py-1">
                <span className="block text-[10px] text-earth-400">{label}</span>
                <span className="font-mono font-bold text-ink">{v.toFixed(2)}</span>
              </div>
            ))}
          </div>
        )}
        {live && dateStats && (
          <p className="text-[10px] text-earth-400">
            {Math.round(dateStats.clear_fraction * 100)} % de la ferme sans nuages · pixels de 10 m
          </p>
        )}
        {!live && link !== 'checking' && (
          <p className="text-[10px] text-earth-400 leading-snug">
            {imageError ?? message ?? 'Données simulées.'} La carte affiche une simulation en attendant.
          </p>
        )}
      </div>

      {/* Opacity slider */}
      <div className="space-y-1">
        <div className="flex justify-between text-[11px] text-earth-300">
          <span className="flex items-center gap-1">
            <Sliders className="h-3 w-3 text-brand-400" /> Opacité de la Couche
          </span>
          <span className="font-mono font-bold text-ink">{Math.round(ndviOpacity * 100)}%</span>
        </div>
        <input
          type="range"
          min="0.1"
          max="1.0"
          step="0.05"
          value={ndviOpacity}
          onChange={(e) => setNdviOpacity(parseFloat(e.target.value))}
          className="w-full accent-brand-500 h-1.5 bg-earth-800 rounded-lg cursor-pointer"
        />
      </div>

      {/* Color Scale Gradient Ramp */}
      <div className="space-y-1">
        <div className="h-3 rounded-full w-full bg-gradient-to-r from-[#D32F2F] via-[#FB8C00] via-[#FDD835] via-[#7CB342] to-[#2E7D32] shadow-inner" />
        <div className="flex justify-between text-[10px] font-mono text-earth-400 px-0.5">
          <span>0.0 (Sol nu)</span>
          <span>0.35</span>
          <span>0.50</span>
          <span>&gt; 0.70 (Dense)</span>
        </div>
      </div>

      {/* Discrete scale labels */}
      <div className="space-y-1 text-[11px] pt-1 border-t border-line">
        {NDVI_COLOR_SCALE.map((stop) => (
          <div key={stop.hex} className="flex items-center gap-2 text-earth-300">
            <span
              className="h-2.5 w-2.5 rounded-full flex-shrink-0"
              style={{ backgroundColor: stop.hex }}
            />
            <span className="truncate flex-1">{stop.labelFr}</span>
          </div>
        ))}
      </div>

      {/* Sampled pixel readout if clicked */}
      {sampledPixel && (
        <div className="p-2.5 rounded-xl bg-sunken border border-brand-500/40 text-[11px] space-y-1">
          <div className="flex items-center justify-between text-brand-300 font-bold">
            <span>Pixel Échantillonné</span>
            <span className="font-mono">{sampledPixel.ndvi}</span>
          </div>
          <div className="flex justify-between text-earth-400 text-[10px]">
            <span>Proche Infrarouge (B08) :</span>
            <span className="font-mono text-earth-200">{sampledPixel.nir}</span>
          </div>
          <div className="flex justify-between text-earth-400 text-[10px]">
            <span>Rouge Visible (B04) :</span>
            <span className="font-mono text-earth-200">{sampledPixel.red}</span>
          </div>
        </div>
      )}

      {/* Agronomic Disclaimer */}
      <div className="p-2 bg-sun-950/20 border border-sun-500/20 rounded-lg flex items-start gap-1.5 text-[10px] text-sun-300/90 leading-tight">
        <Info className="h-3.5 w-3.5 flex-shrink-0 mt-0.5 text-sun-400" />
        <span>
          Un faible NDVI peut correspondre à du sol nu, des semis récents ou une récolte effectuée, et non obligatoirement à un stress hydrique.
        </span>
      </div>
    </div>
  );
}
