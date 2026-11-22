'use client';

import { useState } from 'react';
import {
  Activity,
  ArrowDown,
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  Droplets,
  Eye,
  FileCheck2,
  FlaskConical,
  Gauge,
  GitBranch,
  LockKeyhole,
  RefreshCw,
  ShieldCheck,
  Sprout,
  Sun,
  UsersRound,
  Zap,
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { DEMO_DEVICES, DEMO_ENERGY_TELEMETRY } from '@/lib/mockData';
import { useFarmStore } from '@/stores/useFarmStore';
import { cn, formatNumber } from '@/lib/utils';

type Proposal = {
  id: string;
  title: string;
  domain: string;
  icon: typeof Droplets;
  status: 'À vérifier' | 'En test' | 'Mesuré';
  prediction: string;
  checkpoint: string;
  sources: string[];
  impact: string;
  tone: 'water' | 'energy' | 'agri' | 'consumption';
};

const DOMAIN_STYLE = {
  water: { icon: 'text-water-400', border: 'border-water-500/30', bg: 'bg-water-500/5', badge: 'bg-water-500/10 text-water-400' },
  energy: { icon: 'text-sun-400', border: 'border-sun-500/30', bg: 'bg-sun-500/5', badge: 'bg-sun-500/10 text-sun-400' },
  agri: { icon: 'text-brand-400', border: 'border-brand-500/30', bg: 'bg-brand-500/5', badge: 'bg-brand-500/10 text-brand-400' },
  consumption: { icon: 'text-purple-400', border: 'border-purple-500/30', bg: 'bg-purple-500/5', badge: 'bg-purple-500/10 text-purple-400' },
};

export default function NotificationsPage() {
  const { farm } = useFarmStore();
  const [reviewedIds, setReviewedIds] = useState<string[]>([]);
  const criticalZones = farm.zones.filter((zone) => zone.status === 'critical').length;
  const onlineDevices = DEMO_DEVICES.filter((device) => device.status === 'online').length;
  const proposals: Proposal[] = [
    { id: 'water', title: 'Réduire l’eau sur les zones stables', domain: 'Eau', icon: Droplets, status: criticalZones ? 'À vérifier' : 'En test', prediction: 'Éviter un cycle sur les zones au-dessus du seuil.', checkpoint: 'Comparer humidité avant/après pendant 24 h.', sources: ['Sondes sol ESP32', 'Historique irrigation', 'Seuils par culture'], impact: 'Litres économisés sans baisse de rendement', tone: 'water' },
    { id: 'energy', title: 'Déplacer le pompage vers la fenêtre solaire', domain: 'Énergie', icon: Sun, status: 'En test', prediction: 'Couvrir la pompe avec ' + formatNumber(DEMO_ENERGY_TELEMETRY.solarProductionKw, 1) + ' kW solaires disponibles.', checkpoint: 'Vérifier production, demande pompe et batterie.', sources: ['Onduleur PV', 'BMS batterie', 'Compteur pompe'], impact: 'kWh réseau évités et coût énergétique', tone: 'energy' },
    { id: 'agri', title: 'Tester une action sur la zone la plus fragile', domain: 'Agriculture', icon: Sprout, status: criticalZones ? 'À vérifier' : 'Mesuré', prediction: criticalZones + ' zone(s) nécessitent une validation agronomique.', checkpoint: 'Faire confirmer l’observation par un ingénieur agro.', sources: ['NDVI Sentinel-2', 'Température sol', 'Historique de rendement'], impact: 'Rendement, stress et qualité de récolte', tone: 'agri' },
    { id: 'consumption', title: 'Comparer la consommation entre parcelles', domain: 'Consommation', icon: Gauge, status: 'À vérifier', prediction: 'Identifier la zone qui consomme le plus par hectare.', checkpoint: 'Normaliser par surface, culture et stade de croissance.', sources: ['Compteurs eau/énergie', 'Surface des zones', 'Journal des opérations'], impact: 'Coût par m² et efficacité globale', tone: 'consumption' },
  ];

  const markReviewed = (id: string) => {
    if (!reviewedIds.includes(id)) setReviewedIds([...reviewedIds, id]);
  };

  return (
    <AppShell>
      <main className="h-full overflow-y-auto px-4 pb-8 pt-4 sm:px-5 lg:px-6">
        <div className="mx-auto max-w-[1500px] space-y-4">
          <header className="flex flex-col gap-3 border-b border-line pb-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-brand-400"><RefreshCw className="h-3.5 w-3.5" /> Système évolutif & vérifié</p>
              <h1 className="mt-1 text-xl font-black tracking-tight text-ink sm:text-2xl">Prochaines étapes</h1>
              <p className="mt-1 max-w-3xl text-xs text-earth-400">Le système observe l’environnement chaque jour, propose plusieurs solutions, teste à petite échelle, mesure l’impact et apprend sans s’arrêter à une seule réponse.</p>
            </div>
            <span className="inline-flex items-center gap-2 self-start rounded-lg bg-brand-500/10 px-3 py-2 text-xs font-semibold text-brand-400"><ShieldCheck className="h-3.5 w-3.5" /> Recommandations sous contrôle humain</span>
          </header>

          <section className="grid grid-cols-2 divide-x divide-line overflow-hidden rounded-xl border border-line bg-surface sm:grid-cols-4">
            <Summary icon={Eye} label="Observations" value={String(farm.zones.length + onlineDevices)} detail="signaux suivis" />
            <Summary icon={FlaskConical} label="Pistes du jour" value={String(proposals.length)} detail="solutions à vérifier" />
            <Summary icon={ClipboardCheck} label="Validées" value={String(reviewedIds.length)} detail="revue humaine" tone="success" />
            <Summary icon={LockKeyhole} label="Garde-fous" value="Actifs" detail="politique & impact" tone="warning" />
          </section>

          <section className="rounded-xl border border-line bg-surface p-4">
            <div className="flex items-center gap-2 border-b border-line pb-3"><GitBranch className="h-4 w-4 text-water-400" /><div><h2 className="text-sm font-bold text-ink">Fil de décision · du signal à la consommation maîtrisée</h2><p className="mt-0.5 text-[11px] text-earth-400">Le parcours descend : mesurer la consommation, agir, puis vérifier le résultat réel.</p></div></div>
            <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_260px]">
              <div className="relative pl-10 sm:pl-14"><div className="absolute bottom-5 left-[15px] top-4 w-0.5 bg-gradient-to-b from-alert-400 via-sun-400 to-brand-400 sm:left-[23px]" /><div className="space-y-3"><FlowStep number="1" title="Observer" detail="Capteurs, terrain et marché" tone="alert" /><FlowStep number="2" title="Prévoir" detail="Repérer le poste qui consomme le plus" tone="sun" /><FlowStep number="3" title="Tester" detail="Appliquer une solution sur une petite zone" tone="water" /><FlowStep number="4" title="Mesurer" detail="Comparer avant / après avec les mêmes unités" tone="water" /><FlowStep number="5" title="Apprendre" detail="Garder ce qui réduit réellement la consommation" tone="brand" /></div></div>
              <div className="rounded-xl border border-line bg-raised p-3"><div className="flex items-center justify-between gap-2"><div><p className="text-[10px] font-semibold uppercase tracking-wider text-earth-500">Direction du flux</p><p className="mt-1 text-xs font-bold text-ink">Consommation</p></div><ArrowDown className="h-5 w-5 text-brand-400" /></div><div className="mt-3 space-y-2"><ConsumptionLevel label="Avant QATRA" value="Forte" tone="high" /><ConsumptionLevel label="Après test" value="Comparée" tone="medium" /><ConsumptionLevel label="Cible" value="Réduite" tone="low" /></div><p className="mt-3 text-[10px] leading-4 text-earth-400">Chaque baisse doit être confirmée par l’eau, l’énergie, le rendement et le coût réel.</p></div>
            </div>
          </section>

          <section><div className="mb-2 flex items-center justify-between"><div><h2 className="text-sm font-bold text-ink">Décisions sur le fil</h2><p className="text-[11px] text-earth-400">De la plus forte consommation à l’impact vérifié.</p></div><span className="rounded-full bg-water-500/10 px-2 py-1 text-[10px] font-semibold text-water-400">4 pistes</span></div><div className="space-y-3">{proposals.map((proposal, index) => <div key={proposal.id} className="relative pl-8"><span className="absolute left-0 top-4 flex h-5 w-5 items-center justify-center rounded-full border border-line bg-surface text-[9px] font-bold text-earth-400">{index + 1}</span><ProposalCard proposal={proposal} reviewed={reviewedIds.includes(proposal.id)} onReview={() => markReviewed(proposal.id)} /></div>)}</div></section>

          <section className="grid gap-4 lg:grid-cols-[1.2fr_.8fr]">
            <section className="rounded-xl border border-line bg-surface p-4">
              <div className="flex items-center gap-2 border-b border-line pb-3"><Activity className="h-4 w-4 text-water-400" /><div><h2 className="text-sm font-bold text-ink">Journal de l’impact</h2><p className="mt-0.5 text-[11px] text-earth-400">Ce qui doit être mesuré avant de conclure.</p></div></div>
              <div className="mt-3 overflow-x-auto"><table className="w-full min-w-[520px] text-left text-[10px]"><thead className="border-b border-line text-earth-500"><tr><th className="px-2 py-2">Solution</th><th className="px-2 py-2">Mesure réelle</th><th className="px-2 py-2">Comparaison</th><th className="px-2 py-2">Décision</th></tr></thead><tbody className="divide-y divide-line"><tr><td className="px-2 py-2 font-semibold text-ink">Irrigation ciblée</td><td className="px-2 py-2 text-earth-300">Litres / zone / jour</td><td className="px-2 py-2 text-earth-300">Classique vs QATRA</td><td className="px-2 py-2 text-sun-400">À vérifier</td></tr><tr><td className="px-2 py-2 font-semibold text-ink">Pompage solaire</td><td className="px-2 py-2 text-earth-300">kWh solaire / réseau</td><td className="px-2 py-2 text-earth-300">Avant vs après</td><td className="px-2 py-2 text-brand-400">En suivi</td></tr><tr><td className="px-2 py-2 font-semibold text-ink">Action agronomique</td><td className="px-2 py-2 text-earth-300">Rendement / qualité</td><td className="px-2 py-2 text-earth-300">Parcelle témoin</td><td className="px-2 py-2 text-alert-400">Humain requis</td></tr></tbody></table></div>
            </section>

            <section className="rounded-xl border border-alert-500/30 bg-alert-500/5 p-4">
              <div className="flex items-center gap-2"><LockKeyhole className="h-4 w-4 text-alert-400" /><h2 className="text-sm font-bold text-ink">Garde-fou politique & public</h2></div>
              <p className="mt-3 text-xs leading-5 text-earth-300">Les sorties du système peuvent toucher l’eau, l’énergie, les revenus et les décisions publiques. Elles ne sont donc jamais publiées comme des vérités automatiques.</p>
              <ul className="mt-3 space-y-2 text-[11px] text-earth-300"><li className="flex gap-2"><CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-brand-400" /> Sources et date de chaque information</li><li className="flex gap-2"><CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-brand-400" /> Incertitude et scénario affichés</li><li className="flex gap-2"><CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-brand-400" /> Validation humaine avant généralisation</li><li className="flex gap-2"><CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-brand-400" /> Impact réel archivé après action</li></ul>
              <div className="mt-3 flex items-center gap-2 rounded-lg bg-surface/70 p-2.5 text-[10px] text-earth-400"><UsersRound className="h-3.5 w-3.5 text-water-400" /> Agriculteur + ingénieur + système doivent pouvoir contester une décision.</div>
            </section>
          </section>
        </div>
      </main>
    </AppShell>
  );
}

function Summary({ icon: Icon, label, value, detail, tone = 'default' }: { icon: typeof Eye; label: string; value: string; detail: string; tone?: 'default' | 'success' | 'warning' }) {
  return <div className="min-w-0 px-3 py-2.5 sm:px-4"><div className="flex items-center justify-between gap-2"><span className="truncate text-[11px] text-earth-400">{label}</span><Icon className={cn('h-3.5 w-3.5', tone === 'success' ? 'text-brand-400' : tone === 'warning' ? 'text-sun-400' : 'text-water-400')} /></div><div className="mt-1 flex items-baseline gap-2"><span className="text-lg font-black text-ink">{value}</span><span className="truncate text-[10px] text-earth-500">{detail}</span></div></div>;
}

function FlowStep({ number, title, detail, tone }: { number: string; title: string; detail: string; tone: 'alert' | 'sun' | 'water' | 'brand' }) {
  const color = tone === 'alert' ? 'border-alert-400 bg-alert-500/10 text-alert-400' : tone === 'sun' ? 'border-sun-400 bg-sun-500/10 text-sun-400' : tone === 'brand' ? 'border-brand-400 bg-brand-500/10 text-brand-400' : 'border-water-400 bg-water-500/10 text-water-400';
  return <div className="relative rounded-lg border border-line bg-raised px-3 py-2.5"><span className={cn('absolute -left-[2.05rem] top-2.5 flex h-6 w-6 items-center justify-center rounded-full border text-[10px] font-black sm:-left-[2.45rem]', color)}>{number}</span><div className="flex items-center justify-between gap-3"><p className="text-xs font-bold text-ink">{title}</p><span className="text-[10px] font-semibold text-earth-500">étape {number}/5</span></div><p className="mt-1 text-[10px] leading-4 text-earth-400">{detail}</p></div>;
}

function ConsumptionLevel({ label, value, tone }: { label: string; value: string; tone: 'high' | 'medium' | 'low' }) {
  const color = tone === 'high' ? 'bg-alert-400' : tone === 'medium' ? 'bg-sun-400' : 'bg-brand-400';
  const width = tone === 'high' ? 'w-full' : tone === 'medium' ? 'w-2/3' : 'w-1/3';
  return <div><div className="flex justify-between text-[10px]"><span className="text-earth-400">{label}</span><span className="font-semibold text-ink">{value}</span></div><div className="mt-1 h-1.5 rounded-full bg-surface"><div className={cn('h-full rounded-full', color, width)} /></div></div>;
}

function ProposalCard({ proposal, reviewed, onReview }: { proposal: Proposal; reviewed: boolean; onReview: () => void }) {
  const Icon = proposal.icon;
  const style = DOMAIN_STYLE[proposal.tone];
  return <article className={cn('rounded-xl border p-4', style.border, style.bg)}><div className="flex items-start justify-between gap-3"><div className="flex items-center gap-2.5"><span className={cn('flex h-9 w-9 items-center justify-center rounded-lg', style.badge)}><Icon className="h-4 w-4" /></span><div><p className="text-[10px] font-semibold uppercase tracking-wider text-earth-500">{proposal.domain}</p><h3 className="mt-0.5 text-sm font-bold text-ink">{proposal.title}</h3></div></div><span className={cn('shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold', proposal.status === 'En test' ? 'bg-sun-500/10 text-sun-400' : proposal.status === 'Mesuré' ? 'bg-brand-500/10 text-brand-400' : 'bg-earth-800 text-earth-300')}>{reviewed ? 'Revue terminée' : proposal.status}</span></div><div className="mt-3 grid gap-2 sm:grid-cols-2"><div className="rounded-lg bg-surface/70 p-2.5"><p className="text-[10px] text-earth-500">Prédiction</p><p className="mt-1 text-[11px] font-semibold text-ink">{proposal.prediction}</p></div><div className="rounded-lg bg-surface/70 p-2.5"><p className="text-[10px] text-earth-500">Checkpoint obligatoire</p><p className="mt-1 text-[11px] text-earth-300">{proposal.checkpoint}</p></div></div><div className="mt-3 flex flex-wrap gap-1.5"><span className="text-[10px] font-semibold text-earth-500">Sources :</span>{proposal.sources.map((source) => <span key={source} className="rounded bg-surface/70 px-1.5 py-1 text-[9px] text-earth-400">{source}</span>)}</div><div className="mt-3 flex items-center justify-between gap-2 border-t border-line/70 pt-3"><p className="text-[10px] text-earth-400"><strong className="text-ink">Impact à mesurer :</strong> {proposal.impact}</p><button onClick={onReview} disabled={reviewed} className={cn('shrink-0 rounded-lg px-2.5 py-1.5 text-[10px] font-semibold', reviewed ? 'bg-brand-500/10 text-brand-400' : 'bg-accent text-on-accent hover:bg-accent-hover')}>{reviewed ? 'Validé' : 'Mettre en revue'}</button></div></article>;
}
