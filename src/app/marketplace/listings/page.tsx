'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import {
  Tag,
  Plus,
  ArrowLeft,
  CheckCircle2,
  X,
  Sparkles,
  Eye,
  MessageSquare,
  CircleDollarSign,
  Droplets,
  Sun,
  TrendingDown,
  Scale,
  AlertTriangle
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { DEMO_ENERGY_TELEMETRY, DEMO_LISTINGS, DEMO_WATER_BASELINE } from '@/lib/mockData';
import { useFarmStore } from '@/stores/useFarmStore';
import { ProductListing } from '@/types';
import type { Farm } from '@/types';
import { cn, formatNumber, formatCurrencyTND } from '@/lib/utils';

export default function MyListingsPage() {
  const { farm } = useFarmStore();
  const [listings, setListings] = useState<ProductListing[]>(DEMO_LISTINGS.filter(l => l.farmerName === 'Tarak Ben Salem'));
  const [modalOpen, setModalOpen] = useState(false);
  const [cropName, setCropName] = useState('Piments Baklouti');
  const [variety, setVariety] = useState('Baklouti Rouge Sélection');
  const [quantity, setQuantity] = useState(4000);
  const [price, setPrice] = useState(3.900);
  const [grade, setGrade] = useState<'Extra' | 'Catégorie I' | 'Catégorie II'>('Extra');
  const [description, setDescription] = useState('Culture sous goutte-à-goutte optimisé par capteurs solaires QATRA. Récolte fraîche garantie.');

  const handleCreateListing = (e: React.FormEvent) => {
    e.preventDefault();
    const newListing: ProductListing = {
      id: `list-${Date.now()}`,
      farmerName: 'Tarak Ben Salem',
      farmName: 'Domaine El-Baraka',
      governorate: 'Sidi Bouzid',
      cropName,
      variety,
      quantityKg: Number(quantity),
      harvestDate: '2026-12-25',
      askingPriceTndKg: Number(price),
      qualityGrade: grade,
      status: 'available',
      description,
      certifications: ['Origine Sidi Bouzid', 'Irrigation Solaire Efficience A+'],
      inquiryCount: 0,
      createdAt: new Date().toISOString().split('T')[0],
    };

    setListings([newListing, ...listings]);
    setModalOpen(false);
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-line gap-4">
          <div className="flex items-center gap-3">
            <Link
              href="/marketplace"
              className="p-2 rounded-xl bg-surface border border-line text-earth-300 hover:text-ink qa-card"
            >
              <ArrowLeft className="h-4 w-4" />
            </Link>
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-brand-400">
                Mon Espace Vendeur
              </span>
              <h1 className="text-2xl font-black text-ink">Mes Récoltes Mises en Vente</h1>
            </div>
          </div>

          <button
            onClick={() => setModalOpen(true)}
            className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-accent to-accent-deep hover:from-accent-hover text-on-accent font-bold text-xs flex items-center gap-2 border border-brand-500/30 qa-shine"
          >
            <Plus className="h-4 w-4" />
            <span>Mettre en Vente une Nouvelle Récolte</span>
          </button>
        </div>

        <QatraImpactComparison farm={farm} />

        {/* Listings List */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {listings.map((item) => (
            <div
              key={item.id}
              className="p-5 rounded-2xl border border-line bg-surface space-y-4 shadow-xl qa-card"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-lg font-bold text-ink">{item.cropName}</h3>
                  <p className="text-xs text-brand-400 font-medium">{item.variety}</p>
                </div>
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-brand-500/20 text-brand-300 border border-brand-500/30">
                  {item.status === 'available' ? 'Disponible' : 'Réservé'}
                </span>
              </div>

              <p className="text-xs text-earth-300 leading-relaxed">
                {item.description}
              </p>

              <div className="grid grid-cols-2 gap-3 bg-sunken p-3 rounded-xl border border-line text-xs">
                <div>
                  <span className="text-[10px] text-earth-500">Volume</span>
                  <p className="font-mono font-bold text-ink mt-0.5">{formatNumber(item.quantityKg)} kg</p>
                </div>
                <div>
                  <span className="text-[10px] text-earth-500">Prix Demandé</span>
                  <p className="font-mono font-bold text-sun-300 mt-0.5">{formatCurrencyTND(item.askingPriceTndKg)}/kg</p>
                </div>
              </div>

              <div className="flex items-center justify-between text-xs text-earth-400 pt-2 border-t border-line">
                <span className="flex items-center gap-1.5 text-brand-400 font-medium">
                  <MessageSquare className="h-3.5 w-3.5" />
                  {item.inquiryCount} acheteurs intéressés
                </span>
                <span>Publié le {item.createdAt}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Modal: Create Listing */}
        {modalOpen && (
          <div className="fixed inset-0 bg-earth-900/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="glass-panel rounded-glass max-w-lg w-full p-6 relative">
              <div className="flex items-center justify-between pb-3 border-b border-line">
                <h3 className="text-base font-bold text-ink">Publier une Récolte sur la Place de Marché</h3>
                <button onClick={() => setModalOpen(false)} className="text-earth-400 hover:text-ink">
                  <X className="h-5 w-5" />
                </button>
              </div>

              <form onSubmit={handleCreateListing} className="space-y-4 mt-4 text-xs">
                <div>
                  <label className="text-earth-300 font-semibold block mb-1">Culture</label>
                  <input
                    type="text"
                    value={cropName}
                    onChange={(e) => setCropName(e.target.value)}
                    className="w-full bg-sunken border border-line rounded-xl px-3 py-2 text-ink focus:outline-none focus:border-brand-500"
                    required
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-earth-300 font-semibold block mb-1">Quantité Estimée (kg)</label>
                    <input
                      type="number"
                      value={quantity}
                      onChange={(e) => setQuantity(Number(e.target.value))}
                      className="w-full bg-sunken border border-line rounded-xl px-3 py-2 text-ink font-mono focus:outline-none focus:border-brand-500"
                      required
                    />
                  </div>
                  <div>
                    <label className="text-earth-300 font-semibold block mb-1">Prix Souhaité (TND/kg)</label>
                    <input
                      type="number"
                      step="0.050"
                      value={price}
                      onChange={(e) => setPrice(Number(e.target.value))}
                      className="w-full bg-sunken border border-line rounded-xl px-3 py-2 text-ink font-mono focus:outline-none focus:border-brand-500"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="text-earth-300 font-semibold block mb-1">Description & Qualité</label>
                  <textarea
                    rows={3}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    className="w-full bg-sunken border border-line rounded-xl px-3 py-2 text-ink focus:outline-none focus:border-brand-500"
                  />
                </div>

                <div className="flex gap-3 pt-3">
                  <button
                    type="button"
                    onClick={() => setModalOpen(false)}
                    className="flex-1 py-2 rounded-xl bg-earth-800 text-earth-300 font-semibold"
                  >
                    Annuler
                  </button>
                  <button
                    type="submit"
                    className="flex-1 py-2 rounded-xl bg-accent hover:bg-accent-hover text-on-accent font-bold shadow-lg"
                  >
                    Mettre en Ligne
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}

function QatraImpactComparison({ farm }: { farm: Farm }) {
  const totalWaterWith = farm.zones.reduce((sum, zone) => sum + zone.dailyWaterLiters, 0);
  const totalYield = farm.zones.reduce((sum, zone) => sum + zone.yieldEstimateTons, 0);
  const classicWater = DEMO_WATER_BASELINE.classicIrrigationLitersPerDay;
  const waterSaved = Math.max(0, classicWater - totalWaterWith);
  const waterSavedPct = Math.round((waterSaved / classicWater) * 100);
  const waterCostSavedDaily = (waterSaved / 1000) * 0.9;
  const solarShare = DEMO_ENERGY_TELEMETRY.gridImportKw === 0 ? 100 : Math.round((1 - DEMO_ENERGY_TELEMETRY.gridImportKw / Math.max(DEMO_ENERGY_TELEMETRY.solarProductionKw, 1)) * 100);
  const withoutSystemEnergyShare = 45;
  const protectedYield = totalYield * 0.92;

  return (
    <section className="rounded-2xl border border-brand-500/25 bg-surface p-4 shadow-xl qa-card">
      <div className="flex flex-col gap-3 border-b border-line pb-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider text-brand-400"><Scale className="h-3.5 w-3.5" /> Valeur de QATRA pour votre exploitation</p>
          <h2 className="mt-1 text-base font-bold text-ink">Que se passe-t-il avec et sans le système ?</h2>
          <p className="mt-0.5 text-[11px] text-earth-400">Comparaison de référence sur vos données actuelles, pour comprendre ce que vous gagnez et ce que vous risquez sans pilotage.</p>
        </div>
        <span className="inline-flex items-center gap-1.5 self-start rounded-full bg-sun-500/10 px-2.5 py-1 text-[10px] font-semibold text-sun-400"><AlertTriangle className="h-3 w-3" /> Scénario de référence</span>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <ScenarioCard title="Sans QATRA · irrigation classique" tone="without" items={[
          ['Eau', formatNumber(classicWater) + ' L / jour', 'Référence classique'],
          ['Énergie réseau', withoutSystemEnergyShare + ' %', 'Hypothèse à remplacer'],
          ['Rendement exposé', formatNumber(protectedYield, 1) + ' T', 'Scénario stress -8 %'],
          ['Pilotage', 'Manuel', 'Pas de décision capteur'],
        ]} />
        <ScenarioCard title="Avec QATRA · pilotage connecté" tone="with" items={[
          ['Eau', formatNumber(totalWaterWith) + ' L / jour', '-' + waterSavedPct + ' % vs classique'],
          ['Autonomie solaire', solarShare + ' %', formatNumber(DEMO_ENERGY_TELEMETRY.solarProductionKw, 1) + ' kW produits'],
          ['Rendement projeté', formatNumber(totalYield, 1) + ' T', 'Selon les zones actuelles'],
          ['Pilotage', 'Automatique + humain', 'Capteurs, agents et historique'],
        ]} />
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-3">
        <ImpactFact icon={Droplets} label="Eau sauvée" value={formatNumber(waterSaved) + ' L / jour'} detail={formatNumber(waterSaved * 30) + ' L / mois'} />
        <ImpactFact icon={CircleDollarSign} label="Coût eau évité" value={waterCostSavedDaily.toFixed(2) + ' DT / jour'} detail="base indicative : 0,90 DT/m³" />
        <ImpactFact icon={TrendingDown} label="Risque sans système" value="-8 % rendement" detail="hypothèse à confirmer par historique" tone="warning" />
      </div>

      <p className="mt-3 text-[10px] leading-4 text-earth-500">Pour une comparaison financière exacte, remplacez les hypothèses par vos factures d’eau, d’énergie, de main-d’œuvre et vos rendements historiques. Le système pourra ensuite mesurer le résultat réel après chaque campagne.</p>
    </section>
  );
}

function ScenarioCard({ title, tone, items }: { title: string; tone: 'without' | 'with'; items: [string, string, string][] }) {
  return (
    <div className={cn('rounded-xl border p-3', tone === 'without' ? 'border-alert-500/25 bg-alert-500/5' : 'border-brand-500/25 bg-brand-500/5')}>
      <div className="flex items-center gap-2"><span className={cn('h-2 w-2 rounded-full', tone === 'without' ? 'bg-alert-500' : 'bg-brand-500')} /><h3 className="text-xs font-bold text-ink">{title}</h3></div>
      <div className="mt-3 grid grid-cols-2 gap-2">{items.map(([label, value, detail]) => <div key={label} className="rounded-lg bg-surface/70 p-2"><p className="text-[10px] text-earth-500">{label}</p><p className="mt-1 text-sm font-black text-ink">{value}</p><p className="mt-0.5 text-[9px] text-earth-400">{detail}</p></div>)}</div>
    </div>
  );
}

function ImpactFact({ icon: Icon, label, value, detail, tone = 'success' }: { icon: typeof Droplets; label: string; value: string; detail: string; tone?: 'success' | 'warning' }) {
  return <div className={cn('rounded-xl border p-3', tone === 'warning' ? 'border-sun-500/30 bg-sun-500/5' : 'border-brand-500/25 bg-brand-500/5')}><Icon className={cn('h-4 w-4', tone === 'warning' ? 'text-sun-400' : 'text-brand-400')} /><p className="mt-2 text-[10px] text-earth-500">{label}</p><p className="mt-0.5 text-sm font-black text-ink">{value}</p><p className="mt-1 text-[10px] text-earth-400">{detail}</p></div>;
}
