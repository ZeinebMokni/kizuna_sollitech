'use client';

import React, { useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  TrendingUp,
  Droplets,
  Sun,
  ShieldAlert,
  ArrowUpRight,
  Info
} from 'lucide-react';
import { cn, formatNumber, formatCurrencyTND } from '@/lib/utils';

interface GovernorateData {
  id: string;
  name: string;
  nameAr: string;
  zone: 'Nord' | 'Centre' | 'Sud';
  mainCrops: string[];
  waterStress: 'Élevé' | 'Critique' | 'Modéré';
  solarPotentialKwhM2: number;
  marketRole: string;
  projectedSurplusOrDeficit: string;
  cx: number;
  cy: number;
}

const TUNISIA_GOVERNORATES: GovernorateData[] = [
  {
    id: 'bizerte',
    name: 'Bizerte',
    nameAr: 'بنزرت',
    zone: 'Nord',
    mainCrops: ['Pomme de terre', 'Blé dur', 'Tomates plein champ'],
    waterStress: 'Modéré',
    solarPotentialKwhM2: 1750,
    marketRole: 'Bassin céréalier et maraîcher côtier',
    projectedSurplusOrDeficit: 'Déficit semences certifiées (-22%)',
    cx: 260,
    cy: 80,
  },
  {
    id: 'nabeul',
    name: 'Nabeul (Cap Bon)',
    nameAr: 'نابل',
    zone: 'Nord',
    mainCrops: ['Agrumes', 'Tomates de transformation', 'Piments'],
    waterStress: 'Critique',
    solarPotentialKwhM2: 1820,
    marketRole: 'Premier pôle agrumicole et pimentier historique',
    projectedSurplusOrDeficit: 'Chute de production (-30% stress hydrique barrages)',
    cx: 310,
    cy: 120,
  },
  {
    id: 'kairouan',
    name: 'Kairouan',
    nameAr: 'القيروان',
    zone: 'Centre',
    mainCrops: ['Piments Baklouti', 'Oliviers', 'Abricots', 'Céréales'],
    waterStress: 'Critique',
    solarPotentialKwhM2: 1980,
    marketRole: 'Cœur névralgique du maraîchage central',
    projectedSurplusOrDeficit: 'Tension sur les prix du piment (+38%)',
    cx: 250,
    cy: 220,
  },
  {
    id: 'sidi_bouzid',
    name: 'Sidi Bouzid',
    nameAr: 'سيدي بوزيد',
    zone: 'Centre',
    mainCrops: ['Maraîchage primeur', 'Oliviers Chemlali', 'Fourrages', 'Lait'],
    waterStress: 'Critique',
    solarPotentialKwhM2: 2050,
    marketRole: 'Grenier maraîcher et premier producteur d\'olives du Centre',
    projectedSurplusOrDeficit: 'Surproduction pastèques à éviter; opportunité piments',
    cx: 220,
    cy: 290,
  },
  {
    id: 'sfax',
    name: 'Sfax',
    nameAr: 'صفاقس',
    zone: 'Centre',
    mainCrops: ['Oliviers à huile', 'Amandes', 'Pêche'],
    waterStress: 'Élevé',
    solarPotentialKwhM2: 2020,
    marketRole: 'Capitale oléicole et hub d\'exportation mondial',
    projectedSurplusOrDeficit: 'Demande record huile d\'olive extra vierge (+12%)',
    cx: 300,
    cy: 310,
  },
  {
    id: 'gabes',
    name: 'Gabès',
    nameAr: 'قابس',
    zone: 'Sud',
    mainCrops: ['Grenades côtières', 'Henné', 'Cultures géothermiques'],
    waterStress: 'Critique',
    solarPotentialKwhM2: 2150,
    marketRole: 'Oasis maritimes et maraîchage géothermique',
    projectedSurplusOrDeficit: 'Stabilité grenades Gabsi premium export',
    cx: 270,
    cy: 400,
  },
  {
    id: 'tozeur',
    name: 'Tozeur',
    nameAr: 'توزر',
    zone: 'Sud',
    mainCrops: ['Dattes Deglet Nour', 'Maraîchage d\'oasis'],
    waterStress: 'Critique',
    solarPotentialKwhM2: 2280,
    marketRole: 'Fleuron des dattes premium de renommée mondiale',
    projectedSurplusOrDeficit: 'Pression nappe du Continental Intercalaire',
    cx: 170,
    cy: 420,
  },
  {
    id: 'medenine',
    name: 'Médenine',
    nameAr: 'مدنين',
    zone: 'Sud',
    mainCrops: ['Oliviers Zarrazi', 'Élevage camelin & ovin'],
    waterStress: 'Élevé',
    solarPotentialKwhM2: 2240,
    marketRole: 'Agriculture pastorale et oléiculture aride',
    projectedSurplusOrDeficit: 'Valorisation des variétés arides résistantes',
    cx: 290,
    cy: 470,
  },
];

export function TunisiaIntelligenceMap() {
  const [selectedGovId, setSelectedGovId] = useState<string>('sidi_bouzid');
  const [activeFilter, setActiveFilter] = useState<'all' | 'deficit' | 'surplus'>('all');

  const selectedGov = TUNISIA_GOVERNORATES.find((g) => g.id === selectedGovId) || TUNISIA_GOVERNORATES[3];

  return (
    <div className="bg-surface border border-line rounded-2xl p-4 md:p-6 shadow-xl qa-card">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-line gap-3">
        <div>
          <span className="text-[10px] font-bold uppercase tracking-wider text-brand-400">
            Observatoire National Agricole QATRA
          </span>
          <h2 className="text-lg font-bold text-ink">Cartographie des Régions & Filières</h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-earth-400">Filtrer :</span>
          <button
            onClick={() => setActiveFilter('all')}
            className={cn(
              "px-2.5 py-1 text-xs rounded-lg font-medium transition-colors",
              activeFilter === 'all' ? "bg-accent-deep text-on-accent" : "bg-earth-800 text-earth-400 hover:text-ink"
            )}
          >
            Tous
          </button>
          <button
            onClick={() => setActiveFilter('deficit')}
            className={cn(
              "px-2.5 py-1 text-xs rounded-lg font-medium transition-colors",
              activeFilter === 'deficit' ? "bg-alert-800 text-ink" : "bg-earth-800 text-earth-400 hover:text-ink"
            )}
          >
            Pénuries Détectées
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mt-6 items-center">
        {/* SVG Interactive Map of Tunisia */}
        <div className="lg:col-span-6 relative flex items-center justify-center bg-sunken p-4 rounded-xl border border-line min-h-[460px]">
          <svg viewBox="0 0 450 560" className="w-full max-h-[440px] drop-shadow-xl select-none">
            {/* Outline of Tunisia */}
            <path
              d="M 230 40 Q 280 40 290 70 L 320 110 L 340 140 L 310 180 L 330 250 L 310 330 L 290 400 L 330 460 L 320 530 L 250 510 L 200 450 L 160 410 L 170 320 L 200 240 L 210 160 Z"
              className="fill-brand-900/70 stroke-brand-500"
              strokeWidth="2"
              strokeDasharray="4 2"
            />

            {/* Governorate Nodes */}
            {TUNISIA_GOVERNORATES.map((gov) => {
              const isSelected = gov.id === selectedGovId;
              const isCritical = gov.waterStress === 'Critique';
              return (
                <g
                  key={gov.id}
                  onClick={() => setSelectedGovId(gov.id)}
                  className="cursor-pointer group"
                >
                  {/* Halo pulse for selected */}
                  {isSelected && (
                    <circle
                      cx={gov.cx}
                      cy={gov.cy}
                      r="22"
                      className="fill-brand-400/25 animate-ping"
                    />
                  )}
                  <circle
                    cx={gov.cx}
                    cy={gov.cy}
                    r={isSelected ? "12" : "8"}
                    strokeWidth={isSelected ? "2.5" : "1.5"}
                    className={cn(
                      "stroke-surface transition-all duration-300 group-hover:scale-125",
                      isCritical ? "fill-alert-500" : isSelected ? "fill-sun-500" : "fill-brand-500"
                    )}
                  />
                  <text
                    x={gov.cx + 14}
                    y={gov.cy + 4}
                    fontSize={isSelected ? "12" : "10"}
                    fontWeight={isSelected ? "bold" : "normal"}
                    className={cn(
                      "select-none pointer-events-none",
                      isSelected ? "fill-ink" : "fill-earth-300"
                    )}
                  >
                    {gov.name}
                  </text>
                </g>
              );
            })}
          </svg>

          <div className="absolute bottom-3 left-3 glass-panel px-2.5 py-1 rounded-md text-[10px] text-earth-400 border">
            Cliquez sur un gouvernorat pour inspecter l'écosystème
          </div>
        </div>

        {/* Selected Governorate Intelligence Card */}
        <div className="lg:col-span-6 space-y-4">
          <div className="bg-raised border border-line p-5 rounded-xl">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-xs text-brand-400 font-mono">Gouvernorat de {selectedGov.zone}</span>
                <h3 className="text-2xl font-black text-ink flex items-center gap-2 mt-0.5">
                  {selectedGov.name} <span className="text-base text-earth-400 font-normal">({selectedGov.nameAr})</span>
                </h3>
              </div>
              <span
                className={cn(
                  "px-3 py-1 rounded-full text-xs font-bold border",
                  selectedGov.waterStress === 'Critique'
                    ? "bg-alert-500/20 text-alert-400 border-alert-500/30"
                    : "bg-sun-500/20 text-sun-400 border-sun-500/30"
                )}
              >
                Stress Eau : {selectedGov.waterStress}
              </span>
            </div>

            <p className="text-xs text-earth-300 mt-3 leading-relaxed">
              {selectedGov.marketRole}.
            </p>

            <div className="grid grid-cols-2 gap-3 mt-4">
              <div className="bg-sunken p-3 rounded-lg border border-line">
                <span className="text-[10px] text-earth-400 flex items-center gap-1">
                  <Sun className="h-3 w-3 text-sun-400" /> Potentiel Solaire
                </span>
                <p className="text-base font-bold text-ink mt-1">
                  {selectedGov.solarPotentialKwhM2} <span className="text-xs font-normal text-earth-400">kWh/m²/an</span>
                </p>
              </div>

              <div className="bg-sunken p-3 rounded-lg border border-line">
                <span className="text-[10px] text-earth-400 flex items-center gap-1">
                  <TrendingUp className="h-3 w-3 text-brand-400" /> Tendance Filière
                </span>
                <p className="text-xs font-bold text-brand-300 mt-1 truncate">
                  {selectedGov.projectedSurplusOrDeficit}
                </p>
              </div>
            </div>

            <div className="mt-4">
              <span className="text-[11px] font-semibold text-earth-400 block mb-1.5">
                Cultures Prédominantes dans la Région :
              </span>
              <div className="flex flex-wrap gap-1.5">
                {selectedGov.mainCrops.map((crop, idx) => (
                  <span
                    key={idx}
                    className="px-2.5 py-0.5 rounded-md bg-highlight text-brand-300 text-xs border border-brand-500/20"
                  >
                    {crop}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Kizuna Bilateral Technology Impact Box */}
          <div className="bg-gradient-to-br from-brand-950 to-sunken border border-brand-500/30 p-4 rounded-xl flex items-start gap-3">
            <div className="h-9 w-9 rounded-lg bg-brand-500/20 border border-brand-500/40 flex items-center justify-center text-brand-300 flex-shrink-0">
              <CheckCircle2 className="h-5 w-5" />
            </div>
            <div className="text-xs">
              <span className="font-bold text-ink block">
                Synergie Kizuna 2026 (Japon × Tunisie)
              </span>
              <p className="text-earth-300 mt-1 leading-relaxed">
                Application des principes <span className="text-brand-300 font-semibold">Mottainai</span> (zéro déchet hydrique) et micro-irrigation optimisée par énergie solaire pour préserver les nappes phréatiques fragiles de {selectedGov.name}.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
