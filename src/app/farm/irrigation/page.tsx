'use client';

import { useMemo, useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import {
  Activity,
  AlertTriangle,
  BatteryCharging,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Droplets,
  Gauge,
  GitBranch,
  Lightbulb,
  LockKeyhole,
  Play,
  ShieldAlert,
  SlidersHorizontal,
  Square,
  Sun,
  ThermometerSun,
  Waves,
  Zap,
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { DEMO_DEVICES, DEMO_ENERGY_TELEMETRY } from '@/lib/mockData';
import { useFarmStore } from '@/stores/useFarmStore';
import { cn, formatNumber } from '@/lib/utils';
import type { FarmZone } from '@/types';

type AgentStatus = 'ready' | 'warning' | 'critical';

type Agent = {
  id: string;
  name: string;
  role: string;
  icon: LucideIcon;
  status: AgentStatus;
  focus: string;
  data: string[];
  checkpoints: string[];
  decision: string;
  solution: string;
  dependencies: string[];
  sources: string[];
};

const STATUS_LABEL: Record<AgentStatus, string> = {
  ready: 'Prêt',
  warning: 'À surveiller',
  critical: 'Action requise',
};

const STATUS_CLASS: Record<AgentStatus, string> = {
  ready: 'bg-brand-500/10 text-brand-400',
  warning: 'bg-sun-500/10 text-sun-400',
  critical: 'bg-alert-500/10 text-alert-400',
};

export default function IrrigationPage() {
  const { farm, startIrrigation, stopIrrigation, emergencyStopActive, toggleEmergencyStop } = useFarmStore();
  const [autoMode, setAutoMode] = useState(true);
  const [maxRuntimeMinutes, setMaxRuntimeMinutes] = useState(60);

  const criticalZones = farm.zones.filter((zone) => zone.status === 'critical');
  const warningZones = farm.zones.filter((zone) => zone.status === 'warning');
  const activeZones = farm.zones.filter((zone) => zone.irrigationStatus === 'active');
  const pump = DEMO_DEVICES.find((device) => device.type === 'irrigation_pump');
  const flowRate = Number(pump?.readings.flowRateM3H ?? 0);
  const pressure = Number(pump?.readings.waterPressureBar ?? 0);
  const soilAgentStatus: AgentStatus = criticalZones.length > 0 ? 'critical' : warningZones.length > 0 ? 'warning' : 'ready';
  const safetyStatus: AgentStatus = emergencyStopActive ? 'critical' : 'ready';

  const agents = useMemo<Agent[]>(() => [
    {
      id: 'soil',
      name: 'Agent Sol & Culture',
      role: 'Détecte le besoin réel en eau',
      icon: Droplets,
      status: soilAgentStatus,
      focus: 'Humidité, seuils de culture et stress hydrique par zone.',
      data: [
        criticalZones.length + ' zone(s) sous le seuil critique',
        'Minimum actuel : ' + (criticalZones[0]?.soilMoisturePercent ?? 38) + '%',
        'Seuil culture : ' + (criticalZones[0]?.targetMoistureMin ?? 35) + '%',
      ],
      checkpoints: ['Capteur répondant', 'Mesure comparée au seuil', 'Stress confirmé par la culture'],
      decision: criticalZones.length > 0 ? 'Prioriser les zones critiques' : warningZones.length > 0 ? 'Préparer un cycle ciblé' : 'Aucun arrosage nécessaire',
      solution: criticalZones.length > 0 ? 'Proposer 45 min en goutte-à-goutte sur la zone la plus sèche.' : 'Maintenir la surveillance automatique.',
      dependencies: ['Agent Orchestrateur', 'Agent Solaire'],
      sources: ['Sondes ESP32 / LoRa', 'Fiche culture & seuils', 'NDVI Sentinel-2'],
    },
    {
      id: 'solar',
      name: 'Agent Solaire & Météo',
      role: 'Choisit le meilleur moment',
      icon: Sun,
      status: DEMO_ENERGY_TELEMETRY.solarProductionKw >= DEMO_ENERGY_TELEMETRY.pumpConsumptionKw ? 'ready' : 'warning',
      focus: 'Production photovoltaïque, demande pompe et conditions météo.',
      data: [
        'Production : ' + formatNumber(DEMO_ENERGY_TELEMETRY.solarProductionKw) + ' kW',
        'Demande pompe : ' + formatNumber(DEMO_ENERGY_TELEMETRY.pumpConsumptionKw) + ' kW',
        'Batterie : ' + DEMO_ENERGY_TELEMETRY.batterySoCPercent + '%',
      ],
      checkpoints: ['Solaire supérieur à la demande', 'Batterie au-dessus de 30 %', 'Réseau disponible en secours'],
      decision: DEMO_ENERGY_TELEMETRY.solarProductionKw >= DEMO_ENERGY_TELEMETRY.pumpConsumptionKw ? 'Fenêtre solaire favorable' : 'Reporter ou réduire le cycle',
      solution: 'Autoriser le cycle pendant la production solaire pour éviter le recours réseau.',
      dependencies: ['Agent Sol & Culture', 'Agent Hydraulique'],
      sources: ['Onduleur PV', 'BMS batterie', 'Télémetrie énergie'],
    },
    {
      id: 'hydraulic',
      name: 'Agent Hydraulique',
      role: 'Vérifie que l’eau peut circuler',
      icon: Waves,
      status: flowRate > 0 && pressure > 2 ? 'ready' : 'warning',
      focus: 'Réservoir, pompe, pression, débit et vannes.',
      data: [
        'Réservoir : ' + farm.currentTankLevelPercent + '%',
        'Débit : ' + formatNumber(flowRate, 1) + ' m³/h',
        'Pression : ' + formatNumber(pressure, 1) + ' bar',
      ],
      checkpoints: ['Réservoir suffisant', 'Pression dans la plage', 'Débit confirmé après ouverture'],
      decision: farm.currentTankLevelPercent > 20 && pressure > 2 ? 'Infrastructure disponible' : 'Bloquer le cycle et inspecter',
      solution: 'Ouvrir une seule vanne à la fois puis contrôler le débit réel.',
      dependencies: ['Agent Sol & Culture', 'Agent Sécurité'],
      sources: ['Capteur niveau réservoir', 'Pompe submersible', 'Débitmètre / pressostat'],
    },
    {
      id: 'safety',
      name: 'Agent Sécurité',
      role: 'Bloque les actions dangereuses',
      icon: ShieldAlert,
      status: safetyStatus,
      focus: 'Arrêt d’urgence, watchdog, durée maximale et incohérences.',
      data: [
        'Arrêt d’urgence : ' + (emergencyStopActive ? 'ACTIF' : 'inactif'),
        'Durée maximale : ' + maxRuntimeMinutes + ' min',
        'Zones en fonctionnement : ' + activeZones.length,
      ],
      checkpoints: ['Arrêt d’urgence vérifié', 'Watchdog configuré', 'Une action à la fois'],
      decision: emergencyStopActive ? 'Interdire toute ouverture de vanne' : 'Autoriser sous surveillance',
      solution: emergencyStopActive ? 'Attendre le déverrouillage opérateur.' : 'Couper automatiquement si le débit ou la durée devient anormal.',
      dependencies: ['Agent Hydraulique', 'Agent Orchestrateur'],
      sources: ['État arrêt d’urgence', 'Watchdog local', 'Journal des opérations'],
    },
    {
      id: 'orchestrator',
      name: 'Agent Orchestrateur',
      role: 'Assemble les preuves et décide',
      icon: GitBranch,
      status: emergencyStopActive ? 'critical' : criticalZones.length > 0 ? 'warning' : 'ready',
      focus: 'Arbitrage entre eau, énergie, matériel et sécurité.',
      data: [
        agentsSummary(criticalZones.length, warningZones.length, activeZones.length),
        'Mode : ' + (autoMode ? 'automatique' : 'manuel'),
        'Décisions à valider : ' + (criticalZones.length + warningZones.length),
      ],
      checkpoints: ['Minimum deux sources concordantes', 'Aucune règle de sécurité violée', 'Action expliquée et traçable'],
      decision: emergencyStopActive ? 'Aucune action automatique' : criticalZones.length > 0 ? 'Lancer une irrigation prioritaire' : 'Continuer la surveillance',
      solution: emergencyStopActive ? 'Notifier l’opérateur et conserver les données.' : 'Combiner sol + solaire + hydraulique avant d’ouvrir la vanne.',
      dependencies: ['Tous les agents'],
      sources: ['États des agents', 'Historique des décisions', 'Règles QATRA Mottainai'],
    },
  ], [activeZones.length, autoMode, criticalZones, emergencyStopActive, farm.currentTankLevelPercent, flowRate, maxRuntimeMinutes, pressure, soilAgentStatus, warningZones.length]);

  return (
    <AppShell>
      <main className="h-full overflow-y-auto px-4 pb-8 pt-4 sm:px-5 lg:px-6">
        <div className="mx-auto max-w-[1500px] space-y-4">
          <header className="flex flex-col gap-3 border-b border-line pb-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-brand-400"><Droplets className="h-3.5 w-3.5" /> Gestion de l’irrigation</p>
              <h1 className="mt-1 text-xl font-black tracking-tight text-ink sm:text-2xl">Décisions et opérations</h1>
              <p className="mt-1 text-xs text-earth-400">Priorités des zones, état des agents et actions disponibles.</p>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => setAutoMode((current) => !current)} className={cn('inline-flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-semibold', autoMode ? 'bg-brand-500/15 text-brand-400' : 'bg-earth-800 text-earth-300')}><Activity className="h-3.5 w-3.5" /> {autoMode ? 'Mode automatique' : 'Mode manuel'}</button>
              <button onClick={toggleEmergencyStop} className={cn('inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-bold', emergencyStopActive ? 'border-alert-400 bg-alert-600 text-on-accent' : 'border-alert-500/40 bg-alert-500/10 text-alert-400')}><ShieldAlert className="h-3.5 w-3.5" /> {emergencyStopActive ? 'Déverrouiller' : 'Arrêt urgence'}</button>
            </div>
          </header>

          {false && <section className="grid grid-cols-2 divide-x divide-line overflow-hidden rounded-xl border border-line bg-surface sm:grid-cols-4">
            <Summary label="Agents actifs" value={String(agents.length)} detail="décision coordonnée" icon={GitBranch} />
            <Summary label="Zones critiques" value={String(criticalZones.length)} detail="attention immédiate" icon={AlertTriangle} tone={criticalZones.length ? 'critical' : 'default'} />
            <Summary label="Cycles actifs" value={String(activeZones.length)} detail="opérations en cours" icon={Droplets} tone="water" />
            <Summary label="Sources utilisées" value={String(new Set(agents.flatMap((agent) => agent.sources)).size)} detail="données traçables" icon={CheckCircle2} />
          </section>}

          {false && <section className="rounded-xl border border-line bg-surface p-4">
            <div className="flex items-center justify-between border-b border-line pb-3">
              <div><h2 className="text-sm font-bold text-ink">Chaîne de décision</h2><p className="mt-0.5 text-[11px] text-earth-400">Les agents travaillent ensemble avant toute ouverture de vanne.</p></div>
              <span className="hidden items-center gap-1.5 text-[11px] text-earth-400 sm:flex"><Lightbulb className="h-3.5 w-3.5 text-sun-400" /> checkpoints obligatoires</span>
            </div>
            <div className="mt-3 grid gap-2 md:grid-cols-5">
              {agents.map((agent, index) => <AgentLink key={agent.id} agent={agent} index={index} />)}
            </div>
          </section>}

          <AgentDecisionTable agents={agents} />

          {false && <section className="grid gap-4 xl:grid-cols-2">
            {agents.map((agent) => <AgentCard key={agent.id} agent={agent} />)}
          </section>}

          <section className="overflow-hidden rounded-xl border border-line bg-surface">
            <div className="flex flex-col gap-2 border-b border-line px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
              <div><h2 className="text-sm font-bold text-ink">Décision par zone</h2><p className="mt-0.5 text-[11px] text-earth-400">Résultat coordonné des agents, avec opération disponible immédiatement.</p></div>
              <div className="flex items-center gap-2 text-[11px] text-earth-400"><Clock3 className="h-3.5 w-3.5 text-water-400" /> Watchdog <input type="number" value={maxRuntimeMinutes} onChange={(event) => setMaxRuntimeMinutes(Number(event.target.value))} className="w-14 rounded border border-line bg-sunken px-1.5 py-1 text-center text-ink" /> min</div>
            </div>
            <div className="divide-y divide-line">
              {farm.zones.map((zone) => <ZoneDecision key={zone.id} zone={zone} emergencyStopActive={emergencyStopActive} onStart={() => startIrrigation(zone.id)} onStop={() => stopIrrigation(zone.id)} />)}
            </div>
          </section>
        </div>
      </main>
    </AppShell>
  );
}

function agentsSummary(critical: number, warning: number, active: number) {
  return critical + ' critique(s) · ' + warning + ' à surveiller · ' + active + ' cycle(s) actif(s)';
}

function Summary({ label, value, detail, icon: Icon, tone = 'default' }: { label: string; value: string; detail: string; icon: LucideIcon; tone?: 'default' | 'critical' | 'water' }) {
  return <div className="min-w-0 px-3 py-2.5 sm:px-4"><div className="flex items-center justify-between gap-2"><span className="truncate text-[11px] text-earth-400">{label}</span><Icon className={cn('h-3.5 w-3.5', tone === 'critical' ? 'text-alert-400' : tone === 'water' ? 'text-water-400' : 'text-brand-400')} /></div><div className="mt-1 flex items-baseline gap-2"><span className="text-lg font-black text-ink">{value}</span><span className="truncate text-[10px] text-earth-500">{detail}</span></div></div>;
}

function AgentLink({ agent, index }: { agent: Agent; index: number }) {
  const Icon = agent.icon;
  return <div className="flex items-center gap-2 rounded-lg bg-raised px-2.5 py-2"><span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-water-500/10 text-water-400"><Icon className="h-3.5 w-3.5" /></span><div className="min-w-0"><p className="truncate text-[10px] font-semibold text-ink">{index + 1}. {agent.name.replace('Agent ', '')}</p><p className="truncate text-[9px] text-earth-500">{STATUS_LABEL[agent.status]}</p></div>{index < 4 && <ChevronRight className="ml-auto hidden h-3 w-3 shrink-0 text-earth-500 md:block" />}</div>;
}

function AgentDecisionTable({ agents }: { agents: Agent[] }) {
  return (
    <section className="overflow-hidden rounded-xl border border-line bg-surface">
      <div className="border-b border-line px-4 py-3">
        <h2 className="text-sm font-bold text-ink">Décisions d’irrigation · vue unique</h2>
        <p className="mt-0.5 text-[11px] text-earth-400">Chaque agent parle dans le même tableau, avec sa priorité, ses preuves et son action.</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1050px] text-left text-[10px]">
          <thead className="border-b border-line bg-raised text-earth-500">
            <tr>
              <th className="px-3 py-2.5">Agent / priorité</th>
              <th className="px-3 py-2.5">Service</th>
              <th className="px-3 py-2.5">État</th>
              <th className="px-3 py-2.5">Données observées</th>
              <th className="px-3 py-2.5">Décision & solution</th>
              <th className="px-3 py-2.5">Checkpoint</th>
              <th className="px-3 py-2.5">Sources</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {agents.map((agent, index) => {
              const Icon = agent.icon;
              return (
              <tr key={agent.id} className={cn('align-top transition-colors hover:bg-raised/70', agent.status === 'critical' && 'bg-alert-500/5')}>
                <td className="px-3 py-3">
                  <div className="flex items-center gap-2">
                    <span className={cn('flex h-7 w-7 items-center justify-center rounded-lg', agent.status === 'critical' ? 'bg-alert-500/10 text-alert-400' : agent.status === 'warning' ? 'bg-sun-500/10 text-sun-400' : 'bg-water-500/10 text-water-400')}><Icon className="h-3.5 w-3.5" /></span>
                    <div><p className="font-bold text-ink">{index + 1}. {agent.name.replace('Agent ', '')}</p><p className="mt-0.5 text-[9px] text-earth-500">priorité {agent.status === 'critical' ? '1' : agent.status === 'warning' ? '2' : '3'}</p></div>
                  </div>
                </td>
                <td className="px-3 py-3 text-earth-300">{agent.role}<p className="mt-1 text-[9px] text-earth-500">{agent.focus}</p></td>
                <td className="px-3 py-3"><span className={cn('rounded-full px-2 py-1 font-semibold', STATUS_CLASS[agent.status])}>{STATUS_LABEL[agent.status]}</span></td>
                <td className="px-3 py-3 text-earth-300"><ul className="space-y-1">{agent.data.map((item) => <li key={item}>• {item}</li>)}</ul></td>
                <td className="max-w-[220px] px-3 py-3 text-earth-300"><p className="font-semibold text-ink">{agent.decision}</p><p className="mt-1">{agent.solution}</p></td>
                <td className="px-3 py-3 text-earth-300"><ul className="space-y-1">{agent.checkpoints.map((item) => <li key={item}>✓ {item}</li>)}</ul></td>
                <td className="px-3 py-3 text-brand-400"><div className="flex max-w-[160px] flex-wrap gap-1">{agent.sources.map((source) => <span key={source} className="rounded bg-brand-500/10 px-1.5 py-1 text-[9px]">{source}</span>)}</div></td>
              </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function AgentCard({ agent }: { agent: Agent }) {
  const Icon = agent.icon;
  return (
    <article className={cn('rounded-xl border bg-surface p-4', agent.status === 'critical' ? 'border-alert-500/50' : agent.status === 'warning' ? 'border-sun-500/40' : 'border-line')}>
      <div className="flex items-start justify-between gap-3 border-b border-line pb-3">
        <div className="flex min-w-0 items-center gap-2.5"><span className={cn('flex h-9 w-9 shrink-0 items-center justify-center rounded-lg', agent.status === 'critical' ? 'bg-alert-500/10 text-alert-400' : agent.status === 'warning' ? 'bg-sun-500/10 text-sun-400' : 'bg-water-500/10 text-water-400')}><Icon className="h-4 w-4" /></span><div className="min-w-0"><h3 className="truncate text-sm font-bold text-ink">{agent.name}</h3><p className="mt-0.5 text-[11px] text-earth-400">{agent.role}</p></div></div>
        <span className={cn('shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold', STATUS_CLASS[agent.status])}>{STATUS_LABEL[agent.status]}</span>
      </div>
      <p className="mt-3 text-[11px] leading-4 text-earth-300">{agent.focus}</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div><p className="mb-1.5 text-[10px] font-bold uppercase tracking-wider text-earth-500">Données observées</p><ul className="space-y-1">{agent.data.map((item) => <li key={item} className="flex gap-1.5 text-[10px] text-earth-300"><span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-water-400" />{item}</li>)}</ul></div>
        <div><p className="mb-1.5 text-[10px] font-bold uppercase tracking-wider text-earth-500">Checkpoints</p><ul className="space-y-1">{agent.checkpoints.map((item) => <li key={item} className="flex gap-1.5 text-[10px] text-earth-300"><CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0 text-brand-400" />{item}</li>)}</ul></div>
      </div>
      <div className={cn('mt-3 rounded-lg p-2.5', agent.status === 'critical' ? 'bg-alert-500/10' : agent.status === 'warning' ? 'bg-sun-500/10' : 'bg-water-500/5')}><p className="text-[10px] font-bold uppercase tracking-wider text-earth-500">Décision</p><p className="mt-1 text-xs font-bold text-ink">{agent.decision}</p><p className="mt-1 text-[10px] leading-4 text-earth-300">Solution : {agent.solution}</p></div>
      <div className="mt-3 flex flex-wrap items-center gap-1.5"><span className="text-[10px] font-semibold text-earth-500">Dépend de :</span>{agent.dependencies.map((dependency) => <span key={dependency} className="rounded bg-earth-800 px-1.5 py-1 text-[9px] text-earth-300">{dependency}</span>)}</div>
      <div className="mt-2 flex flex-wrap items-center gap-1.5 border-t border-line pt-2"><span className="text-[10px] font-semibold text-earth-500">Sources :</span>{agent.sources.map((source) => <span key={source} className="rounded bg-brand-500/10 px-1.5 py-1 text-[9px] text-brand-400">{source}</span>)}</div>
    </article>
  );
}

function ZoneDecision({ zone, emergencyStopActive, onStart, onStop }: { zone: FarmZone; emergencyStopActive: boolean; onStart: () => void; onStop: () => void }) {
  const active = zone.irrigationStatus === 'active';
  const critical = zone.status === 'critical';
  const decision = active ? 'Cycle en cours' : critical ? 'Arroser maintenant' : zone.status === 'warning' ? 'Arrosage prioritaire' : 'Surveiller';
  return <div className="grid gap-3 px-4 py-3 lg:grid-cols-[minmax(190px,1.2fr)_100px_minmax(150px,1fr)_auto] lg:items-center"><div><div className="flex items-center gap-2"><span className={cn('h-2 w-2 rounded-full', critical ? 'bg-alert-500' : zone.status === 'warning' ? 'bg-sun-500' : active ? 'bg-water-500' : 'bg-brand-500')} /><p className="truncate text-xs font-bold text-ink">{zone.name}</p></div><p className="mt-1 pl-4 text-[10px] text-earth-500">{zone.cropType} · seuil {zone.targetMoistureMin}–{zone.targetMoistureMax}%</p></div><div><p className={cn('text-lg font-black', critical ? 'text-alert-400' : 'text-ink')}>{zone.soilMoisturePercent}%</p><p className="text-[10px] text-earth-500">humidité</p></div><div><p className={cn('text-xs font-semibold', critical ? 'text-alert-400' : zone.status === 'warning' ? 'text-sun-400' : 'text-water-400')}>{decision}</p><p className="mt-1 text-[10px] text-earth-500">{formatNumber(zone.dailyWaterLiters)} L / jour · {zone.irrigationMethod}</p></div><div className="flex justify-start lg:justify-end">{active ? <button onClick={onStop} className="inline-flex items-center gap-1.5 rounded-lg border border-alert-500/30 px-2.5 py-1.5 text-[10px] font-semibold text-alert-400"><Square className="h-3 w-3 fill-current" /> Arrêter</button> : <button disabled={emergencyStopActive} onClick={onStart} className={cn('inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[10px] font-semibold', emergencyStopActive ? 'cursor-not-allowed bg-earth-800 text-earth-500' : critical ? 'bg-alert-600 text-on-accent hover:bg-alert-500' : 'bg-accent text-on-accent hover:bg-accent-hover')}><Play className="h-3 w-3 fill-current" /> Ouvrir vanne</button>}</div></div>;
}
