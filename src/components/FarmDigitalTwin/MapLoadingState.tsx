'use client';

import React from 'react';
import { Compass, Satellite, Sparkles, Layers } from 'lucide-react';

interface MapLoadingStateProps {
  message?: string;
}

export function MapLoadingState({ message = 'Chargement de l\'imagerie satellite & calibrage NDVI...' }: MapLoadingStateProps) {
  return (
    <div className="absolute inset-0 z-50 bg-sunken/90 backdrop-blur-md flex flex-col items-center justify-center p-6 text-center select-none">
      <div className="relative mb-6">
        {/* Outer glowing pulsing ring */}
        <div className="h-20 w-20 rounded-full border-2 border-brand-500/30 animate-ping absolute inset-0" />
        <div className="h-20 w-20 rounded-full border-2 border-dashed border-accent animate-spin flex items-center justify-center bg-brand-950/40 shadow-2xl shadow-shade/20">
          <Satellite className="h-8 w-8 text-brand-400 animate-pulse" />
        </div>
      </div>

      <div className="space-y-1.5 max-w-sm">
        <h4 className="text-sm font-black text-ink tracking-wider">
          QATRA · JUMEAU NUMÉRIQUE SIG
        </h4>
        <p className="text-xs text-earth-300 font-medium">
          {message}
        </p>
        <div className="pt-2 flex items-center justify-center gap-2 text-[10px] text-brand-400/80 font-mono">
          <span>Copernicus Sentinel-2</span>
          <span>•</span>
          <span>Résolution 10m</span>
          <span>•</span>
          <span>WGS84 EPSG:3857</span>
        </div>
      </div>
    </div>
  );
}
