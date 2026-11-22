'use client';

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import {
  Layers,
  Eye,
  Maximize2,
  RotateCcw,
  Compass,
  Droplets,
  Sun,
  Thermometer,
  ShieldAlert,
  Play,
  Square,
  CheckCircle2,
  AlertTriangle,
  Info,
  ChevronRight,
  Sparkles,
  Zap
} from 'lucide-react';
import { useFarmStore } from '@/stores/useFarmStore';
import { MapLayerMode, FarmZone, HealthStatus } from '@/types';
import { cn, formatNumber } from '@/lib/utils';
import { fetchZoneHistory, requestAgenticDecision, type ZoneHistory } from '@/lib/qatra/client';

export function FarmDigitalTwinMap() {
  const {
    farm,
    selectedZoneId,
    selectZone,
    mapLayerMode,
    setMapLayerMode,
    startIrrigation,
    stopIrrigation,
    emergencyStopActive,
  } = useFarmStore();

  const [mapType, setMapType] = useState<'satellite' | 'street'>('satellite');
  const [zoomLevel, setZoomLevel] = useState(1);
  const [hoveredZoneId, setHoveredZoneId] = useState<string | null>(null);

  const selectedZone = farm.zones.find((z) => z.id === selectedZoneId) || farm.zones[0];

  // Helper to determine zone color by layer mode
  const getZoneFillColor = (zone: FarmZone, isHovered: boolean, isSelected: boolean) => {
    if (zone.status === 'irrigating') {
      return isSelected ? 'rgba(50, 156, 150, 0.75)' : 'rgba(50, 156, 150, 0.55)';
    }

    switch (mapLayerMode) {
      case 'health':
        if (zone.status === 'healthy') return isSelected ? 'rgba(154, 180, 122, 0.65)' : 'rgba(124, 152, 91, 0.45)';
        if (zone.status === 'warning') return isSelected ? 'rgba(239, 180, 71, 0.65)' : 'rgba(239, 180, 71, 0.45)';
        return isSelected ? 'rgba(226, 116, 99, 0.75)' : 'rgba(226, 116, 99, 0.55)';

      case 'moisture':
        if (zone.soilMoisturePercent < 20) return 'rgba(204, 78, 60, 0.6)';
        if (zone.soilMoisturePercent < 35) return 'rgba(227, 154, 38, 0.55)';
        if (zone.soilMoisturePercent < 50) return 'rgba(124, 152, 91, 0.55)';
        return 'rgba(50, 156, 150, 0.65)';

      case 'temperature':
        if (zone.temperatureC > 34) return 'rgba(176, 62, 46, 0.65)';
        if (zone.temperatureC > 29) return 'rgba(212, 109, 63, 0.55)';
        return 'rgba(86, 184, 178, 0.5)';

      case 'energy':
        return zone.dailyEnergyKwh > 10 ? 'rgba(239, 180, 71, 0.6)' : 'rgba(124, 152, 91, 0.45)';

      case 'crop':
        if (zone.cropType.includes('Olivier')) return 'rgba(170, 190, 100, 0.55)';
        if (zone.cropType.includes('Tomate')) return 'rgba(196, 72, 64, 0.55)';
        if (zone.cropType.includes('Grenadier')) return 'rgba(140, 70, 96, 0.55)';
        if (zone.cropType.includes('Piment')) return 'rgba(204, 78, 60, 0.55)';
        return 'rgba(124, 152, 91, 0.55)';

      case 'prediction':
        return zone.status === 'critical' ? 'rgba(176, 62, 46, 0.7)' : 'rgba(124, 152, 91, 0.45)';

      default:
        return 'rgba(124, 152, 91, 0.5)';
    }
  };

  const getZoneStrokeColor = (zone: FarmZone, isSelected: boolean) => {
    if (isSelected) return '#FFFFFF';
    if (zone.status === 'irrigating') return '#56B8B2';
    if (zone.status === 'critical') return '#D9573F';
    if (zone.status === 'warning') return '#E39A26';
    return '#7C985B';
  };

  const layerOptions: { mode: MapLayerMode; label: string; icon: any }[] = [
    { mode: 'health', label: 'Santé Végétale', icon: CheckCircle2 },
    { mode: 'moisture', label: 'Humidité Sol', icon: Droplets },
    { mode: 'temperature', label: 'Température', icon: Thermometer },
    { mode: 'irrigation', label: 'Réseau Irrigation', icon: Droplets },
    { mode: 'energy', label: 'Énergie Solaire', icon: Sun },
    { mode: 'prediction', label: 'Risque Hydrique', icon: ShieldAlert },
    { mode: 'crop', label: 'Variétés Cultures', icon: Layers },
  ];

  return (
    <div className="relative w-full h-[calc(100vh-8rem)] min-h-[600px] rounded-2xl overflow-hidden border border-line bg-sunken flex flex-col md:flex-row shadow-2xl">
      {/* Top Map Floating Bar: Layer Mode Switcher */}
      <div className="absolute top-4 left-4 z-20 flex flex-wrap items-center gap-1.5 glass-panel p-1.5 rounded-xl border max-w-[calc(100%-2rem)]">
        <span className="text-[10px] font-bold text-earth-400 uppercase tracking-wider px-2 hidden sm:inline">
          Couche
        </span>
        {layerOptions.map((opt) => {
          const Icon = opt.icon;
          const active = mapLayerMode === opt.mode;
          return (
            <button
              key={opt.mode}
              onClick={() => setMapLayerMode(opt.mode)}
              className={cn(
                "flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all",
                active
                  ? "bg-accent text-on-accent shadow-md shadow-shade/20 font-semibold"
                  : "text-earth-300 hover:bg-highlight hover:text-ink"
              )}
            >
              <Icon className="h-3.5 w-3.5" />
              <span className="hidden md:inline">{opt.label}</span>
            </button>
          );
        })}
      </div>

      {/* Map Controls: Satellite/Street, Reset View, Zoom */}
      <div className="absolute top-20 left-4 z-20 flex flex-col gap-2">
        <div className="glass-panel p-1 rounded-xl border flex flex-col">
          <button
            onClick={() => setMapType(mapType === 'satellite' ? 'street' : 'satellite')}
            className={cn(
              "p-2 rounded-lg text-xs font-semibold transition-colors flex items-center justify-center",
              mapType === 'satellite' ? "bg-brand-800 text-ink" : "text-earth-300 hover:bg-earth-800"
            )}
            title="Basculer Imagerie Satellite / Carte Vectorielle"
          >
            <Eye className="h-4 w-4" />
          </button>
          <button
            onClick={() => setZoomLevel(1)}
            className="p-2 rounded-lg text-xs text-earth-300 hover:bg-earth-800 hover:text-ink transition-colors"
            title="Recentrer sur le Domaine"
          >
            <RotateCcw className="h-4 w-4" />
          </button>
          <button
            onClick={() => setZoomLevel(prev => Math.min(prev + 0.2, 1.8))}
            className="p-2 rounded-lg text-xs font-mono font-bold text-earth-300 hover:bg-earth-800"
          >
            +
          </button>
          <button
            onClick={() => setZoomLevel(prev => Math.max(prev - 0.2, 0.8))}
            className="p-2 rounded-lg text-xs font-mono font-bold text-earth-300 hover:bg-earth-800"
          >
            -
          </button>
        </div>
      </div>

      {/* Interactive Map Canvas / SVG GIS Digital Twin */}
      <div className="relative flex-1 w-full h-full overflow-hidden bg-canvas select-none">
        {/* Background Satellite Texture / Raster Grid Simulation */}
        <div 
          className={cn(
            "absolute inset-0 transition-opacity duration-700 bg-cover bg-center",
            mapType === 'satellite' ? "opacity-45" : "opacity-15"
          )}
          style={{
            backgroundImage: `radial-gradient(circle at 50% 50%, rgba(58, 76, 42, 0.3) 0%, rgba(26, 23, 19, 0.95) 100%), linear-gradient(rgba(124, 152, 91, 0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(124, 152, 91, 0.08) 1px, transparent 1px)`,
            backgroundSize: '100% 100%, 40px 40px, 40px 40px',
          }}
        />

        {/* SVG Interactive GIS Surface */}
        <div 
          className="absolute inset-0 flex items-center justify-center p-8 transition-transform duration-300"
          style={{ transform: `scale(${zoomLevel})` }}
        >
          <svg
            viewBox="0 0 1000 700"
            className="w-full h-full max-w-4xl max-h-[600px] drop-shadow-2xl"
          >
            <defs>
              {/* Pulsing water flow animation for active irrigation */}
              <pattern id="waterLines" width="20" height="20" patternUnits="userSpaceOnUse">
                <line x1="0" y1="0" x2="20" y2="20" stroke="#56B8B2" strokeWidth="2" strokeDasharray="4 4" className="animate-water-flow" />
              </pattern>

              {/* Holographic grid glow */}
              <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="6" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
            </defs>

            {/* Farm Perimeter Boundary */}
            <polygon
              points="150,150 820,130 860,560 210,580 140,360"
              fill="rgba(58, 76, 42, 0.15)"
              stroke="#9AB47A"
              strokeWidth="2.5"
              strokeDasharray="6 4"
            />

            {/* Zone 1: Oliviers (Top Left) */}
            <g
              onClick={() => selectZone('zone-1')}
              onMouseEnter={() => setHoveredZoneId('zone-1')}
              onMouseLeave={() => setHoveredZoneId(null)}
              className="cursor-pointer transition-all duration-300"
            >
              <polygon
                points="180,180 470,170 460,350 170,340"
                fill={getZoneFillColor(farm.zones[0], hoveredZoneId === 'zone-1', selectedZoneId === 'zone-1')}
                stroke={getZoneStrokeColor(farm.zones[0], selectedZoneId === 'zone-1')}
                strokeWidth={selectedZoneId === 'zone-1' ? "3.5" : "1.8"}
                className="transition-colors duration-300"
              />
              <text x="240" y="250" fill="#FFFFFF" fontSize="13" fontWeight="bold">Zone A · Oliviers</text>
              <text x="240" y="270" fill="#F2ECE2" fontSize="11">4.5 Ha · {farm.zones[0].soilMoisturePercent}% Humidité</text>
            </g>

            {/* Zone 2: Tomates Serres (Top Right) */}
            <g
              onClick={() => selectZone('zone-2')}
              onMouseEnter={() => setHoveredZoneId('zone-2')}
              onMouseLeave={() => setHoveredZoneId(null)}
              className="cursor-pointer transition-all duration-300"
            >
              <polygon
                points="490,165 790,150 780,340 480,345"
                fill={getZoneFillColor(farm.zones[1], hoveredZoneId === 'zone-2', selectedZoneId === 'zone-2')}
                stroke={getZoneStrokeColor(farm.zones[1], selectedZoneId === 'zone-2')}
                strokeWidth={selectedZoneId === 'zone-2' ? "3.5" : "1.8"}
                className="transition-colors duration-300"
              />
              <text x="540" y="240" fill="#FFFFFF" fontSize="13" fontWeight="bold">Zone B · Serres Tomates</text>
              <text x="540" y="260" fill="#F2ECE2" fontSize="11">2.2 Ha · {farm.zones[1].soilMoisturePercent}% (Vigilance)</text>
            </g>

            {/* Zone 3: Grenadiers (Middle Right) */}
            <g
              onClick={() => selectZone('zone-3')}
              onMouseEnter={() => setHoveredZoneId('zone-3')}
              onMouseLeave={() => setHoveredZoneId(null)}
              className="cursor-pointer transition-all duration-300"
            >
              <polygon
                points="480,360 820,355 810,520 510,530"
                fill={getZoneFillColor(farm.zones[2], hoveredZoneId === 'zone-3', selectedZoneId === 'zone-3')}
                stroke={getZoneStrokeColor(farm.zones[2], selectedZoneId === 'zone-3')}
                strokeWidth={selectedZoneId === 'zone-3' ? "3.5" : "1.8"}
                className="transition-colors duration-300"
              />
              <text x="570" y="440" fill="#FFFFFF" fontSize="13" fontWeight="bold">Zone C · Grenadiers</text>
              <text x="570" y="460" fill="#F2ECE2" fontSize="11">3.8 Ha · {farm.zones[2].soilMoisturePercent}% Humidité</text>
            </g>

            {/* Zone 4: Piments Baklouti (Critical Zone) */}
            <g
              onClick={() => selectZone('zone-4')}
              onMouseEnter={() => setHoveredZoneId('zone-4')}
              onMouseLeave={() => setHoveredZoneId(null)}
              className="cursor-pointer transition-all duration-300"
            >
              <polygon
                points="180,360 460,365 470,540 220,550"
                fill={getZoneFillColor(farm.zones[3], hoveredZoneId === 'zone-4', selectedZoneId === 'zone-4')}
                stroke={getZoneStrokeColor(farm.zones[3], selectedZoneId === 'zone-4')}
                strokeWidth={selectedZoneId === 'zone-4' ? "4" : "2"}
                className="transition-colors duration-300"
              />
              {/* Alert Beacon Pulse */}
              <circle cx="320" cy="450" r="14" fill="#D9573F" opacity="0.3" className="animate-ping" />
              <circle cx="320" cy="450" r="7" fill="#D9573F" />
              <text x="240" y="420" fill="#FFFFFF" fontSize="13" fontWeight="bold">Zone D · Piments Baklouti</text>
              <text x="240" y="480" fill="#F2B5AB" fontSize="11" fontWeight="bold">
                {farm.zones[3].status === 'irrigating' ? '💧 Irrigation en cours' : '⚠️ 14% Humidité — Stress Critique'}
              </text>
            </g>

            {/* Water Well, Solar Array & Pump Station Node */}
            <g transform="translate(475, 340)">
              {/* Solar Array Icon */}
              <rect x="-35" y="-30" width="30" height="20" rx="3" fill="#257F7B" stroke="#56B8B2" strokeWidth="1.5" />
              <text x="-32" y="-16" fill="#FFFFFF" fontSize="8" fontWeight="bold">PV 18kW</text>

              {/* Central Well & Pump Station */}
              <circle cx="0" cy="0" r="14" fill="#3A4C2A" stroke="#9AB47A" strokeWidth="2.5" />
              <circle cx="0" cy="0" r="4" fill="#9AB47A" className="animate-ping" />
              <text x="-40" y="26" fill="#9AB47A" fontSize="10" fontWeight="bold">Forage & Station Solaire</text>
            </g>

            {/* ESP32 LoRa Gateway Antenna Node */}
            <g transform="translate(490, 200)">
              <circle cx="0" cy="0" r="8" fill="#9AB47A" stroke="#FFFFFF" strokeWidth="1.5" />
              <circle cx="0" cy="0" r="16" fill="none" stroke="#9AB47A" strokeWidth="1" strokeDasharray="3 3" className="animate-spin" />
              <text x="12" y="4" fill="#B3C796" fontSize="9" fontWeight="bold">ESP32 Gateway</text>
            </g>
          </svg>
        </div>

        {/* Floating Map Legend & Attribution */}
        <div className="absolute bottom-4 left-4 z-20 glass-panel px-3 py-2 rounded-xl border flex items-center gap-4 text-[11px] text-earth-300">
          <div className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-brand-400" />
            <span>Optimal (&gt;30%)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-sun-400" />
            <span>Vigilance (&lt;25%)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-alert-500 animate-pulse" />
            <span>Stress Critique (&lt;15%)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-water-400 animate-ping" />
            <span>Irrigation Active</span>
          </div>
          <span className="text-[10px] text-earth-500 border-l border-earth-700 pl-2">
            Système Géoréférencé WGS84
          </span>
        </div>
      </div>

      {/* Right Side Inspection Panel (Flagship Zone Detail) */}
      <div className="w-full md:w-96 bg-surface border-t md:border-t-0 md:border-l border-line flex flex-col z-20 overflow-y-auto">
        <div className="p-4 border-b border-line flex items-center justify-between bg-raised">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-brand-400">
              Inspection Parcellaire en Direct
            </span>
            <h3 className="text-base font-bold text-ink">{selectedZone.name}</h3>
          </div>
          <span
            className={cn(
              "px-2.5 py-1 text-[11px] font-bold rounded-full capitalize border",
              selectedZone.status === 'healthy' && "bg-brand-500/20 text-brand-400 border-brand-500/30",
              selectedZone.status === 'warning' && "bg-sun-500/20 text-sun-400 border-sun-500/30",
              selectedZone.status === 'critical' && "bg-alert-500/20 text-alert-400 border-alert-500/30 animate-pulse",
              selectedZone.status === 'irrigating' && "bg-water-500/20 text-water-400 border-water-500/30"
            )}
          >
            {selectedZone.status === 'irrigating' ? 'Arrosage en cours' : selectedZone.status}
          </span>
        </div>

        {/* Zone Key Specs */}
        <div className="p-4 space-y-4 flex-1">
          {/* Quick Metrics Grid */}
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-sunken p-3 rounded-xl border border-line">
              <span className="text-[10px] text-earth-400 flex items-center gap-1">
                <Droplets className="h-3 w-3 text-water-400" /> Humidité Sol
              </span>
              <p className="text-xl font-black text-ink mt-1">
                {selectedZone.soilMoisturePercent}%
              </p>
              <div className="w-full bg-earth-800 h-1.5 rounded-full overflow-hidden mt-1.5">
                <div
                  className={cn(
                    "h-full rounded-full transition-all duration-500",
                    selectedZone.soilMoisturePercent < 20 ? "bg-alert-500" : "bg-brand-500"
                  )}
                  style={{ width: `${selectedZone.soilMoisturePercent}%` }}
                />
              </div>
            </div>

            <div className="bg-sunken p-3 rounded-xl border border-line">
              <span className="text-[10px] text-earth-400 flex items-center gap-1">
                <Thermometer className="h-3 w-3 text-sun-400" /> Température Canopée
              </span>
              <p className="text-xl font-black text-ink mt-1">
                {selectedZone.temperatureC}°C
              </p>
              <span className="text-[10px] text-earth-500">
                {selectedZone.humidityPercent}% Humidité Air
              </span>
            </div>
          </div>

          {/* Agronomic Details */}
          <div className="bg-sunken p-3.5 rounded-xl border border-line space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-earth-400">Culture & Variété :</span>
              <span className="font-semibold text-ink">{selectedZone.cropType}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-earth-400">Superficie :</span>
              <span className="font-semibold text-ink">{selectedZone.areaHa} Hectares</span>
            </div>
            <div className="flex justify-between">
              <span className="text-earth-400">Système d'irrigation :</span>
              <span className="font-semibold text-water-300">{selectedZone.irrigationMethod}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-earth-400">Type de sol :</span>
              <span className="font-semibold text-earth-200">{selectedZone.soilType}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-earth-400">Récolte prévisionnelle :</span>
              <span className="font-semibold text-brand-400">{selectedZone.predictedHarvestDate}</span>
            </div>
          </div>

          {/* AI Recommendation Alert */}
          {selectedZone.status === 'critical' && (
            <div className="bg-alert-950/40 border border-alert-500/40 p-3 rounded-xl flex gap-3 text-xs">
              <ShieldAlert className="h-5 w-5 text-alert-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-bold text-alert-200">Recommandation IA Immédiate</p>
                <p className="text-alert-300/80 text-[11px] mt-0.5">
                  L'humidité est tombée à {selectedZone.soilMoisturePercent}% avec une température de 36.4°C. Déclencher un cycle d'irrigation goutte-à-goutte de 45 minutes alimenté par l'énergie solaire.
                </p>
              </div>
            </div>
          )}

          {/* Interactive Direct Irrigation Action */}
          <div className="bg-sunken p-3.5 rounded-xl border border-line">
            <span className="text-[10px] font-bold uppercase tracking-wider text-earth-400 block mb-2">
              Actionneur de Vanne Électrique
            </span>
            {selectedZone.status === 'irrigating' ? (
              <button
                onClick={() => stopIrrigation(selectedZone.id)}
                className="w-full py-2.5 rounded-xl bg-earth-800 hover:bg-earth-700 text-alert-400 border border-alert-500/30 font-bold text-xs flex items-center justify-center gap-2 transition-all"
              >
                <Square className="h-4 w-4 fill-current" />
                Interrompre l'Irrigation
              </button>
            ) : (
              <button
                disabled={emergencyStopActive}
                onClick={() => startIrrigation(selectedZone.id)}
                className={cn(
                  "w-full py-2.5 rounded-xl font-bold text-xs flex items-center justify-center gap-2 transition-all shadow-lg",
                  emergencyStopActive
                    ? "bg-earth-800 text-earth-500 cursor-not-allowed border border-earth-700"
                    : "bg-accent hover:bg-accent-hover text-on-accent shadow-shade/20"
                )}
              >
                <Play className="h-4 w-4 fill-current" />
                {emergencyStopActive ? "Verrouillé (Arrêt d'Urgence)" : "Lancer Cycle d'Irrigation (45 min)"}
              </button>
            )}
            <p className="text-[10px] text-earth-500 text-center mt-2">
              Action simulée en mode démonstration sécurisé
            </p>
          </div>

          <Link
            href={`/farm/zones/${selectedZone.id}`}
            className="w-full py-2 rounded-xl bg-highlight hover:bg-highlight text-brand-300 text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors border border-brand-500/20"
          >
            <span>Détails Complets de la Parcelle</span>
            <ChevronRight className="h-3.5 w-3.5" />
          </Link>

          <ZoneDecisionPanel farmId={farm.id} zone={selectedZone} />
        </div>
      </div>
    </div>
  );
}

function ZoneDecisionPanel({ farmId, zone }: { farmId: string; zone: FarmZone }) {
  const [history, setHistory] = useState<ZoneHistory | null>(null);
  const [decision, setDecision] = useState<Awaited<ReturnType<typeof requestAgenticDecision>> | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let active = true;
    setDecision(null);
    void fetchZoneHistory(farmId, zone.id).then((data) => { if (active) setHistory(data); }).catch(() => { if (active) setHistory(null); });
    void requestAgenticDecision(zone).then((data) => { if (active) setDecision(data); }).catch(() => { if (active) setDecision(null); });
    return () => { active = false; };
  }, [farmId, zone]);

  const refreshDecision = () => {
    setLoading(true);
    void requestAgenticDecision(zone).then(setDecision).finally(() => setLoading(false));
  };
  const lastImpact = history?.impacts[0];
  const firstFinding = decision?.findings.find((finding) => finding.status === 'critical') ?? decision?.findings[0];

  return (
    <section className="rounded-xl border border-brand-500/25 bg-brand-500/5 p-3.5 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-wider text-brand-400">Dossier agentique de la parcelle</p>
          <h4 className="mt-1 text-sm font-bold text-ink">Solutions et réaction du terrain</h4>
        </div>
        <Sparkles className="h-4 w-4 text-brand-400" />
      </div>

      {decision ? (
        <div className="rounded-lg bg-surface/80 p-2.5">
          <p className="text-[10px] font-semibold text-earth-500">Solution maintenant</p>
          <p className="mt-1 text-[11px] font-bold text-ink">{firstFinding?.recommendation ?? decision.recommendation}</p>
          <p className="mt-1 text-[10px] leading-4 text-earth-400">Pourquoi : {firstFinding?.observation ?? 'Les agents ont comparé les mesures de la parcelle et son contexte énergétique.'}</p>
          {firstFinding?.checkpoints?.length ? <p className="mt-1 text-[10px] text-sun-400">Checkpoint : {firstFinding.checkpoints[0]}</p> : null}
        </div>
      ) : (
        <p className="rounded-lg bg-surface/80 p-2.5 text-[10px] text-earth-400">Analyse agentique en cours…</p>
      )}

      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-lg bg-surface/80 p-2.5">
          <p className="text-[10px] text-earth-500">Réaction précédente</p>
          <p className="mt-1 text-xs font-bold text-brand-400">{lastImpact ? `${lastImpact.observed} ${lastImpact.unit}` : 'Pas encore mesurée'}</p>
          {lastImpact ? <p className="mt-0.5 text-[9px] text-earth-500">référence {lastImpact.baseline} {lastImpact.unit}</p> : null}
        </div>
        <div className="rounded-lg bg-surface/80 p-2.5">
          <p className="text-[10px] text-earth-500">Historique</p>
          <p className="mt-1 text-xs font-bold text-ink">{history?.decisions.length ?? 0} décision(s)</p>
          <p className="mt-0.5 text-[9px] text-earth-500">source PostgreSQL</p>
        </div>
      </div>

      <button onClick={refreshDecision} disabled={loading} className="w-full rounded-lg bg-accent px-3 py-2 text-[10px] font-bold text-on-accent hover:bg-accent-hover disabled:opacity-50">
        {loading ? 'Nouvelle analyse…' : 'Recalculer avec l’environnement actuel'}
      </button>
    </section>
  );
}
