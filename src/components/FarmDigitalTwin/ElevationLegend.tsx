'use client';

import React from 'react';
import { Mountain, Sliders, Info, TrendingDown, ArrowUp } from 'lucide-react';
import { useFarmStore } from '@/stores/useFarmStore';

export function ElevationLegend() {
  const { elevationOpacity, setElevationOpacity } = useFarmStore();

  const stops = [
    { elevation: '342 m', color: '#56B8B2', label: 'Drainage naturel / Talweg Ouest' },
    { elevation: '350 m', color: '#9AB47A', label: 'Plaine maraîchère basse' },
    { elevation: '358 m', color: '#EFB447', label: 'Oliveraies médianes (Pente 1.8%)' },
    { elevation: '364 m', color: '#E68660', label: 'Revers de plateau' },
    { elevation: '368 m', color: '#E27463', label: 'Crête Sud-Est / Tête de forage' },
  ];

  return (
    <div className="glass-panel p-3.5 rounded-2xl border border-water-500/30 text-xs space-y-3 max-w-xs text-ink">
      <div className="flex items-center justify-between pb-2 border-b border-line">
        <div className="flex items-center gap-2">
          <Mountain className="h-4 w-4 text-water-400" />
          <span className="font-bold text-ink text-xs">
            Altimétrie & Relief MNT
          </span>
        </div>
        <span className="text-[10px] font-mono text-water-400 bg-water-950/60 px-1.5 py-0.5 rounded border border-water-500/30">
          ΔH = 26 m
        </span>
      </div>

      {/* Opacity Slider */}
      <div className="space-y-1">
        <div className="flex justify-between text-[11px] text-earth-300">
          <span className="flex items-center gap-1">
            <Sliders className="h-3 w-3 text-water-400" /> Opacité du Relief
          </span>
          <span className="font-mono font-bold text-ink">{Math.round(elevationOpacity * 100)}%</span>
        </div>
        <input
          type="range"
          min="0.1"
          max="1.0"
          step="0.05"
          value={elevationOpacity}
          onChange={(e) => setElevationOpacity(parseFloat(e.target.value))}
          className="w-full accent-water-500 h-1.5 bg-earth-800 rounded-lg cursor-pointer"
        />
      </div>

      {/* Micro-topography Key Stats */}
      <div className="grid grid-cols-2 gap-2 text-center text-[10px]">
        <div className="bg-sunken p-2 rounded-xl border border-line">
          <span className="text-earth-400 block">Pente Moyenne</span>
          <span className="font-mono font-bold text-sun-400 text-xs">1.8% vers N-O</span>
        </div>
        <div className="bg-sunken p-2 rounded-xl border border-line">
          <span className="text-earth-400 block">Écoulement Gravitaire</span>
          <span className="font-mono font-bold text-brand-400 text-xs">Favorable</span>
        </div>
      </div>

      {/* Hypsometric Gradient Steps */}
      <div className="space-y-1 pt-1 border-t border-line">
        {stops.map((stop) => (
          <div key={stop.elevation} className="flex items-center gap-2 text-[11px] text-earth-300">
            <span
              className="h-2.5 w-2.5 rounded-full flex-shrink-0"
              style={{ backgroundColor: stop.color }}
            />
            <span className="font-mono font-bold text-ink w-12">{stop.elevation}</span>
            <span className="text-[10px] text-earth-400 truncate">{stop.label}</span>
          </div>
        ))}
      </div>

      <div className="p-2 bg-water-950/30 border border-water-500/20 rounded-lg text-[10px] text-water-300/90 leading-tight">
        Les zones basses (bleu/vert) accumulent le ruissellement pluvial, tandis que la crête (orange) bénéficie d'une pression gravitaire naturelle pour le réseau d'irrigation.
      </div>
    </div>
  );
}
