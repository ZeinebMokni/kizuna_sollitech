'use client';

import React, { useEffect, useState } from 'react';
import { Sun, Compass, Clock, ArrowUpRight, Sparkles, Eye, EyeOff } from 'lucide-react';
import { calculateSunPosition, SunPosition } from '@/lib/geo/sun';
import { useFarmStore } from '@/stores/useFarmStore';
import { cn } from '@/lib/utils';

interface SunSimulationPanelProps {
  onRotateCameraToSun?: (azimuth: number) => void;
}

export function SunSimulationPanel({ onRotateCameraToSun }: SunSimulationPanelProps) {
  const { farm, sunSimulationEnabled, setSunSimulationEnabled } = useFarmStore();
  const [sunData, setSunData] = useState<SunPosition | null>(null);
  const [currentTime, setCurrentTime] = useState<string>('');
  const [customHour, setCustomHour] = useState<number | null>(null);

  useEffect(() => {
    const updateSun = () => {
      const now = new Date();
      if (customHour !== null) {
        now.setHours(customHour, 0, 0, 0);
      }
      const [lng, lat] = farm.centerCoordinates;
      const pos = calculateSunPosition(now, lat, lng);
      setSunData(pos);
      setCurrentTime(
        now.toLocaleTimeString('fr-FR', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        })
      );
    };

    updateSun();
    const interval = setInterval(updateSun, 1000);
    return () => clearInterval(interval);
  }, [farm.centerCoordinates, customHour]);

  if (!sunData) return null;

  // Azimuth from North (0° = N, 90° = E, 180° = S, 270° = W)
  // Arrow rotation: pointing in the direction the light is travelling (from sun towards center) or where the sun is located
  const sunBearingDeg = sunData.azimuth;

  return (
    <div className="glass-panel p-3.5 rounded-2xl border border-sun-500/30 text-xs space-y-3 max-w-xs text-ink">
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b border-line">
        <div className="flex items-center gap-2">
          <div className="h-7 w-7 rounded-lg bg-sun-500/20 border border-sun-500/40 flex items-center justify-center text-sun-400">
            <Sun className={cn("h-4 w-4", sunData.isDaylight ? "animate-spin-slow text-sun-400" : "text-earth-400")} />
          </div>
          <div>
            <span className="font-bold text-ink text-xs block">
              Orientation Solaire en Direct
            </span>
            <span className="text-[10px] text-sun-400 font-mono">
              {sunData.isDaylight ? 'Ensoleillement Actif' : 'Nuit Astronomique'}
            </span>
          </div>
        </div>
        <button
          onClick={() => setSunSimulationEnabled(!sunSimulationEnabled)}
          className={cn(
            "p-1.5 rounded-lg border text-xs transition-colors",
            sunSimulationEnabled
              ? "bg-sun-500/20 border-sun-500/40 text-sun-300"
              : "bg-earth-800 border-earth-700 text-earth-400 hover:text-ink"
          )}
          title={sunSimulationEnabled ? "Masquer le faisceau solaire" : "Afficher le faisceau solaire"}
        >
          {sunSimulationEnabled ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
        </button>
      </div>

      {/* Sun Direction Compass Dial */}
      <div className="flex items-center gap-3 bg-sunken p-3 rounded-xl border border-line">
        <div className="relative h-14 w-14 rounded-full border border-earth-700 flex items-center justify-center bg-sunken flex-shrink-0">
          {/* Cardinal Points */}
          <span className="absolute top-0.5 text-[8px] font-bold text-earth-400">N</span>
          <span className="absolute right-0.5 text-[8px] font-bold text-earth-400">E</span>
          <span className="absolute bottom-0.5 text-[8px] font-bold text-earth-400">S</span>
          <span className="absolute left-0.5 text-[8px] font-bold text-earth-400">O</span>

          {/* Sun Direction Indicator Needle */}
          <div
            className="absolute inset-0 flex items-center justify-center transition-transform duration-700 pointer-events-none"
            style={{ transform: `rotate(${sunBearingDeg}deg)` }}
          >
            <div className="h-12 w-0.5 relative flex flex-col items-center">
              {/* Sun Icon at the edge */}
              <div className="h-3 w-3 rounded-full bg-sun-400 shadow-[0_0_8px_#E39A26] border border-on-accent" />
            </div>
          </div>

          <div className="h-2 w-2 rounded-full bg-brand-400" />
        </div>

        {/* Readouts */}
        <div className="flex-1 space-y-1">
          <div className="flex justify-between items-center">
            <span className="text-earth-400 text-[10px]">Origine de la Lumière :</span>
            <span className="font-bold text-sun-300 font-mono text-[11px]">
              {sunData.compassDirection} ({sunData.azimuth}°)
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-earth-400 text-[10px]">Hauteur (Élévation) :</span>
            <span className={cn(
              "font-bold font-mono text-[11px]",
              sunData.altitude > 0 ? "text-sun-400" : "text-water-400"
            )}>
              {sunData.altitude > 0 ? `+${sunData.altitude}°` : `${sunData.altitude}°`}
            </span>
          </div>
          <div className="flex justify-between items-center text-[10px] text-earth-400">
            <span>Heure Solaire :</span>
            <span className="font-mono text-earth-200">{currentTime}</span>
          </div>
        </div>
      </div>

      {/* Sun Times (Aube, Midi, Crépuscule) */}
      <div className="grid grid-cols-3 gap-1.5 text-center text-[10px]">
        <div className="bg-sunken p-1.5 rounded-lg border border-line">
          <span className="text-earth-500 block">Lever</span>
          <span className="font-mono font-bold text-sun-300">{sunData.sunrise}</span>
        </div>
        <div className="bg-sunken p-1.5 rounded-lg border border-line">
          <span className="text-earth-500 block">Zénith</span>
          <span className="font-mono font-bold text-ink">{sunData.solarNoon}</span>
        </div>
        <div className="bg-sunken p-1.5 rounded-lg border border-line">
          <span className="text-earth-500 block">Coucher</span>
          <span className="font-mono font-bold text-sun-400">{sunData.sunset}</span>
        </div>
      </div>

      {/* Time of day slider for simulation */}
      <div className="space-y-1 pt-1 border-t border-line">
        <div className="flex justify-between text-[10px] text-earth-400">
          <span>Simuler une heure de la journée :</span>
          {customHour !== null ? (
            <button
              onClick={() => setCustomHour(null)}
              className="text-brand-400 font-bold hover:underline"
            >
              Temps Réel
            </button>
          ) : (
            <span className="text-brand-400 font-mono">En Direct</span>
          )}
        </div>
        <input
          type="range"
          min="5"
          max="20"
          step="1"
          value={customHour !== null ? customHour : new Date().getHours()}
          onChange={(e) => setCustomHour(parseInt(e.target.value))}
          className="w-full accent-sun-500 h-1.5 bg-earth-800 rounded-lg cursor-pointer"
        />
        <div className="flex justify-between text-[9px] font-mono text-earth-500">
          <span>05h (Aube)</span>
          <span>12h (Midi)</span>
          <span>16h (Après-midi)</span>
          <span>20h (Crépuscule)</span>
        </div>
      </div>

      {/* Align Camera to Sun button */}
      {onRotateCameraToSun && (
        <button
          onClick={() => onRotateCameraToSun(sunData.azimuth)}
          className="w-full py-1.5 rounded-xl bg-gradient-to-r from-sun-600/30 to-sun-500/20 hover:from-sun-600/50 hover:to-sun-500/40 text-sun-300 border border-sun-500/30 font-bold text-[11px] flex items-center justify-center gap-1.5 transition-all shadow-md"
        >
          <ArrowUpRight className="h-3.5 w-3.5" />
          <span>Orienter la Caméra Face au Soleil</span>
        </button>
      )}
    </div>
  );
}
