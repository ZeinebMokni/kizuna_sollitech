'use client';

import { useEffect, useState } from 'react';
import { ArrowUpRight, ChevronDown, ChevronUp, Eye, EyeOff, Sun } from 'lucide-react';
import { calculateSunPosition, SunPosition } from '@/lib/geo/sun';
import { useFarmStore } from '@/stores/useFarmStore';
import { cn } from '@/lib/utils';

interface SunSimulationPanelProps {
  onRotateCameraToSun?: (azimuth: number) => void;
}

export function SunSimulationPanel({ onRotateCameraToSun }: SunSimulationPanelProps) {
  const { farm, sunSimulationEnabled, setSunSimulationEnabled } = useFarmStore();
  const [sunData, setSunData] = useState<SunPosition | null>(null);
  const [currentTime, setCurrentTime] = useState('');
  const [customHour, setCustomHour] = useState<number | null>(null);
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    const updateSun = () => {
      const now = new Date();
      if (customHour !== null) now.setHours(customHour, 0, 0, 0);
      const [lng, lat] = farm.centerCoordinates;
      setSunData(calculateSunPosition(now, lat, lng));
      setCurrentTime(now.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
    };

    updateSun();
    const interval = setInterval(updateSun, 1000);
    return () => clearInterval(interval);
  }, [farm.centerCoordinates, customHour]);

  if (!sunData) return null;

  return (
    <section className="w-72 max-w-[calc(100vw-2rem)] space-y-3 rounded-2xl border border-sun-500/30 p-3.5 text-xs text-ink glass-panel">
      <header className="flex items-center justify-between border-b border-line pb-2">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg border border-sun-500/40 bg-sun-500/20 text-sun-400">
            <Sun className={cn('h-4 w-4', sunData.isDaylight && 'animate-spin-slow')} />
          </div>
          <div>
            <span className="block text-xs font-bold text-ink">Soleil en direct</span>
            <span className="font-mono text-[10px] text-sun-400">{sunData.isDaylight ? 'Ensoleillement actif' : 'Soleil sous l’horizon'}</span>
          </div>
        </div>
        <button onClick={() => setSunSimulationEnabled(!sunSimulationEnabled)} className="rounded-lg border border-line p-1.5 text-earth-400 transition-colors hover:bg-earth-800 hover:text-ink" title="Afficher ou masquer le faisceau solaire">
          {sunSimulationEnabled ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
        </button>
      </header>

      <div className="grid grid-cols-3 gap-1.5 rounded-xl border border-line bg-sunken p-2.5 text-center">
        <Metric label="Direction" value={`${sunData.compassDirection} ${sunData.azimuth}°`} />
        <Metric label="Hauteur" value={`${sunData.altitude > 0 ? '+' : ''}${sunData.altitude}°`} />
        <Metric label="Heure" value={currentTime.slice(0, 5)} />
      </div>

      <button type="button" aria-expanded={showDetails} onClick={() => setShowDetails((current) => !current)} className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-line py-2 text-[11px] font-semibold text-sun-400 transition-colors hover:bg-sun-500/10">
        {showDetails ? 'Voir moins' : 'Voir plus'}
        {showDetails ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
      </button>

      {showDetails && (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-1.5 text-center text-[10px]">
            <Metric label="Lever" value={sunData.sunrise} />
            <Metric label="Zénith" value={sunData.solarNoon} />
            <Metric label="Coucher" value={sunData.sunset} />
          </div>

          <div className="space-y-1 border-t border-line pt-2">
            <div className="flex justify-between text-[10px] text-earth-400">
              <span>Simuler une heure</span>
              {customHour !== null ? (
                <button onClick={() => setCustomHour(null)} className="font-bold text-brand-400 hover:underline">Temps réel</button>
              ) : <span className="font-mono text-brand-400">En direct</span>}
            </div>
            <input type="range" min="5" max="20" step="1" value={customHour ?? new Date().getHours()} onChange={(event) => setCustomHour(parseInt(event.target.value, 10))} className="h-1.5 w-full cursor-pointer accent-sun-500" />
          </div>

          {onRotateCameraToSun && (
            <button onClick={() => onRotateCameraToSun(sunData.azimuth)} className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-sun-500/30 bg-sun-500/10 py-2 text-[11px] font-bold text-sun-300 transition-all hover:bg-sun-500/20">
              <ArrowUpRight className="h-3.5 w-3.5" /> Orienter la caméra vers le soleil
            </button>
          )}
        </div>
      )}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-line bg-surface p-1.5">
      <span className="block text-[9px] text-earth-400">{label}</span>
      <span className="font-mono text-[11px] font-bold text-ink">{value}</span>
    </div>
  );
}
