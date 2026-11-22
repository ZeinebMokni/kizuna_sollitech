'use client';

import React from 'react';
import {
  Satellite,
  Sprout,
  Droplets,
  Thermometer,
  Activity,
  Layers,
  ShieldAlert,
  History,
  Mountain,
  Sun,
  Zap
} from 'lucide-react';
import { useFarmStore } from '@/stores/useFarmStore';
import { MapLayerMode } from '@/types';
import { cn } from '@/lib/utils';

export function LayerSwitcher() {
  const { mapLayerMode, setMapLayerMode, tileProviderId, setTileProviderId } = useFarmStore();

  const layers: { mode: MapLayerMode; label: string; icon: any; desc: string }[] = [
    { mode: 'satellite', label: 'Satellite Vrai', icon: Satellite, desc: 'Imagerie Satellite Haute Résolution & Sentinel-2' },
    { mode: 'ndvi', label: 'Indice NDVI', icon: Sprout, desc: 'Biomasse végétale calculée (NIR - RED)' },
    { mode: 'elevation', label: 'Altimétrie & Pentes', icon: Mountain, desc: 'Courbes de niveau et relief MNT' },
    { mode: 'moisture', label: 'Humidité Sol', icon: Droplets, desc: 'Sondes capacitives & profil hydrique' },
    { mode: 'temperature', label: 'Température', icon: Thermometer, desc: 'Stress thermique & canopée' },
    { mode: 'irrigation', label: 'Irrigation', icon: Activity, desc: 'Réseau de canalisations & pompes actives' },
    { mode: 'energy', label: 'Énergie Solaire', icon: Zap, desc: 'Panneaux solaires & production photovoltaïque en temps réel' },
    { mode: 'crop', label: 'Cultures', icon: Layers, desc: 'Variétés d\'assolement parcelles' },
    { mode: 'alerts', label: 'Alertes', icon: ShieldAlert, desc: 'Balises de stress critique' },
  ];

  return (
    <div className="glass-panel p-1.5 rounded-2xl border flex flex-wrap items-center gap-1">
      {/* Basemap Toggle Quick Pills */}
      <div className="flex items-center gap-1 pr-2 border-r border-line mr-1">
        <button
          onClick={() => setTileProviderId('esriWorldImagery')}
          className={cn(
            "px-2.5 py-1 rounded-lg text-[11px] font-bold transition-all",
            tileProviderId === 'esriWorldImagery'
              ? "bg-accent text-on-accent shadow-sm"
              : "text-earth-400 hover:text-ink hover:bg-earth-800"
          )}
          title="Imagerie satellite haute définition Maxar/Airbus/Esri"
        >
          Satellite
        </button>
        <button
          onClick={() => setTileProviderId('sentinel2Cloudless')}
          className={cn(
            "px-2.5 py-1 rounded-lg text-[11px] font-bold transition-all",
            tileProviderId === 'sentinel2Cloudless'
              ? "bg-accent text-on-accent shadow-sm"
              : "text-earth-400 hover:text-ink hover:bg-earth-800"
          )}
          title="Copernicus Sentinel-2 EOX 10m"
        >
          Sentinel-2
        </button>
        <button
          onClick={() => setTileProviderId('osmStandard')}
          className={cn(
            "px-2.5 py-1 rounded-lg text-[11px] font-bold transition-all",
            tileProviderId === 'osmStandard'
              ? "bg-earth-700 text-ink shadow-sm"
              : "text-earth-400 hover:text-ink hover:bg-earth-800"
          )}
          title="Plan des rues OpenStreetMap"
        >
          Rues
        </button>
      </div>

      {/* Main Agronomic Layer Modes */}
      {layers.map((layer) => {
        const Icon = layer.icon;
        const active = mapLayerMode === layer.mode;
        return (
          <button
            key={layer.mode}
            onClick={() => setMapLayerMode(layer.mode)}
            title={layer.desc}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all",
              active
                ? "bg-gradient-to-r from-accent to-accent-deep text-on-accent shadow-lg shadow-shade/20 border border-brand-500/40"
                : "text-earth-300 hover:bg-highlight hover:text-ink"
            )}
          >
            <Icon className={cn("h-3.5 w-3.5", active ? "text-brand-300" : "text-earth-400")} />
            <span>{layer.label}</span>
          </button>
        );
      })}
    </div>
  );
}
