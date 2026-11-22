'use client';

import React from 'react';
import { Droplets } from 'lucide-react';
import { useFarmStore } from '@/stores/useFarmStore';
import { moistureGradientCss, MOISTURE_STOPS } from '@/lib/geo/moisture';

/**
 * Legend for the live water view on the digital twin: soil-moisture colour
 * scale, flowing vs idle pipes, and open / closed valves (clickable on the map).
 */
export function WaterNetworkLegend() {
  const { farm, emergencyStopActive } = useFarmStore();
  const open = emergencyStopActive ? [] : farm.zones.filter((z) => z.irrigationStatus === 'active');
  const min = MOISTURE_STOPS[0].at;
  const max = MOISTURE_STOPS[MOISTURE_STOPS.length - 1].at;

  return (
    <div className="glass-panel rounded-2xl p-3.5 text-xs w-72 space-y-3 text-ink">
      <div className="flex items-center gap-2 pb-2 border-b border-line/70">
        <Droplets className="h-4 w-4 text-water-400" />
        <span className="font-bold">Eau & humidité du sol</span>
      </div>

      {/* Moisture scale */}
      <div className="space-y-1.5">
        <div className="h-2.5 rounded-full ring-1 ring-inset ring-black/10" style={{ background: moistureGradientCss() }} />
        <div className="flex justify-between text-[11px] text-earth-300 tabular-nums">
          <span>Sec · {min} %</span>
          <span>35 %</span>
          <span>65 %</span>
          <span>Humide · {max} %</span>
        </div>
      </div>

      {/* Pipes & valves */}
      <ul className="space-y-1.5 text-[11px] text-earth-200">
        <li className="flex items-center gap-2.5">
          <span className="qa-legend-flow h-1 w-8 rounded-full" aria-hidden="true" />
          Eau en circulation (vanne ouverte)
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
          Vanne ouverte / fermée · cliquer pour l'actionner
        </li>
      </ul>

      <p className="pt-2 border-t border-line/70 text-[11px] text-earth-300">
        {emergencyStopActive
          ? "Arrêt d'urgence actif : toutes les vannes sont coupées."
          : open.length === 0
          ? 'Aucune vanne ouverte.'
          : `${open.length} vanne${open.length > 1 ? 's' : ''} ouverte${open.length > 1 ? 's' : ''} : ${open
              .map((z) => z.name.split(' - ')[0])
              .join(', ')}`}
      </p>
    </div>
  );
}
