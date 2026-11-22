'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  ArrowRight,
  CircleDollarSign,
  CheckCircle2,
  ClipboardCheck,
  Clock3,
  Database,
  FileText,
  Handshake,
  LandPlot,
  Map,
  MessageSquare,
  Satellite,
  Send,
  ShieldAlert,
  Sprout,
  UserRound,
  UsersRound,
  WalletCards,
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { DEMO_DEVICES } from '@/lib/mockData';
import { useFarmStore } from '@/stores/useFarmStore';
import { cn, formatNumber } from '@/lib/utils';
import type { FarmZone } from '@/types';

type CaseStatus = 'urgent' | 'review' | 'resolved';

type NearbyFarm = {
  id: string;
  name: string;
  distance: string;
  area: string;
  crops: string;
  resources: string[];
  data: string;
  finance: string;
  x: number;
  y: number;
};

const NEARBY_FARMS: NearbyFarm[] = [
  { id: 'farm-mateur-02', name: 'Coopérative El Amal', distance: '8 km', area: '42 ha', crops: 'Tomates · Oliviers', resources: ['Station météo', 'Technicien irrigation'], data: '18 capteurs partagés', finance: 'Achats groupés · 12 400 TND', x: 245, y: 90 },
  { id: 'farm-mateur-03', name: 'Ferme Ben Salem', distance: '14 km', area: '27 ha', crops: 'Piments · Grenadiers', resources: ['Pompe de secours', 'Chambre froide'], data: '2 campagnes historiques', finance: 'Vente commune · 8 700 TND', x: 320, y: 165 },
  { id: 'farm-mateur-04', name: 'Domaine Oued Tinja', distance: '22 km', area: '64 ha', crops: 'Céréales · Luzerne', resources: ['Ingénieur agro', 'Débitmètre mobile'], data: '36 parcelles comparables', finance: 'Transport mutualisé · 5 200 TND', x: 145, y: 185 },
];

type FieldCase = {
  id: string;
  zone: FarmZone;
  status: CaseStatus;
  title: string;
  impact: string;
  detected: string;
  source: string[];
};

const STATUS_LABEL: Record<CaseStatus, string> = {
  urgent: 'Intervention urgente',
  review: 'En revue',
  resolved: 'Résolu',
};

export default function IntelligencePage() {
  const { farm } = useFarmStore();
  const [selectedCaseId, setSelectedCaseId] = useState('case-zone-4');
  const [showDossier, setShowDossier] = useState(false);
  const [expertNote, setExpertNote] = useState('');
  const [resolution, setResolution] = useState('Inspection terrain demandée');
  const [submitted, setSubmitted] = useState(false);
  const [selectedArea, setSelectedArea] = useState('25 km autour de Mateur');
  const [selectedFarmId, setSelectedFarmId] = useState(NEARBY_FARMS[0].id);
  const [connectedFarmIds, setConnectedFarmIds] = useState<string[]>([]);

  useEffect(() => {
    const saved = window.localStorage.getItem('qatra-connected-farms');
    if (saved) {
      try { setConnectedFarmIds(JSON.parse(saved)); } catch { setConnectedFarmIds([]); }
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem('qatra-connected-farms', JSON.stringify(connectedFarmIds));
  }, [connectedFarmIds]);

  const cases = useMemo<FieldCase[]>(() => farm.zones
    .filter((zone) => zone.status === 'critical' || zone.status === 'warning')
    .map((zone) => ({
      id: 'case-' + zone.id,
      zone,
      status: zone.status === 'critical' ? 'urgent' : 'review',
      title: zone.status === 'critical' ? 'Stress hydrique à confirmer' : 'Humidité sous surveillance',
      impact: zone.status === 'critical' ? 'Risque de perte de rendement et de stress durable.' : 'Risque de ralentissement de croissance si la baisse continue.',
      detected: zone.status === 'critical' ? 'Détection capteur + seuil culture' : 'Variation capteur + météo locale',
      source: ['Sonde sol ESP32', 'Fiche de culture', zone.ndviStats ? 'NDVI Sentinel-2' : 'Télémétrie locale'],
    })), [farm.zones]);

  const selectedCase = cases.find((item) => item.id === selectedCaseId) ?? cases[0];
  const criticalCount = cases.filter((item) => item.status === 'urgent').length;
  const deviceAlerts = DEMO_DEVICES.filter((device) => device.status === 'alert' || device.status === 'warning').length;

  const submitCase = () => {
    if (!selectedCase) return;
    setSubmitted(true);
  };

  return (
    <AppShell>
      <main className="h-full overflow-y-auto px-4 pb-8 pt-4 sm:px-5 lg:px-6">
        <div className="mx-auto max-w-[1500px] space-y-4">
          <header className="flex flex-col gap-3 border-b border-line pb-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-brand-400"><UsersRound className="h-3.5 w-3.5" /> Connexion terrain · expertise humaine</p>
              <h1 className="mt-1 text-xl font-black tracking-tight text-ink sm:text-2xl">Centre de résolution Agro</h1>
              <p className="mt-1 max-w-3xl text-xs text-earth-400">Un point de rencontre entre agriculteurs et ingénieurs agro pour comprendre les problèmes, agir au bon moment et documenter chaque résultat.</p>
            </div>
            <div className="flex items-center gap-2">
              <Link href="/farm/map" className="inline-flex items-center gap-2 rounded-lg border border-line px-3 py-2 text-xs font-semibold text-earth-300 hover:bg-earth-800 hover:text-ink"><Map className="h-3.5 w-3.5" /> Vision complète</Link>
              <span className="inline-flex items-center gap-2 rounded-lg bg-brand-500/10 px-3 py-2 text-xs font-semibold text-brand-400"><span className="h-2 w-2 rounded-full bg-brand-500" /> 3 ingénieurs disponibles</span>
            </div>
          </header>

          <section className="grid grid-cols-2 divide-x divide-line overflow-hidden rounded-xl border border-line bg-surface sm:grid-cols-4">
            <Summary label="Cas ouverts" value={String(cases.length)} detail="à traiter" icon={FileText} />
            <Summary label="Urgents" value={String(criticalCount)} detail="action humaine" icon={ShieldAlert} tone="critical" />
            <Summary label="Alertes appareils" value={String(deviceAlerts)} detail="à vérifier" icon={AlertTriangle} tone="warning" />
            <Summary label="Cas documentés" value={submitted ? '1' : '0'} detail="prêts à apprendre" icon={ClipboardCheck} tone="success" />
          </section>

          <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,.8fr)_minmax(0,1.2fr)]">
            <section className="overflow-hidden rounded-xl border border-line bg-surface">
              <div className="flex items-center justify-between border-b border-line px-4 py-3">
                <div><h2 className="text-sm font-bold text-ink">Cas terrain à traiter</h2><p className="mt-0.5 text-[11px] text-earth-400">Sélectionnez un problème pour ouvrir son dossier.</p></div>
                <MessageSquare className="h-4 w-4 text-water-400" />
              </div>
              <div className="divide-y divide-line">
                {cases.map((item) => (
                  <button key={item.id} onClick={() => { setSelectedCaseId(item.id); setShowDossier(false); setSubmitted(false); }} className={cn('w-full p-4 text-left transition-colors', selectedCase?.id === item.id ? 'bg-water-500/5' : 'hover:bg-raised')}>
                    <div className="flex items-start gap-3">
                      <span className={cn('mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg', item.status === 'urgent' ? 'bg-alert-500/10 text-alert-400' : 'bg-sun-500/10 text-sun-400')}><AlertTriangle className="h-4 w-4" /></span>
                      <span className="min-w-0 flex-1"><span className="flex items-center justify-between gap-2"><strong className="truncate text-xs text-ink">{item.zone.name}</strong><span className={cn('shrink-0 rounded-full px-2 py-1 text-[9px] font-semibold', item.status === 'urgent' ? 'bg-alert-500/10 text-alert-400' : 'bg-sun-500/10 text-sun-400')}>{STATUS_LABEL[item.status]}</span></span><span className="mt-1 block text-[11px] font-semibold text-earth-300">{item.title}</span><span className="mt-1 block text-[10px] leading-4 text-earth-400">{item.impact}</span></span>
                    </div>
                  </button>
                ))}
                {cases.length === 0 && <div className="p-5 text-xs text-brand-400">Aucun cas ouvert. Les agriculteurs et les capteurs peuvent créer un nouveau dossier.</div>}
              </div>
            </section>

            {selectedCase ? (
              <div className="space-y-3">
                <CaseSummary fieldCase={selectedCase} onOpen={() => setShowDossier((current) => !current)} open={showDossier} />
                {showDossier && <CaseDossier fieldCase={selectedCase} farmName={farm.name} expertNote={expertNote} setExpertNote={setExpertNote} resolution={resolution} setResolution={setResolution} submitted={submitted} onSubmit={submitCase} />}
              </div>
            ) : (
              <section className="rounded-xl border border-line bg-surface p-6 text-sm text-earth-400">Sélectionnez un cas terrain pour consulter le dossier complet.</section>
            )}
          </div>

          <FarmNetworkSection
            selectedArea={selectedArea}
            setSelectedArea={setSelectedArea}
            selectedFarmId={selectedFarmId}
            setSelectedFarmId={setSelectedFarmId}
            connectedFarmIds={connectedFarmIds}
            setConnectedFarmIds={setConnectedFarmIds}
          />
        </div>
      </main>
    </AppShell>
  );
}

function FarmNetworkSection({ selectedArea, setSelectedArea, selectedFarmId, setSelectedFarmId, connectedFarmIds, setConnectedFarmIds }: { selectedArea: string; setSelectedArea: (value: string) => void; selectedFarmId: string; setSelectedFarmId: (value: string) => void; connectedFarmIds: string[]; setConnectedFarmIds: (value: string[]) => void }) {
  const selectedFarm = NEARBY_FARMS.find((farm) => farm.id === selectedFarmId) ?? NEARBY_FARMS[0];
  const [showImpact, setShowImpact] = useState(false);
  const connectedFarms = NEARBY_FARMS.filter((farm) => connectedFarmIds.includes(farm.id));
  const sharedSensors = connectedFarms.reduce((total, farm) => total + extractNumber(farm.data), 0);
  const sharedSurface = connectedFarms.reduce((total, farm) => total + extractNumber(farm.area), 0);
  const sharedFinance = connectedFarms.reduce((total, farm) => total + extractNumber(farm.finance), 0);
  const toggleConnection = (farmId: string) => {
    setConnectedFarmIds(connectedFarmIds.includes(farmId) ? connectedFarmIds.filter((id) => id !== farmId) : [...connectedFarmIds, farmId]);
    setShowImpact(true);
  };

  return (
    <section className="overflow-hidden rounded-xl border border-line bg-surface">
      <div className="flex flex-col gap-3 border-b border-line px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-brand-400"><Handshake className="h-3.5 w-3.5" /> Réseau de coopération</p>
          <h2 className="mt-1 text-base font-bold text-ink">Point de connexion entre fermes proches</h2>
          <p className="mt-0.5 text-[11px] text-earth-400">Partager les ressources, comparer les données et construire des opérations financières ensemble.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2"><label className="text-[10px] font-semibold text-earth-400">Zone logique sélectionnée
          <select value={selectedArea} onChange={(event) => setSelectedArea(event.target.value)} className="ml-2 rounded-lg border border-line bg-sunken px-2.5 py-2 text-xs text-ink outline-none focus:border-water-400">
            <option>25 km autour de Mateur</option>
            <option>50 km · Bizerte Nord</option>
            <option>75 km · Béja Est</option>
          </select>
        </label><button onClick={() => setShowImpact((current) => !current)} className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-2.5 py-2 text-[10px] font-semibold text-on-accent hover:bg-accent-hover">{showImpact ? 'Masquer impact' : 'Voir impact connexion'} <ArrowRight className={cn('h-3 w-3 transition-transform', showImpact && 'rotate-90')} /></button></div>
      </div>

      <div className="grid gap-4 p-4 xl:grid-cols-[minmax(0,.9fr)_minmax(0,1.1fr)]">
        <div className="space-y-3">
          <div className="relative overflow-hidden rounded-xl border border-line bg-[#76886f] aspect-[16/9]" aria-label="Petit plan satellite stylisé de la zone de coopération">
            <div className="absolute inset-0 opacity-30" style={{ backgroundImage: 'linear-gradient(18deg, transparent 45%, rgba(230, 221, 165, .55) 46%, transparent 48%), linear-gradient(110deg, transparent 42%, rgba(45, 81, 55, .55) 43%, transparent 45%)', backgroundSize: '130px 90px, 160px 120px' }} />
            <svg viewBox="0 0 420 240" className="absolute inset-0 h-full w-full" role="img" aria-label="Parcelles agricoles voisines autour de l’exploitation principale">
              <rect x="24" y="28" width="128" height="70" rx="5" fill="#9aaa75" stroke="#d9dfac" strokeWidth="2" />
              <rect x="170" y="28" width="112" height="84" rx="5" fill="#bd9e67" stroke="#e0cf9b" strokeWidth="2" />
              <rect x="294" y="36" width="95" height="65" rx="5" fill="#829b6c" stroke="#d9dfac" strokeWidth="2" />
              <rect x="36" y="126" width="130" height="82" rx="5" fill="#6c936d" stroke="#d9dfac" strokeWidth="2" />
              <rect x="184" y="136" width="102" height="72" rx="5" fill="#b7a76b" stroke="#e0cf9b" strokeWidth="2" />
              <rect x="303" y="126" width="86" height="85" rx="5" fill="#74926e" stroke="#d9dfac" strokeWidth="2" />
              <circle cx="210" cy="113" r="42" fill="none" stroke="#28b8ca" strokeWidth="2.5" strokeDasharray="6 5" />
              <circle cx="210" cy="113" r="7" fill="#28b8ca" stroke="#f4fbfc" strokeWidth="3" />
              {NEARBY_FARMS.map((farm) => <g key={farm.id} onClick={() => setSelectedFarmId(farm.id)} className="cursor-pointer"><circle cx={farm.x} cy={farm.y} r={farm.id === selectedFarmId ? 8 : 6} fill={farm.id === selectedFarmId ? '#f0a43b' : '#f4fbfc'} stroke="#164b55" strokeWidth="3" /><text x={farm.x + 10} y={farm.y + 3} fontSize="9" fontWeight="700" fill="#113840">{farm.name.replace('Coopérative ', '').replace('Ferme ', '').replace('Domaine ', '')}</text></g>)}
              <text x="175" y="106" fontSize="9" fontWeight="700" fill="#0f4854">Votre ferme</text>
            </svg>
            <div className="absolute left-3 top-3 rounded-lg bg-surface/85 px-2 py-1 text-[9px] font-semibold text-ink backdrop-blur">Aperçu satellite · {selectedArea}</div>
            <div className="absolute bottom-3 left-3 flex items-center gap-1.5 rounded-lg bg-surface/85 px-2 py-1 text-[9px] text-earth-300 backdrop-blur"><span className="h-2 w-2 rounded-full bg-water-400" /> Rayon de collaboration</div>
          </div>
          <div className="grid grid-cols-3 gap-2">
            <NetworkMetric icon={Database} label="Données" value={sharedSensors ? sharedSensors + ' points' : 'à partager'} />
            <NetworkMetric icon={LandPlot} label="Surface" value={sharedSurface ? formatNumber(sharedSurface, 0) + ' ha' : 'à mutualiser'} />
            <NetworkMetric icon={CircleDollarSign} label="Opérations" value={sharedFinance ? formatNumber(sharedFinance, 0) + ' TND' : 'à créer'} />
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between"><p className="text-xs font-bold text-ink">Fermes détectées dans la zone</p><span className="text-[10px] text-earth-500">{connectedFarmIds.length} connectée(s)</span></div>
          {NEARBY_FARMS.map((farm) => {
            const connected = connectedFarmIds.includes(farm.id);
            const selected = selectedFarmId === farm.id;
            return (
              <div key={farm.id} onClick={() => setSelectedFarmId(farm.id)} className={cn('rounded-lg border p-3 transition-colors', selected ? 'border-water-400 bg-water-500/5' : 'border-line bg-raised hover:border-water-400/40')}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0"><div className="flex items-center gap-2"><LandPlot className="h-3.5 w-3.5 shrink-0 text-brand-400" /><p className="truncate text-xs font-bold text-ink">{farm.name}</p><span className="shrink-0 rounded-full bg-earth-800 px-1.5 py-0.5 text-[9px] text-earth-300">{farm.distance}</span></div><p className="mt-1 text-[10px] text-earth-400">{farm.area} · {farm.crops}</p></div>
                  <button onClick={(event) => { event.stopPropagation(); toggleConnection(farm.id); }} className={cn('shrink-0 rounded-lg px-2.5 py-1.5 text-[10px] font-semibold', connected ? 'bg-brand-500/15 text-brand-400' : 'bg-accent text-on-accent hover:bg-accent-hover')}>{connected ? 'Synchronisée' : 'Connecter'}</button>
                </div>
                {selected && <div className="mt-3 grid gap-2 border-t border-line pt-2 sm:grid-cols-2"><div><p className="text-[9px] uppercase tracking-wider text-earth-500">Ressources</p><p className="mt-1 text-[10px] text-earth-300">{farm.resources.join(' · ')}</p></div><div><p className="text-[9px] uppercase tracking-wider text-earth-500">Données & finance</p><p className="mt-1 text-[10px] text-brand-400">{farm.data}</p><p className="mt-0.5 text-[10px] text-earth-300">{farm.finance}</p></div></div>}
              </div>
            );
          })}
          <div className="flex items-start gap-2 rounded-lg bg-brand-500/5 p-2.5 text-[10px] leading-4 text-earth-400"><WalletCards className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-400" /> Les connexions peuvent ensuite alimenter un marché commun : achats d’intrants, transport, stockage et ventes groupées.</div>
        </div>
      </div>
      {showImpact && <div className="border-t border-line bg-brand-500/5 px-4 py-3"><p className="text-[10px] font-bold uppercase tracking-wider text-brand-400">Connexion active · impact calculé avec {connectedFarmIds.length} ferme(s)</p><div className="mt-2 grid gap-2 sm:grid-cols-4"><ImpactMini label="Données" value={sharedSensors + ' points'} detail="capteurs et historiques partagés" /><ImpactMini label="Ressources" value={connectedFarms.reduce((total, farm) => total + farm.resources.length, 0) + ' disponibles'} detail="pompes, experts, stockage" /><ImpactMini label="Opérations" value={sharedFinance ? formatNumber(sharedFinance, 0) + ' TND' : 'À créer'} detail="budget identifié pour mutualiser" /><ImpactMini label="Ferme ciblée" value={selectedFarm.distance} detail={selectedFarm.name} /></div><p className="mt-2 text-[10px] text-earth-400">Synchronisation locale active. Les données restent simulées jusqu’au branchement d’une API sécurisée entre exploitants.</p></div>}
    </section>
  );
}

function extractNumber(value: string) {
  const match = value.replace(/\s/g, '').match(/\d+(?:[.,]\d+)?/);
  return match ? Number(match[0].replace(',', '.')) : 0;
}

function ImpactMini({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <div className="rounded-lg border border-brand-500/20 bg-surface p-2.5"><p className="text-[10px] text-earth-500">{label}</p><p className="mt-1 text-sm font-black text-ink">{value}</p><p className="mt-0.5 text-[9px] text-earth-400">{detail}</p></div>;
}

function NetworkMetric({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) {
  return <div className="rounded-lg border border-line bg-raised p-2"><Icon className="h-3.5 w-3.5 text-water-400" /><p className="mt-1 text-[9px] text-earth-500">{label}</p><p className="text-[10px] font-bold text-ink">{value}</p></div>;
}

function CaseSummary({ fieldCase, onOpen, open }: { fieldCase: FieldCase; onOpen: () => void; open: boolean }) {
  return <section className={cn('rounded-xl border bg-surface p-4', fieldCase.status === 'urgent' ? 'border-alert-500/45' : 'border-line')}><div className="flex items-start justify-between gap-3"><div className="flex min-w-0 items-start gap-2.5"><span className={cn('flex h-9 w-9 shrink-0 items-center justify-center rounded-lg', fieldCase.status === 'urgent' ? 'bg-alert-500/10 text-alert-400' : 'bg-sun-500/10 text-sun-400')}><AlertTriangle className="h-4 w-4" /></span><div className="min-w-0"><p className="text-[10px] font-semibold uppercase tracking-wider text-brand-400">Problème sélectionné</p><h2 className="mt-1 truncate text-sm font-bold text-ink">{fieldCase.title}</h2><p className="mt-1 truncate text-[11px] text-earth-400">{fieldCase.zone.name} · {fieldCase.zone.cropType}</p></div></div><span className={cn('shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold', fieldCase.status === 'urgent' ? 'bg-alert-500/10 text-alert-400' : 'bg-sun-500/10 text-sun-400')}>{STATUS_LABEL[fieldCase.status]}</span></div><div className="mt-3 grid grid-cols-3 gap-2"><Fact label="Humidité" value={fieldCase.zone.soilMoisturePercent + '%'} critical={fieldCase.zone.soilMoisturePercent < fieldCase.zone.targetMoistureMin} /><Fact label="Impact" value={fieldCase.status === 'urgent' ? 'Élevé' : 'Modéré'} critical={fieldCase.status === 'urgent'} /><Fact label="Données" value={fieldCase.source.length + ' sources'} /></div><p className="mt-3 text-[11px] leading-4 text-earth-300">{fieldCase.impact}</p><button onClick={onOpen} className="mt-3 inline-flex items-center gap-2 rounded-lg bg-accent px-3 py-2 text-[11px] font-semibold text-on-accent hover:bg-accent-hover">{open ? 'Masquer le dossier' : 'Afficher le dossier complet'} <ArrowRight className={cn('h-3 w-3 transition-transform', open && 'rotate-90')} /></button></section>;
}

function Summary({ label, value, detail, icon: Icon, tone = 'default' }: { label: string; value: string; detail: string; icon: LucideIcon; tone?: 'default' | 'critical' | 'warning' | 'success' }) {
  return <div className="min-w-0 px-3 py-2.5 sm:px-4"><div className="flex items-center justify-between gap-2"><span className="truncate text-[11px] text-earth-400">{label}</span><Icon className={cn('h-3.5 w-3.5', tone === 'critical' ? 'text-alert-400' : tone === 'warning' ? 'text-sun-400' : tone === 'success' ? 'text-brand-400' : 'text-water-400')} /></div><div className="mt-1 flex items-baseline gap-2"><span className="text-lg font-black text-ink">{value}</span><span className="truncate text-[10px] text-earth-500">{detail}</span></div></div>;
}

function CaseDossier({ fieldCase, farmName, expertNote, setExpertNote, resolution, setResolution, submitted, onSubmit }: { fieldCase: FieldCase; farmName: string; expertNote: string; setExpertNote: (value: string) => void; resolution: string; setResolution: (value: string) => void; submitted: boolean; onSubmit: () => void }) {
  const { zone } = fieldCase;
  return (
    <section className={cn('rounded-xl border bg-surface p-4', fieldCase.status === 'urgent' ? 'border-alert-500/45' : 'border-line')}>
      <div className="flex flex-col gap-3 border-b border-line pb-3 sm:flex-row sm:items-start sm:justify-between">
        <div><p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-brand-400">Dossier problème · {fieldCase.id}</p><h2 className="mt-1 text-base font-bold text-ink">{fieldCase.title}</h2><p className="mt-1 text-[11px] text-earth-400">{farmName} · {zone.name} · {zone.cropType}</p></div>
        <span className={cn('self-start rounded-full px-2.5 py-1 text-[10px] font-semibold', fieldCase.status === 'urgent' ? 'bg-alert-500/10 text-alert-400' : 'bg-sun-500/10 text-sun-400')}>{STATUS_LABEL[fieldCase.status]}</span>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="space-y-3">
          <BlockTitle icon={Sprout} title="Vision complète du problème" />
          <div className="grid grid-cols-2 gap-2">
            <Fact label="Humidité sol" value={zone.soilMoisturePercent + '%'} critical={zone.soilMoisturePercent < zone.targetMoistureMin} />
            <Fact label="Seuil culture" value={zone.targetMoistureMin + '–' + zone.targetMoistureMax + '%'} />
            <Fact label="Température" value={zone.temperatureC + ' °C'} />
            <Fact label="Impact estimé" value={fieldCase.status === 'urgent' ? 'Élevé' : 'Modéré'} critical={fieldCase.status === 'urgent'} />
          </div>
          <div className="rounded-lg bg-raised p-3 text-[11px] leading-5 text-earth-300"><strong className="text-ink">Observation :</strong> {fieldCase.detected}. {fieldCase.impact}</div>
          <div className="flex flex-wrap gap-1.5"><span className="text-[10px] font-semibold text-earth-500">Données disponibles :</span>{fieldCase.source.map((source) => <span key={source} className="rounded bg-brand-500/10 px-1.5 py-1 text-[9px] text-brand-400">{source}</span>)}</div>
          <Link href={'/farm/zones/' + zone.id} className="inline-flex items-center gap-1 text-[11px] font-semibold text-water-400 hover:underline">Ouvrir la zone et ses capteurs <ArrowRight className="h-3 w-3 rtl:rotate-180" /></Link>
        </div>

        <div className="space-y-3">
          <BlockTitle icon={ClipboardCheck} title="Checkpoints de l’ingénieur" />
          <Checkpoint label="Confirmer le signal capteur sur le terrain" done />
          <Checkpoint label="Comparer avec l’historique et le NDVI" done={Boolean(zone.ndviStats)} />
          <Checkpoint label="Évaluer le risque agronomique et économique" />
          <Checkpoint label="Documenter l’action et son résultat" />
          <div className="rounded-lg border border-line bg-sunken p-3"><p className="text-[10px] font-bold uppercase tracking-wider text-earth-500">Décision proposée par le système</p><p className="mt-1 text-xs font-bold text-ink">{fieldCase.status === 'urgent' ? 'Inspection humaine + irrigation ciblée de 45 min' : 'Surveillance renforcée + cycle court si le seuil baisse encore'}</p><p className="mt-1 text-[10px] text-earth-400">L’ingénieur peut confirmer, modifier ou refuser cette proposition.</p></div>
        </div>
      </div>

      <div className="mt-4 border-t border-line pt-4">
        <div className="flex items-center gap-2"><UserRound className="h-4 w-4 text-water-400" /><h3 className="text-sm font-bold text-ink">Retour humain et documentation</h3></div>
        <div className="mt-3 grid gap-3 lg:grid-cols-[1fr_220px_auto] lg:items-end">
          <label className="text-[11px] text-earth-400">Analyse de l’ingénieur
            <textarea value={expertNote} onChange={(event) => setExpertNote(event.target.value)} placeholder="Cause probable, observation terrain, action recommandée…" className="mt-1 min-h-20 w-full resize-y rounded-lg border border-line bg-sunken p-2.5 text-xs text-ink outline-none focus:border-water-400" />
          </label>
          <label className="text-[11px] text-earth-400">Résolution retenue
            <select value={resolution} onChange={(event) => setResolution(event.target.value)} className="mt-1 w-full rounded-lg border border-line bg-sunken p-2.5 text-xs text-ink outline-none focus:border-water-400">
              <option>Inspection terrain demandée</option>
              <option>Irrigation ciblée validée</option>
              <option>Capteur à recalibrer</option>
              <option>Fausse alerte documentée</option>
            </select>
          </label>
          <button onClick={onSubmit} className={cn('inline-flex items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-xs font-semibold', submitted ? 'bg-brand-500/15 text-brand-400' : 'bg-accent text-on-accent hover:bg-accent-hover')}><Send className="h-3.5 w-3.5" /> {submitted ? 'Envoyé au système' : 'Valider & envoyer'}</button>
        </div>
        <p className="mt-2 flex items-center gap-1.5 text-[10px] text-earth-500"><Clock3 className="h-3 w-3" /> Le dossier, la décision et l’impact seront conservés pour améliorer les futures recommandations.</p>
      </div>
    </section>
  );
}

function BlockTitle({ icon: Icon, title }: { icon: LucideIcon; title: string }) {
  return <div className="flex items-center gap-2 text-xs font-bold text-ink"><Icon className="h-4 w-4 text-water-400" />{title}</div>;
}

function Fact({ label, value, critical = false }: { label: string; value: string; critical?: boolean }) {
  return <div className="rounded-lg border border-line bg-raised p-2.5"><p className="text-[10px] text-earth-500">{label}</p><p className={cn('mt-1 text-sm font-black', critical ? 'text-alert-400' : 'text-ink')}>{value}</p></div>;
}

function Checkpoint({ label, done = false }: { label: string; done?: boolean }) {
  return <div className="flex items-center gap-2 text-[11px] text-earth-300">{done ? <CheckCircle2 className="h-3.5 w-3.5 text-brand-400" /> : <span className="h-3.5 w-3.5 rounded-full border border-earth-500" />}<span>{label}</span></div>;
}
