'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ThemeToggle } from '@/components/layout/ThemeToggle';
import {
  Sprout,
  MapPin,
  Droplets,
  Sun,
  Layers,
  ArrowRight,
  CheckCircle2,
  Compass
} from 'lucide-react';
import { cn } from '@/lib/utils';

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [farmName, setFarmName] = useState('Domaine El-Waha');
  const [governorate, setGovernorate] = useState('Sidi Bouzid');
  const [delegation, setDelegation] = useState('Regueb');
  const [totalArea, setTotalArea] = useState(12.5);
  const [waterSource, setWaterSource] = useState('Puits profond (Sondage)');
  const [energySource, setEnergySource] = useState('Solaire Hybride (PV + Réseau)');
  const [crops, setCrops] = useState(['Olivier', 'Piment', 'Tomate']);

  const nextStep = () => {
    if (step < 3) setStep(step + 1);
    else router.push('/dashboard');
  };

  return (
    <div className="min-h-screen flex flex-col justify-center items-center px-4 py-12 relative">
      <ThemeToggle className="absolute top-4 right-4 z-20" />
      <div className="max-w-2xl w-full bg-surface border border-line rounded-2xl p-8 shadow-2xl relative z-10">
        {/* Progress indicator */}
        <div className="flex items-center justify-between pb-6 border-b border-line mb-6">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-brand-400">
              Assistant de Configuration
            </span>
            <h2 className="text-xl font-bold text-ink">Création de votre Exploitation</h2>
          </div>
          <div className="flex items-center gap-2">
            {[1, 2, 3].map((s) => (
              <div
                key={s}
                className={cn(
                  "h-8 w-8 rounded-full flex items-center justify-center text-xs font-bold font-mono transition-all",
                  step === s
                    ? "bg-accent text-on-accent ring-2 ring-brand-500/40"
                    : step > s
                    ? "bg-brand-900 text-brand-300"
                    : "bg-earth-800 text-earth-500"
                )}
              >
                {step > s ? '✓' : s}
              </div>
            ))}
          </div>
        </div>

        {/* Step 1: Farm identity & location */}
        {step === 1 && (
          <div className="space-y-4">
            <div>
              <label className="text-xs text-earth-300 font-semibold block mb-1">Nom de l'Exploitation</label>
              <input
                type="text"
                value={farmName}
                onChange={(e) => setFarmName(e.target.value)}
                className="w-full bg-sunken border border-line rounded-xl px-3.5 py-2.5 text-xs text-ink focus:outline-none focus:border-brand-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-earth-300 font-semibold block mb-1">Gouvernorat</label>
                <select
                  value={governorate}
                  onChange={(e) => setGovernorate(e.target.value)}
                  className="w-full bg-sunken border border-line rounded-xl px-3.5 py-2.5 text-xs text-ink focus:outline-none focus:border-brand-500"
                >
                  <option>Sidi Bouzid</option>
                  <option>Kairouan</option>
                  <option>Sfax</option>
                  <option>Nabeul</option>
                  <option>Bizerte</option>
                  <option>Gabès</option>
                  <option>Tozeur</option>
                </select>
              </div>

              <div>
                <label className="text-xs text-earth-300 font-semibold block mb-1">Délégation / Localité</label>
                <input
                  type="text"
                  value={delegation}
                  onChange={(e) => setDelegation(e.target.value)}
                  className="w-full bg-sunken border border-line rounded-xl px-3.5 py-2.5 text-xs text-ink focus:outline-none focus:border-brand-500"
                />
              </div>
            </div>

            <div>
              <label className="text-xs text-earth-300 font-semibold block mb-1">Superficie Totale (Hectares)</label>
              <input
                type="number"
                value={totalArea}
                onChange={(e) => setTotalArea(Number(e.target.value))}
                className="w-full bg-sunken border border-line rounded-xl px-3.5 py-2.5 text-xs text-ink focus:outline-none focus:border-brand-500"
              />
            </div>
          </div>
        )}

        {/* Step 2: Water & Energy resources */}
        {step === 2 && (
          <div className="space-y-4">
            <div>
              <label className="text-xs text-earth-300 font-semibold block mb-1">Ressource en Eau Principale</label>
              <select
                value={waterSource}
                onChange={(e) => setWaterSource(e.target.value)}
                className="w-full bg-sunken border border-line rounded-xl px-3.5 py-2.5 text-xs text-ink focus:outline-none focus:border-brand-500"
              >
                <option>Puits profond (Sondage nappe phréatique)</option>
                <option>Retenue collinaire / Barrage</option>
                <option>Réseau SONEDE / GDA d'irrigation</option>
                <option>Eau traitée recyclée</option>
              </select>
            </div>

            <div>
              <label className="text-xs text-earth-300 font-semibold block mb-1">Source Énergétique des Pompes</label>
              <select
                value={energySource}
                onChange={(e) => setEnergySource(e.target.value)}
                className="w-full bg-sunken border border-line rounded-xl px-3.5 py-2.5 text-xs text-ink focus:outline-none focus:border-brand-500"
              >
                <option>Solaire Hybride (PV + Réseau)</option>
                <option>Pompage Solaire Autonome (Off-Grid)</option>
                <option>Réseau STEG Triphasé Exclusif</option>
                <option>Générateur Diesel</option>
              </select>
            </div>

            <div className="bg-sunken p-3.5 rounded-xl border border-brand-500/20 text-xs text-brand-300 flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
              <span>Optimisation Kizuna : QATRA configurera les cycles d'irrigation synchronisés sur le pic solaire.</span>
            </div>
          </div>
        )}

        {/* Step 3: Interactive Boundary preview */}
        {step === 3 && (
          <div className="space-y-4 text-center">
            <div className="h-48 bg-sunken rounded-xl border border-line flex flex-col items-center justify-center p-4">
              <Compass className="h-10 w-10 text-brand-400 mb-2 animate-spin" />
              <p className="text-xs font-semibold text-ink">Géoréférencement Automatique Réussi</p>
              <p className="text-[11px] text-earth-400 mt-1">
                Coordonnées assignées : [9.4858° E, 35.0382° N] · {totalArea} Ha à {governorate}
              </p>
            </div>
            <p className="text-xs text-earth-300">
              Votre exploitation est prête à être connectée aux capteurs IoT et aux prévisions de marché.
            </p>
          </div>
        )}

        {/* Footer Navigation */}
        <div className="flex items-center justify-between pt-6 border-t border-line mt-8">
          {step > 1 ? (
            <button
              onClick={() => setStep(step - 1)}
              className="px-4 py-2 rounded-xl text-xs font-semibold text-earth-400 hover:text-ink"
            >
              Précédent
            </button>
          ) : <div />}

          <button
            onClick={nextStep}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-accent to-accent-deep hover:from-accent-hover hover:to-accent-deep text-on-accent font-bold text-xs flex items-center gap-2 transition-all border border-brand-500/30 qa-shine"
          >
            <span>{step === 3 ? "Lancer l'Exploitation" : "Continuer"}</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
