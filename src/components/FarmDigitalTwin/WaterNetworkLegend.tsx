'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, Droplets } from 'lucide-react';
import { useFarmStore } from '@/stores/useFarmStore';
import { moistureGradientCss, MOISTURE_STOPS } from '@/lib/geo/moisture';

export function WaterNetworkLegend() {
  const { farm, emergencyStopActive } = useFarmStore();
  const [showDetails, setShowDetails] = useState(false);
  const open = emergencyStopActive ? [] : farm.zones.filter((zone) => zone.irrigationStatus === 'active');
  const min = MOISTURE_STOPS[0].at;
  const max = MOISTURE_STOPS[MOISTURE_STOPS.length - 1].at;

  return (
    <section className="w-72 max-w-[calc(100vw-2rem)] space-y-3 rounded-2xl p-3.5 text-xs text-ink glass-panel">
      <header className="flex items-center justify-between border-b border-line/70 pb-2">
        <div className="flex items-center gap-2">
          <Droplets className="h-4 w-4 text-water-400" />
          <span className="font-bold">Eau & humidité du sol</span>
        </div>
        <span className="rounded-full bg-water-500/10 px-2 py-1 text-[10px] font-semibold text-water-400">
          {open.length} ouverte{open.length === 1 ? '' : 's'}
        </span>
      </header>

      <div className="space-y-1.5">
        <div className="h-2.5 rounded-full ring-1 ring-inset ring-black/10" style={{ background: moistureGradientCss() }} />
        <div className="flex justify-between text-[10px] tabular-nums text-earth-300">
          <span>Sec · {min}%</span>
          <span>35%</span>
          <span>65%</span>
          <span>Humide · {max}%</span>
        </div>
      </div>

      <p className="border-t border-line/70 pt-2 text-[11px] text-earth-300">
        {emergencyStopActive
          ? 'Arrêt d’urgence actif : les vannes sont coupées.'
          : open.length === 0
          ? 'Aucune vanne ouverte.'
          : `${open.length} vanne${open.length > 1 ? 's' : ''} active${open.length > 1 ? 's' : ''} · ${open.map((zone) => zone.name.split(' - ')[0]).join(', ')}`}
      </p>

      <button type="button" aria-expanded={showDetails} onClick={() => setShowDetails((current) => !current)} className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-line py-2 text-[11px] font-semibold text-water-400 transition-colors hover:bg-water-500/10">
        {showDetails ? 'Voir moins' : 'Voir plus'}
        {showDetails ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
      </button>

      {showDetails && (
        <ul className="space-y-1.5 text-[11px] text-earth-200">
          <li className="flex items-center gap-2.5">
            <span className="qa-legend-flow h-1 w-8 rounded-full" aria-hidden="true" />
            Eau en circulation
          </li>
          <li className="flex items-center gap-2.5">
            <span className="h-1 w-8 rounded-full bg-[#E8F2F5] ring-1 ring-[#08222A]/50" aria-hidden="true" />
            Tuyau au repos
          </li>
          <li className="flex items-center gap-2.5">
            <span className="flex w-8 items-center justify-center gap-1.5" aria-hidden="true">
              <span className="h-3 w-3 rounded-full bg-[#1FA9C6] ring-2 ring-[#0E3A44]" />
              <span className="h-3 w-3 rounded-full bg-[#F4F8F9] ring-2 ring-[#0E3A44]" />
            </span>
            Vanne ouverte / fermée
          </li>
        </ul>
      )}
    </section>
  );
}
