'use client';

import React from 'react';
import { History, ArrowRight, X, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { SENTINEL2_TUNISIA_SCENES } from '@/lib/geo/providers';
import { useFarmStore } from '@/stores/useFarmStore';
import { cn } from '@/lib/utils';

export function HistoricalComparison() {
  const {
    selectedScene,
    historicalCompareScene,
    setHistoricalCompareScene,
    mapLayerMode,
    setMapLayerMode
  } = useFarmStore();

  const isComparing = historicalCompareScene !== null;

  return (
    <div className="glass-panel p-3 rounded-2xl border text-xs space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 font-bold text-ink">
          <History className="h-4 w-4 text-brand-400" />
          <span>Comparaison Temporelle Sentinel-2</span>
        </div>
        {isComparing && (
          <button
            onClick={() => setHistoricalCompareScene(null)}
            className="p-1 text-earth-400 hover:text-ink rounded"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {!isComparing ? (
        <div className="flex items-center gap-2">
          <span className="text-earth-400 text-[11px]">Comparer avec un passage antérieur :</span>
          <button
            onClick={() => setHistoricalCompareScene(SENTINEL2_TUNISIA_SCENES[3])} // July 2026 heatwave
            className="px-2.5 py-1 rounded-lg bg-accent hover:bg-accent-hover text-on-accent font-semibold text-[11px] transition-colors"
          >
            Passage Été 2026 (Canicule)
          </button>
        </div>
      ) : (
        <div className="space-y-2 text-[11px]">
          <div className="grid grid-cols-2 gap-2 bg-sunken p-2.5 rounded-xl border border-line">
            <div>
              <span className="text-earth-500 block text-[10px]">Passage Actuel</span>
              <span className="font-bold text-ink">{selectedScene.acquisitionDate}</span>
              <p className="text-[10px] text-brand-400">NDVI moyen 0.52</p>
            </div>
            <div>
              <span className="text-earth-500 block text-[10px]">Passage Comparé</span>
              <span className="font-bold text-sun-300">{historicalCompareScene.acquisitionDate}</span>
              <p className="text-[10px] text-sun-400">NDVI moyen 0.38 (Canicule)</p>
            </div>
          </div>
          <p className="text-[10px] text-earth-300">
            Gain de biomasse végétative : <span className="text-brand-400 font-bold">+26.9%</span> suite à l'installation des sondes intelligentes QATRA.
          </p>
        </div>
      )}
    </div>
  );
}
