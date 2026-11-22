'use client';

import React, { useState } from 'react';
import {
  Brain,
  Sparkles,
  Droplets,
  Sun,
  Coins,
  ShieldAlert,
  ArrowRight,
  Check,
  Calendar,
  Layers,
  ChevronDown,
  Info,
  BookOpen,
  ExternalLink,
  BarChart3
} from 'lucide-react';
import { DEMO_CROP_RECOMMENDATIONS } from '@/lib/mockData';
import { CropRecommendation } from '@/types';
import { cn, formatNumber, formatCurrencyTND } from '@/lib/utils';
import { useFarmStore } from '@/stores/useFarmStore';

export function AICropPlanner() {
  const { farm } = useFarmStore();
  const [selectedCropId, setSelectedCropId] = useState<string>('rec-01');
  const [selectedSeason, setSelectedSeason] = useState('Hiver 2026 / Printemps 2027');
  const [availableWaterM3, setAvailableWaterM3] = useState(5000);
  const [hasSolar, setHasSolar] = useState(true);
  const [planCreated, setPlanCreated] = useState(false);
  const [showSources, setShowSources] = useState(true);

  const selectedCrop = DEMO_CROP_RECOMMENDATIONS.find((c) => c.id === selectedCropId) || DEMO_CROP_RECOMMENDATIONS[0];
  const dominantSoil = Array.from(new Set(farm.zones.map((zone) => zone.soilType))).filter(Boolean)[0] ?? 'Sablo-limoneux';
  const soilFit = getSoilFit(selectedCrop.cropName, dominantSoil);

  return (
    <div className="space-y-6">
      {/* Parameter input card */}
      <div className="bg-surface border border-line p-5 rounded-2xl shadow-xl qa-card">
        <div className="flex items-center gap-2.5 pb-4 border-b border-line">
          <div className="h-9 w-9 rounded-xl bg-brand-500/20 border border-brand-500/40 flex items-center justify-center text-brand-400">
            <Brain className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-ink">
              Générateur d'Orientation Culturale Prédictive (Moteur IA QATRA)
            </h2>
            <p className="text-xs text-earth-400">
              Simulation croisée : Marché national tunisien × Données pédoclimatiques × Bilan Eau/Solaire
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 mt-4 text-xs">
          <div>
            <label className="text-earth-400 block mb-1 font-medium">Saison Cible</label>
            <select
              value={selectedSeason}
              onChange={(e) => setSelectedSeason(e.target.value)}
              className="w-full bg-sunken border border-line rounded-xl px-3 py-2 text-ink font-medium focus:outline-none focus:border-brand-500"
            >
              <option>Hiver 2026 / Printemps 2027</option>
              <option>Été 2027</option>
              <option>Automne 2027</option>
            </select>
          </div>

          <div>
            <label className="text-earth-400 block mb-1 font-medium">Réserve d'Eau Estimée (m³/Ha)</label>
            <div className="flex items-center bg-sunken border border-line rounded-xl px-3 py-2">
              <input
                type="number"
                value={availableWaterM3}
                onChange={(e) => setAvailableWaterM3(Number(e.target.value))}
                className="w-full bg-transparent text-ink font-mono font-bold focus:outline-none"
              />
              <span className="text-[11px] text-earth-500 ml-1">m³</span>
            </div>
          </div>

          <div>
            <label className="text-earth-400 block mb-1 font-medium">Alimentation Énergétique</label>
            <div className="flex items-center gap-2 mt-1">
              <button
                type="button"
                onClick={() => setHasSolar(!hasSolar)}
                className={cn(
                  "flex-1 py-2 px-3 rounded-xl border text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors",
                  hasSolar
                    ? "bg-brand-600/30 border-brand-500 text-brand-300"
                    : "bg-earth-800 border-earth-700 text-earth-400"
                )}
              >
                <Sun className="h-3.5 w-3.5 text-sun-400" />
                {hasSolar ? 'Solaire Photovoltaïque' : 'Réseau STEG Seul'}
              </button>
            </div>
          </div>

          <div>
            <label className="text-earth-400 block mb-1 font-medium">Objectif Stratégique</label>
            <select className="w-full bg-sunken border border-line rounded-xl px-3 py-2 text-ink font-medium focus:outline-none focus:border-brand-500">
              <option>Maximiser la Marge Nette par m³ d'eau</option>
              <option>Sécurité & Résilience Sécheresse</option>
              <option>Exportation Haut de Gamme</option>
            </select>
          </div>
        </div>
      </div>

      {/* Recommended Crops Cards */}
      <div>
        <h3 className="text-sm font-bold uppercase tracking-wider text-earth-400 mb-3">
          Classement des Cultures Évaluées par l'IA
        </h3>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-brand-500/20 bg-brand-500/5 px-3 py-2 text-[11px]">
          <span className="flex items-center gap-2 text-earth-300"><Layers className="h-3.5 w-3.5 text-brand-400" /> Sol détecté : <strong className="text-ink">{dominantSoil}</strong></span>
          <span className="font-bold text-brand-400">Adéquation actuelle : {soilFit}/100</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {DEMO_CROP_RECOMMENDATIONS.map((crop) => {
            const isSelected = crop.id === selectedCropId;
            const isDiscouraged = crop.suitabilityScore < 50;

            return (
              <div
                key={crop.id}
                onClick={() => setSelectedCropId(crop.id)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    setSelectedCropId(crop.id);
                  }
                }}
                role="button"
                tabIndex={0}
                aria-pressed={isSelected}
                className={cn(
                  "p-4 rounded-2xl border transition-all cursor-pointer flex flex-col justify-between relative",
                  isSelected
                    ? "bg-raised border-brand-500 shadow-xl shadow-shade/20 scale-[1.02]"
                    : "bg-surface border-line hover:border-earth-600",
                  isDiscouraged && "opacity-80 border-alert-500/40 bg-alert-950/20"
                )}
              >
                {/* Score badge */}
                <div className="flex items-start justify-between">
                  <span
                    className={cn(
                      "px-2.5 py-1 text-xs font-black rounded-lg font-mono border",
                      isDiscouraged
                        ? "bg-alert-500/20 text-alert-400 border-alert-500/30"
                        : "bg-brand-500/20 text-brand-400 border-brand-500/30"
                    )}
                  >
                    Score {crop.suitabilityScore}/100
                  </span>
                  <span className="text-[10px] text-earth-400">{crop.growthDurationDays} jours</span>
                </div>

                <div className="my-3">
                  <h4 className="text-base font-bold text-ink leading-snug">{crop.cropName}</h4>
                  <p className="text-xs text-earth-400 mt-0.5">{crop.category}</p>
                </div>

                <div className="space-y-1.5 text-xs border-t border-line pt-3 text-earth-300">
                  <div className="flex justify-between">
                    <span className="text-earth-500 flex items-center gap-1">
                      <Droplets className="h-3 w-3 text-water-400" /> Eau requise
                    </span>
                    <span className="font-mono font-semibold">{crop.waterRequirementM3Ha} m³/Ha</span>
                  </div>

                  <div className="flex justify-between">
                    <span className="text-earth-500 flex items-center gap-1">
                      <Coins className="h-3 w-3 text-sun-400" /> Marge nette
                    </span>
                    <span className={cn("font-mono font-bold", isDiscouraged ? "text-alert-400" : "text-brand-400")}>
                      {formatCurrencyTND(crop.netMarginTndHa)}/Ha
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-earth-500 flex items-center gap-1"><Layers className="h-3 w-3 text-brand-400" /> Compatibilité sol</span>
                    <span className="font-mono font-bold text-brand-400">{getSoilFit(crop.cropName, dominantSoil)}/100</span>
                  </div>
                </div>
                <span className={cn('mt-3 inline-flex items-center gap-1 text-[10px] font-semibold', isSelected ? 'text-brand-400' : 'text-earth-500')}>
                  <Info className="h-3 w-3" /> Cliquer pour voir l’analyse et les sources
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Selected Crop Deep-Dive Analysis */}
      <div className="bg-surface border border-line p-6 rounded-2xl shadow-xl qa-card">
        <div className="flex flex-col md:flex-row md:items-center justify-between pb-4 border-b border-line gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-brand-500/20 text-brand-300 border border-brand-500/30">
                Analyse Détaillée de Rentabilité
              </span>
              <span className="text-xs text-earth-400 font-mono">Cycle : {selectedCrop.harvestPeriod}</span>
            </div>
            <h3 className="text-xl font-bold text-ink mt-1">{selectedCrop.cropName}</h3>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                setPlanCreated(true);
                setTimeout(() => setPlanCreated(false), 4000);
              }}
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-accent to-accent-deep hover:from-accent-hover hover:to-accent-deep text-on-accent font-bold text-xs flex items-center gap-2 transition-all border border-brand-500/30 qa-shine"
            >
              {planCreated ? <Check className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
              {planCreated ? 'Plan Agricole Généré & Assigné !' : 'Générer le Plan de Culture'}
            </button>
          </div>
        </div>

        {/* Financial and Environmental metrics bar */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
          <div className="bg-sunken p-4 rounded-xl border border-line">
            <span className="text-xs text-earth-400">Rendement Prévisionnel</span>
            <p className="text-xl font-black text-ink mt-1">
              {selectedCrop.estimatedYieldTonsHa} <span className="text-xs font-normal text-earth-400">Tonnes / Ha</span>
            </p>
          </div>

          <div className="bg-sunken p-4 rounded-xl border border-line">
            <span className="text-xs text-earth-400">Coûts de Production (Semences, Eau, MO)</span>
            <p className="text-xl font-black text-earth-300 mt-1">
              {formatCurrencyTND(selectedCrop.estimatedCostTndHa)}
            </p>
          </div>

          <div className="bg-sunken p-4 rounded-xl border border-line">
            <span className="text-xs text-earth-400">Chiffre d'Affaires Brut Estimé</span>
            <p className="text-xl font-black text-sun-300 mt-1">
              {formatCurrencyTND(selectedCrop.estimatedRevenueTndHa)}
            </p>
          </div>

          <div className="bg-sunken p-4 rounded-xl border border-brand-500/30 bg-brand-950/20">
            <span className="text-xs text-brand-400 font-semibold">Bénéfice Net Projeté</span>
            <p className="text-xl font-black text-brand-400 mt-1">
              {formatCurrencyTND(selectedCrop.netMarginTndHa)}
            </p>
          </div>
        </div>

        {/* Arguments and Risks */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
          <div className="bg-canvas p-4 rounded-xl border border-line">
            <h4 className="text-xs font-bold uppercase tracking-wider text-brand-400 flex items-center gap-1.5 mb-3">
              <Check className="h-4 w-4" /> Pourquoi cette culture est recommandée
            </h4>
            <ul className="space-y-2">
              {selectedCrop.whyRecommended.length > 0 ? (
                selectedCrop.whyRecommended.map((arg, idx) => (
                  <li key={idx} className="text-xs text-earth-300 flex items-start gap-2">
                    <span className="h-1.5 w-1.5 rounded-full bg-brand-400 mt-1.5 flex-shrink-0" />
                    <span>{arg}</span>
                  </li>
                ))
              ) : (
                <li className="text-xs text-alert-300 italic">
                  Aucun point positif détecté dans le contexte hydrique et commercial actuel.
                </li>
              )}
            </ul>
          </div>

          <div className="bg-canvas p-4 rounded-xl border border-line">
            <h4 className="text-xs font-bold uppercase tracking-wider text-sun-400 flex items-center gap-1.5 mb-3">
              <ShieldAlert className="h-4 w-4" /> Facteurs de Risque & Vigilance
            </h4>
            <ul className="space-y-2">
              {selectedCrop.keyRisks.map((risk, idx) => (
                <li key={idx} className="text-xs text-earth-300 flex items-start gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-sun-400 mt-1.5 flex-shrink-0" />
                  <span>{risk}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="mt-6 rounded-xl border border-brand-500/25 bg-brand-500/5 overflow-hidden">
          <button
            type="button"
            onClick={() => setShowSources((current) => !current)}
            className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left hover:bg-brand-500/5"
            aria-expanded={showSources}
          >
            <span className="flex items-center gap-2">
              <BookOpen className="h-4 w-4 text-brand-400" />
              <span>
                <span className="block text-xs font-bold uppercase tracking-wider text-brand-400">Analyse IA & sources</span>
                <span className="block mt-0.5 text-[11px] text-earth-400">Pourquoi cette note a été calculée pour {selectedCrop.cropName}</span>
              </span>
            </span>
            <ChevronDown className={cn('h-4 w-4 text-brand-400 transition-transform', showSources && 'rotate-180')} />
          </button>

          {showSources && (
            <div className="grid grid-cols-1 lg:grid-cols-[1.2fr_.8fr] gap-4 border-t border-brand-500/15 p-4">
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-[11px] font-semibold text-ink">
                  <BarChart3 className="h-3.5 w-3.5 text-water-400" /> Lecture du modèle
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <AnalysisSignal label="Adéquation eau" value={`${Math.max(0, Math.round(100 - (selectedCrop.waterRequirementM3Ha / Math.max(availableWaterM3, 1)) * 100))}/100`} />
                  <AnalysisSignal label="Compatibilité solaire" value={`${selectedCrop.solarFitScore}/100`} />
                  <AnalysisSignal label="Résilience" value={selectedCrop.droughtResistance} />
                </div>
                <div className="mt-3 rounded-lg border border-brand-500/20 bg-surface px-3 py-2 text-[11px] text-earth-300">
                  <strong className="text-brand-400">Sol pris en compte :</strong> {dominantSoil}. {soilExplanation(selectedCrop.cropName, dominantSoil)}
                </div>
                <p className="text-[11px] leading-5 text-earth-300">
                  Le score combine le besoin en eau, la marge nette projetée, la compatibilité avec l’énergie disponible,
                  la résistance à la sécheresse et les risques agronomiques listés ci-dessus. Il est recalculé avec vos paramètres.
                </p>
              </div>
              <div className="rounded-lg border border-line bg-surface p-3">
                <div className="flex items-center gap-2 text-[11px] font-semibold text-ink">
                  <BookOpen className="h-3.5 w-3.5 text-brand-400" /> Sources utilisées
                </div>
                <div className="mt-2 space-y-2">
                  {[
                    ['Marché tunisien', 'Prévision de demande, prix et marge estimée'],
                    ['Données pédoclimatiques', 'Sol, saison, évapotranspiration et stress hydrique'],
                    ['Bilan eau & solaire', `${formatNumber(availableWaterM3)} m³ disponibles · ${hasSolar ? 'solaire actif' : 'réseau STEG'}`],
                  ].map(([name, detail]) => (
                    <div key={name} className="flex items-start justify-between gap-3 rounded-lg bg-raised px-2.5 py-2">
                      <div><p className="text-[10px] font-semibold text-ink">{name}</p><p className="mt-0.5 text-[10px] leading-4 text-earth-500">{detail}</p></div>
                      <ExternalLink className="mt-0.5 h-3 w-3 shrink-0 text-water-400" />
                    </div>
                  ))}
                </div>
                <p className="mt-2 text-[9px] leading-4 text-earth-500">Sources de démonstration · à remplacer par les flux connectés QATRA avant décision opérationnelle.</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function AnalysisSignal({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg border border-line bg-surface px-2.5 py-2"><p className="text-[9px] text-earth-500">{label}</p><p className="mt-1 text-xs font-black text-ink">{value}</p></div>;
}

function getSoilFit(cropName: string, soilType: string) {
  const soil = soilType.toLowerCase();
  const crop = cropName.toLowerCase();
  if (soil.includes('sablo') && crop.includes('piment')) return 96;
  if (soil.includes('sablo') && crop.includes('grenad')) return 91;
  if (soil.includes('sablo') && crop.includes('fenouil')) return 84;
  if (soil.includes('argil') && crop.includes('past')) return 74;
  if (soil.includes('limon')) return 84;
  return 70;
}

function soilExplanation(cropName: string, soilType: string) {
  const crop = cropName.toLowerCase();
  const soil = soilType.toLowerCase();
  if (soil.includes('sablo') && crop.includes('piment')) return 'Le drainage naturel favorise l’enracinement du piment ; une irrigation fractionnée évite le stress hydrique.';
  if (soil.includes('sablo') && crop.includes('grenad')) return 'La texture filtrante convient au grenadier ; maintenez une réserve d’eau régulière pendant la nouaison.';
  if (soil.includes('argil')) return 'La rétention d’eau est favorable, mais surveillez le drainage et le compactage.';
  return 'La structure du sol est compatible, avec une gestion de l’humidité adaptée au cycle de la culture.';
}
