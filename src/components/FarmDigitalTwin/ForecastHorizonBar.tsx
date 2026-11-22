'use client';

import { Clock3 } from 'lucide-react';

const HORIZONS = ['12 h', '2 jours', '5 jours', '7 jours', '1 mois'];

export function ForecastHorizonBar() {
  return (
    <div className="pointer-events-auto flex items-center gap-1 rounded-xl border border-line bg-surface/90 p-1.5 text-[10px] shadow-lg backdrop-blur-md">
      <span className="flex items-center gap-1 px-2 text-earth-400">
        <Clock3 className="h-3 w-3 text-water-400" />
        Horizon
      </span>
      {HORIZONS.map((horizon, index) => (
        <button
          key={horizon}
          type="button"
          aria-disabled="true"
          title="Prévisions bientôt disponibles"
          className={index === 0 ? 'rounded-lg bg-water-500/15 px-2 py-1.5 font-semibold text-water-400 transition-colors' : 'rounded-lg px-2 py-1.5 font-semibold text-earth-400 transition-colors hover:bg-earth-800 hover:text-ink'}
        >
          {horizon}
        </button>
      ))}
    </div>
  );
}
