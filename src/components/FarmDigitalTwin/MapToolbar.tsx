'use client';

import React, { useState } from 'react';
import {
  Search,
  RotateCcw,
  Maximize2,
  Minimize2,
  Navigation,
  Mountain,
  Sun,
  Layers,
  ChevronDown
} from 'lucide-react';
import { TUNISIA_SEARCH_LOCATIONS, SearchLocation } from '@/lib/geo/providers';
import { useFarmStore } from '@/stores/useFarmStore';
import { cn } from '@/lib/utils';

interface MapToolbarProps {
  onFlyTo: (center: [number, number], zoom?: number) => void;
  onResetView: () => void;
  onTogglePitch: () => void;
  isFullscreen: boolean;
  onToggleFullscreen: () => void;
  currentPitch: number;
}

export function MapToolbar({
  onFlyTo,
  onResetView,
  onTogglePitch,
  isFullscreen,
  onToggleFullscreen,
  currentPitch,
}: MapToolbarProps) {
  const {
    farm,
    terrain3DEnabled,
    setTerrain3DEnabled,
    sunSimulationEnabled,
    setSunSimulationEnabled
  } = useFarmStore();

  const [searchOpen, setSearchOpen] = useState(false);
  const [customCoords, setCustomCoords] = useState('');

  const handleSelectLocation = (loc: SearchLocation) => {
    onFlyTo(loc.center, loc.zoom);
    setSearchOpen(false);
  };

  const handleCustomCoordinatesSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const parts = customCoords.split(',').map((p) => parseFloat(p.trim()));
    if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
      let lat = parts[0], lng = parts[1];
      if (lat < 20 && lng > 20) {
        lng = parts[0];
        lat = parts[1];
      }
      onFlyTo([lng, lat], 16);
      setSearchOpen(false);
      setCustomCoords('');
    }
  };

  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      {/* Search Location Dropdown */}
      <div className="relative">
        <button
          onClick={() => setSearchOpen(!searchOpen)}
          className="glass-panel px-3 py-1.5 rounded-xl border text-xs font-semibold text-earth-200 hover:text-ink flex items-center gap-1.5 transition-colors"
        >
          <Search className="h-3.5 w-3.5 text-brand-400" />
          <span className="hidden sm:inline">Exploitation</span>
          <ChevronDown className="h-3 w-3 text-earth-400" />
        </button>

        {searchOpen && (
          <div className="absolute top-full right-0 mt-2 w-80 bg-surface border border-line rounded-2xl shadow-2xl p-3 z-50 text-xs space-y-3">
            <div>
              <span className="text-[10px] font-bold text-brand-400 uppercase tracking-wider block mb-1">
                Coordonnées GPS (WGS84)
              </span>
              <form onSubmit={handleCustomCoordinatesSubmit} className="flex gap-1.5">
                <input
                  type="text"
                  placeholder="Ex: 35.0382, 9.4858"
                  value={customCoords}
                  onChange={(e) => setCustomCoords(e.target.value)}
                  className="flex-1 bg-sunken border border-line rounded-xl px-2.5 py-1.5 text-ink font-mono text-xs focus:outline-none focus:border-brand-500"
                />
                <button
                  type="submit"
                  className="px-3 py-1.5 bg-accent hover:bg-accent text-on-accent font-bold rounded-xl"
                >
                  Aller
                </button>
              </form>
            </div>

            <div className="border-t border-line pt-2">
              <span className="text-[10px] font-bold text-earth-400 uppercase tracking-wider block mb-1.5">
                Régions Agricoles Clés en Tunisie
              </span>
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {TUNISIA_SEARCH_LOCATIONS.map((loc) => (
                  <button
                    key={loc.name}
                    onClick={() => handleSelectLocation(loc)}
                    className="w-full text-left px-2.5 py-1.5 rounded-lg hover:bg-highlight text-earth-300 hover:text-ink flex items-center justify-between transition-colors"
                  >
                    <span>{loc.name}</span>
                    <span className="text-[10px] font-mono text-brand-400">{loc.governorate}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 3D Terrain MNT Toggle */}
      <button
        onClick={() => setTerrain3DEnabled(!terrain3DEnabled)}
        className={cn(
          "glass-panel px-2.5 py-1.5 rounded-xl border text-xs font-semibold flex items-center gap-1.5 transition-all",
          terrain3DEnabled
            ? "bg-water-950/80 border-water-500 text-water-300"
            : "border-line text-earth-400 hover:text-ink"
        )}
        title="Activer/Désactiver le relief MNT 3D"
      >
        <Mountain className={cn("h-3.5 w-3.5", terrain3DEnabled ? "text-water-400" : "text-earth-400")} />
        <span className="hidden sm:inline">Relief 3D</span>
      </button>

      {/* Sun Simulation Toggle */}
      <button
        onClick={() => setSunSimulationEnabled(!sunSimulationEnabled)}
        className={cn(
          "glass-panel px-2.5 py-1.5 rounded-xl border text-xs font-semibold flex items-center gap-1.5 transition-all",
          sunSimulationEnabled
            ? "bg-sun-950/80 border-sun-500 text-sun-300"
            : "border-line text-earth-400 hover:text-ink"
        )}
        title="Simulation solaire en temps réel (azimut, hauteur, course de la lumière)"
      >
        <Sun className={cn("h-3.5 w-3.5", sunSimulationEnabled ? "text-sun-400" : "text-earth-400")} />
        <span className="hidden sm:inline">Soleil</span>
      </button>

      {/* 2D / 3D Isometric Pitch Tilt */}
      <button
        onClick={onTogglePitch}
        className={cn(
          "glass-panel px-2.5 py-1.5 rounded-xl border text-xs font-semibold flex items-center gap-1.5 transition-all",
          currentPitch > 10 ? "bg-brand-900/60 border-brand-500 text-brand-300" : "border-line text-earth-300 hover:text-ink"
        )}
        title="Basculer perspective 2D Nadir / 3D Inclinée"
      >
        <Navigation className={cn("h-3.5 w-3.5 transition-transform", currentPitch > 10 ? "text-brand-400 rotate-45" : "text-earth-400")} />
        <span>{currentPitch > 10 ? '3D (50°)' : '2D (Nadir)'}</span>
      </button>

      {/* Reset Camera to Farm Center & Bounds */}
      <button
        onClick={onResetView}
        className="glass-panel p-2 rounded-xl border text-earth-300 hover:text-ink hover:bg-highlight transition-colors"
        title="Recentrer et cadrer l'exploitation"
      >
        <RotateCcw className="h-3.5 w-3.5" />
      </button>

      {/* Fullscreen Toggle */}
      <button
        onClick={onToggleFullscreen}
        className="glass-panel p-2 rounded-xl border text-earth-300 hover:text-ink hover:bg-highlight transition-colors"
        title="Plein écran"
      >
        {isFullscreen ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
      </button>
    </div>
  );
}
