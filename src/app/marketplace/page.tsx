'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import {
  Store,
  Tag,
  Calculator,
  CircleDollarSign,
  Ruler,
  WalletCards,
  Droplets,
  Zap,
  TrendingUp,
  Sprout,
  Search,
  Filter,
  MapPin,
  Calendar,
  ShieldCheck,
  ArrowRight,
  MessageSquare,
  Sparkles,
  Check
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { DEMO_LISTINGS } from '@/lib/mockData';
import { useFarmStore } from '@/stores/useFarmStore';
import { ProductListing } from '@/types';
import type { Farm } from '@/types';
import { cn, formatNumber, formatCurrencyTND } from '@/lib/utils';

export default function MarketplacePage() {
  const { farm } = useFarmStore();
  const [listings, setListings] = useState<ProductListing[]>(DEMO_LISTINGS);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedGovernorate, setSelectedGovernorate] = useState('all');
  const [inquirySentId, setInquirySentId] = useState<string | null>(null);

  const filteredListings = listings.filter((l) => {
    const matchesSearch = l.cropName.toLowerCase().includes(searchQuery.toLowerCase()) || l.farmerName.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesGov = selectedGovernorate === 'all' || l.governorate === selectedGovernorate;
    return matchesSearch && matchesGov;
  });

  const handleSendInquiry = (id: string) => {
    setInquirySentId(id);
    setTimeout(() => setInquirySentId(null), 3000);
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-line gap-4">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-brand-400">
              Circuits Courts & Valorisation Directe (Kizuna)
            </span>
            <h1 className="text-2xl font-black text-ink">Place de Marché Agricole QATRA</h1>
            <p className="text-xs text-earth-400 mt-0.5">
              Connexion directe entre producteurs tunisiens et transformateurs, grossistes & exportateurs
            </p>
          </div>

          <Link
            href="/marketplace/listings"
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-accent to-accent-deep hover:from-accent-hover text-on-accent font-bold text-xs flex items-center gap-2 border border-brand-500/30 qa-shine"
          >
            <Tag className="h-4 w-4" />
            <span>Publier une Récolte</span>
          </Link>
        </div>

        {/* Search & Filter Bar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-surface p-3 rounded-2xl border border-line qa-card">
          <div className="relative w-full sm:w-80">
            <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-earth-400" />
            <input
              type="text"
              placeholder="Rechercher par culture, variété, producteur..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-sunken border border-line rounded-xl pl-9 pr-3 py-2 text-xs text-ink placeholder-earth-500 focus:outline-none focus:border-brand-500"
            />
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <select
              value={selectedGovernorate}
              onChange={(e) => setSelectedGovernorate(e.target.value)}
              className="bg-sunken border border-line rounded-xl px-3 py-2 text-xs text-ink focus:outline-none focus:border-brand-500"
            >
              <option value="all">Tous les gouvernorats</option>
              <option value="Sidi Bouzid">Sidi Bouzid</option>
              <option value="Kairouan">Kairouan</option>
              <option value="Sfax">Sfax</option>
              <option value="Nabeul">Nabeul</option>
              <option value="Bizerte">Bizerte</option>
            </select>
          </div>
        </div>

        <ProfitabilityCalculator farm={farm} />

        {/* Listings Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredListings.map((item) => (
            <div
              key={item.id}
              className="p-5 rounded-2xl border border-line bg-surface flex flex-col justify-between space-y-4 shadow-xl hover:border-brand-500/40 transition-all qa-card"
            >
              <div>
                <div className="flex items-start justify-between">
                  <div>
                    <span className="text-[10px] font-mono text-brand-400 font-semibold flex items-center gap-1">
                      <MapPin className="h-3 w-3" /> {item.governorate} · {item.farmName}
                    </span>
                    <h3 className="text-lg font-bold text-ink mt-1">{item.cropName}</h3>
                    <p className="text-xs text-earth-400">{item.variety}</p>
                  </div>
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-brand-500/20 text-brand-300 border border-brand-500/30">
                    {item.qualityGrade}
                  </span>
                </div>

                <p className="text-xs text-earth-300 mt-3 leading-relaxed">
                  {item.description}
                </p>

                <div className="flex flex-wrap gap-1.5 mt-3">
                  {item.certifications.map((cert, i) => (
                    <span key={i} className="px-2 py-0.5 rounded bg-sunken text-[10px] text-earth-400 border border-line">
                      {cert}
                    </span>
                  ))}
                </div>
              </div>

              <div className="pt-3 border-t border-line space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <div>
                    <span className="text-[10px] text-earth-500 block">Quantité Disponible</span>
                    <span className="font-mono font-bold text-ink">{formatNumber(item.quantityKg)} kg</span>
                  </div>

                  <div className="text-right">
                    <span className="text-[10px] text-earth-500 block">Prix Demandé</span>
                    <span className="font-mono font-black text-sun-300 text-sm">
                      {formatCurrencyTND(item.askingPriceTndKg)}/kg
                    </span>
                  </div>
                </div>

                <button
                  onClick={() => handleSendInquiry(item.id)}
                  className="w-full py-2.5 rounded-xl bg-gradient-to-r from-accent to-accent-deep hover:from-accent-hover hover:to-accent-deep text-on-accent font-bold text-xs flex items-center justify-center gap-1.5 transition-all border border-brand-500/30 qa-shine"
                >
                  {inquirySentId === item.id ? (
                    <>
                      <Check className="h-4 w-4" />
                      <span>Demande d'Achat Envoyée !</span>
                    </>
                  ) : (
                    <>
                      <MessageSquare className="h-4 w-4" />
                      <span>Contacter le Producteur ({item.inquiryCount} offres)</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </AppShell>
  );
}

function ProfitabilityCalculator({ farm }: { farm: Farm }) {
  const [selectedZoneId, setSelectedZoneId] = useState(farm.zones[0]?.id ?? '');
  const [salePrice, setSalePrice] = useState(3.9);
  const [seasonDays, setSeasonDays] = useState(120);
  const [inputCostPerHa, setInputCostPerHa] = useState(2200);
  const [laborCostPerHa, setLaborCostPerHa] = useState(1800);
  const [fixedCostPerHa, setFixedCostPerHa] = useState(600);
  const [waterPrice, setWaterPrice] = useState(0.9);
  const [energyPrice, setEnergyPrice] = useState(0.32);
  const [packagingCostPerKg, setPackagingCostPerKg] = useState(0.35);
  const [transportCostPerKg, setTransportCostPerKg] = useState(0.18);

  const zone = farm.zones.find((item) => item.id === selectedZoneId) ?? farm.zones[0];
  if (!zone) return null;

  const seasonalWaterM3 = (zone.dailyWaterLiters * seasonDays) / 1000;
  const seasonalEnergyKwh = zone.dailyEnergyKwh * seasonDays;
  const harvestKg = zone.yieldEstimateTons * 1000;
  const productionCosts = {
    inputs: inputCostPerHa * zone.areaHa,
    labor: laborCostPerHa * zone.areaHa,
    fixed: fixedCostPerHa * zone.areaHa,
    water: seasonalWaterM3 * waterPrice,
    energy: seasonalEnergyKwh * energyPrice,
    packaging: harvestKg * packagingCostPerKg,
    transport: harvestKg * transportCostPerKg,
  };
  const totalCost = Object.values(productionCosts).reduce((sum, value) => sum + value, 0);
  const revenue = harvestKg * salePrice;
  const profit = revenue - totalCost;
  const costPerM2 = totalCost / (zone.areaHa * 10000);
  const profitPerM2 = profit / (zone.areaHa * 10000);
  const margin = revenue > 0 ? (profit / revenue) * 100 : 0;
  const positiveProfit = Math.max(0, profit);
  const safetyReserve = positiveProfit * 0.2;
  const growthBudget = positiveProfit * 0.35;
  const availableAfterReserve = positiveProfit - safetyReserve;
  const waterSavingPct = zone.status === 'critical' ? 0.08 : 0.15;
  const energySavingPct = zone.status === 'critical' ? 0.06 : 0.12;
  const waterSavedM3 = seasonalWaterM3 * waterSavingPct;
  const energySavedKwh = seasonalEnergyKwh * energySavingPct;
  const nextAction = profit > 0 ? 'Réinvestir une partie du gain dans le pilotage de la zone' : 'Corriger les coûts ou le prix avant d’augmenter la production';

  return (
    <section className="rounded-2xl border border-brand-500/25 bg-surface p-4 shadow-xl qa-card">
      <div className="flex flex-col gap-3 border-b border-line pb-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider text-brand-400"><Calculator className="h-3.5 w-3.5" /> Rentabilité par parcelle</p>
          <h2 className="mt-1 text-base font-bold text-ink">Combien coûte 1 m² et combien rapporte-t-il ?</h2>
          <p className="mt-0.5 text-[11px] text-earth-400">Le calcul combine surface, rendement, eau, énergie, main-d’œuvre, intrants, emballage et transport.</p>
        </div>
        <label className="text-[10px] font-semibold text-earth-400">Zone analysée
          <select value={selectedZoneId} onChange={(event) => setSelectedZoneId(event.target.value)} className="ml-2 rounded-lg border border-line bg-sunken px-2.5 py-2 text-xs text-ink outline-none focus:border-brand-500">
            {farm.zones.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </label>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_1.35fr]">
        <div className="grid grid-cols-2 gap-2 text-[10px]">
          <Input label="Prix de vente (DT/kg)" value={salePrice} onChange={setSalePrice} step="0.05" />
          <Input label="Durée de campagne (jours)" value={seasonDays} onChange={setSeasonDays} step="1" />
          <Input label="Intrants (DT/ha)" value={inputCostPerHa} onChange={setInputCostPerHa} step="50" />
          <Input label="Main-d’œuvre (DT/ha)" value={laborCostPerHa} onChange={setLaborCostPerHa} step="50" />
          <Input label="Charges fixes (DT/ha)" value={fixedCostPerHa} onChange={setFixedCostPerHa} step="50" />
          <Input label="Eau (DT/m³)" value={waterPrice} onChange={setWaterPrice} step="0.05" />
          <Input label="Énergie (DT/kWh)" value={energyPrice} onChange={setEnergyPrice} step="0.01" />
          <Input label="Emballage + transport (DT/kg)" value={packagingCostPerKg + transportCostPerKg} onChange={(value) => { setPackagingCostPerKg(value * 0.66); setTransportCostPerKg(value * 0.34); }} step="0.05" />
        </div>

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Result icon={Ruler} label="Surface" value={formatNumber(zone.areaHa, 1) + ' ha'} detail={formatNumber(zone.areaHa * 10000, 0) + ' m²'} />
          <Result icon={WalletCards} label="Coût total" value={formatCurrencyTND(totalCost)} detail={formatCurrencyTND(costPerM2) + ' / m²'} tone="warning" />
          <Result icon={CircleDollarSign} label="Chiffre d’affaires" value={formatCurrencyTND(revenue)} detail={formatCurrencyTND(revenue / (zone.areaHa * 10000)) + ' / m²'} tone="water" />
          <Result icon={TrendingUp} label="Gain net estimé" value={formatCurrencyTND(profit)} detail={formatCurrencyTND(profitPerM2) + ' / m² · marge ' + margin.toFixed(1) + '%'} tone={profit >= 0 ? 'success' : 'critical'} />
          <div className="col-span-2 rounded-lg border border-line bg-raised p-3 text-[10px] text-earth-400 sm:col-span-4">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1"><span><Droplets className="mr-1 inline h-3 w-3 text-water-400" />{formatNumber(seasonalWaterM3, 0)} m³ eau</span><span><Zap className="mr-1 inline h-3 w-3 text-sun-400" />{formatNumber(seasonalEnergyKwh, 0)} kWh énergie</span><span><Sprout className="mr-1 inline h-3 w-3 text-brand-400" />{formatNumber(harvestKg, 0)} kg rendement prévu</span></div>
            <p className="mt-2">Pour obtenir un coût exact, remplacez les hypothèses par vos factures réelles d’intrants, d’eau, d’énergie, de salaires et de transport.</p>
          </div>
        </div>
      </div>

      <div className="mt-4 rounded-xl border border-brand-500/25 bg-brand-500/5 p-4">
        <div className="flex flex-col gap-2 border-b border-brand-500/15 pb-3 sm:flex-row sm:items-center sm:justify-between"><div><p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider text-brand-400"><Sparkles className="h-3.5 w-3.5" /> Prochaines étapes QATRA</p><h3 className="mt-1 text-sm font-bold text-ink">Le gain sert à faire grandir la ferme et réduire les consommations</h3></div><span className="rounded-full bg-brand-500/10 px-2.5 py-1 text-[10px] font-semibold text-brand-400">Simulation · à valider</span></div>
        <div className="mt-3 grid gap-2 sm:grid-cols-3"><PlanCard icon={ShieldCheck} label="Réserve de sécurité" value={formatCurrencyTND(safetyReserve)} detail="20% du gain pour les imprévus, maladies, météo ou prix." tone="warning" /><PlanCard icon={Sprout} label="Budget croissance" value={formatCurrencyTND(growthBudget)} detail="35% pour capteurs, irrigation, sol et productivité." tone="success" /><PlanCard icon={CircleDollarSign} label="Disponible après réserve" value={formatCurrencyTND(availableAfterReserve)} detail="Reste à répartir après validation des investissements." tone="water" /></div>
        <div className="mt-3 grid gap-2 lg:grid-cols-[1fr_1fr]">
          <div className="rounded-lg border border-line bg-surface p-3"><p className="text-[10px] font-bold uppercase tracking-wider text-earth-500">Impact attendu des optimisations</p><div className="mt-2 grid grid-cols-2 gap-2 text-[10px]"><ImpactLine icon={Droplets} label="Eau économisée" value={`${formatNumber(waterSavedM3, 1)} m³`} note={`${Math.round(waterSavingPct * 100)}% scénario`} /><ImpactLine icon={Zap} label="Énergie évitée" value={`${formatNumber(energySavedKwh, 0)} kWh`} note={`${Math.round(energySavingPct * 100)}% scénario`} /><ImpactLine icon={Sprout} label="Rendement protégé" value={`${formatNumber(harvestKg, 0)} kg`} note="à confirmer par parcelle" /><ImpactLine icon={MapPin} label="Contexte Tunisie" value="Eau prioritaire" note="coût, climat, disponibilité" /></div></div>
          <div className="rounded-lg border border-line bg-surface p-3"><p className="text-[10px] font-bold uppercase tracking-wider text-earth-500">Décision suivante</p><p className="mt-2 text-xs font-bold text-ink">{nextAction}</p><div className="mt-2 space-y-1.5 text-[10px] text-earth-400"><p>1. Vérifier les factures et le rendement réel.</p><p>2. Tester l’économie sur une zone pendant 14 jours.</p><p>3. Comparer eau, énergie, qualité et revenu.</p><p>4. Généraliser seulement si l’impact est confirmé.</p></div><p className="mt-2 flex items-center gap-1 text-[10px] font-semibold text-brand-400"><ShieldCheck className="h-3 w-3" /> Pas de réservation financière automatique · validation humaine obligatoire</p></div>
        </div>
      </div>
    </section>
  );
}

function PlanCard({ icon: Icon, label, value, detail, tone }: { icon: typeof ShieldCheck; label: string; value: string; detail: string; tone: 'warning' | 'success' | 'water' }) {
  return <div className={cn('rounded-lg border p-3', tone === 'warning' ? 'border-sun-500/25 bg-sun-500/5' : tone === 'success' ? 'border-brand-500/25 bg-brand-500/5' : 'border-water-500/25 bg-water-500/5')}><Icon className={cn('h-4 w-4', tone === 'warning' ? 'text-sun-400' : tone === 'success' ? 'text-brand-400' : 'text-water-400')} /><p className="mt-2 text-[10px] text-earth-500">{label}</p><p className="mt-0.5 text-sm font-black text-ink">{value}</p><p className="mt-1 text-[10px] leading-4 text-earth-400">{detail}</p></div>;
}

function ImpactLine({ icon: Icon, label, value, note }: { icon: typeof Droplets; label: string; value: string; note: string }) {
  return <div className="rounded-lg bg-raised p-2"><div className="flex items-center gap-1 text-earth-500"><Icon className="h-3 w-3 text-water-400" />{label}</div><p className="mt-1 font-bold text-ink">{value}</p><p className="mt-0.5 text-[9px] text-earth-500">{note}</p></div>;
}

function Input({ label, value, onChange, step }: { label: string; value: number; onChange: (value: number) => void; step: string }) {
  return <label className="text-earth-400">{label}<input type="number" min="0" step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} className="mt-1 w-full rounded-lg border border-line bg-sunken px-2.5 py-2 font-mono text-xs text-ink outline-none focus:border-brand-500" /></label>;
}

function Result({ icon: Icon, label, value, detail, tone = 'default' }: { icon: typeof Ruler; label: string; value: string; detail: string; tone?: 'default' | 'warning' | 'water' | 'success' | 'critical' }) {
  return <div className={cn('rounded-lg border p-3', tone === 'critical' ? 'border-alert-500/30 bg-alert-500/5' : tone === 'success' ? 'border-brand-500/30 bg-brand-500/5' : tone === 'warning' ? 'border-sun-500/30 bg-sun-500/5' : tone === 'water' ? 'border-water-500/30 bg-water-500/5' : 'border-line bg-raised')}><Icon className={cn('h-3.5 w-3.5', tone === 'critical' ? 'text-alert-400' : tone === 'success' ? 'text-brand-400' : tone === 'warning' ? 'text-sun-400' : 'text-water-400')} /><p className="mt-2 text-[10px] text-earth-500">{label}</p><p className="mt-0.5 text-sm font-black text-ink">{value}</p><p className="mt-1 text-[10px] text-earth-400">{detail}</p></div>;
}
