'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import type { DragEvent } from 'react';
import type { LucideIcon } from 'lucide-react';
import {
  BatteryCharging,
  Bell,
  Cable,
  ArrowRight,
  Clock3,
  Database,
  Droplets,
  Gauge,
  Move,
  Pause,
  Play,
  Plus,
  Radio,
  RotateCcw,
  ShieldAlert,
  Sun,
  Thermometer,
  TriangleAlert,
  Waves,
  WifiOff,
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { DEMO_DEVICES } from '@/lib/mockData';
import { fetchDevices } from '@/lib/qatra/client';
import { useFarmStore } from '@/stores/useFarmStore';
import type { Device, DeviceType, FarmZone } from '@/types';
import { cn } from '@/lib/utils';

type MaterialType = DeviceType | 'irrigation_valve' | 'weather_station' | 'water_flow';

type Material = {
  type: MaterialType;
  label: string;
  shortLabel: string;
  icon: LucideIcon;
  tone: string;
  defaultPayload: string;
};

type CanvasNode = {
  id: string;
  materialType: MaterialType;
  label: string;
  x: number;
  y: number;
  status: 'online' | 'warning' | 'alert' | 'ready';
  device?: Device;
};

type Connection = {
  id: string;
  from: string;
  to: string;
  kind: 'data' | 'power' | 'water';
  label: string;
  topic: string;
  payload: string;
  frequency: string;
};

const MATERIALS: Material[] = [
  { type: 'soil_sensor', label: 'Capteur sol', shortLabel: 'Sol', icon: Droplets, tone: 'text-water-400 bg-water-500/10', defaultPayload: '{"soilMoisture":38.2,"temperature":21.4}' },
  { type: 'esp32_gateway', label: 'Passerelle ESP32', shortLabel: 'Gateway', icon: Radio, tone: 'text-brand-400 bg-brand-500/10', defaultPayload: '{"device":"gateway","signal":-58}' },
  { type: 'irrigation_pump', label: 'Pompe solaire', shortLabel: 'Pompe', icon: Waves, tone: 'text-sun-400 bg-sun-500/10', defaultPayload: '{"flowRate":26.4,"power":6.8}' },
  { type: 'irrigation_valve', label: 'Vanne irrigation', shortLabel: 'Vanne', icon: Droplets, tone: 'text-water-300 bg-water-500/10', defaultPayload: '{"state":"open","durationMin":45}' },
  { type: 'solar_inverter', label: 'Onduleur solaire', shortLabel: 'Solaire', icon: Sun, tone: 'text-sun-400 bg-sun-500/10', defaultPayload: '{"productionKw":14.8,"efficiency":97.4}' },
  { type: 'battery_bms', label: 'Batterie BMS', shortLabel: 'Batterie', icon: BatteryCharging, tone: 'text-brand-300 bg-brand-500/10', defaultPayload: '{"soc":89,"voltage":53.2}' },
  { type: 'water_flow', label: 'Débitmètre', shortLabel: 'Débit', icon: Gauge, tone: 'text-water-400 bg-water-500/10', defaultPayload: '{"flowRateM3H":26.4,"pressureBar":3.8}' },
  { type: 'weather_station', label: 'Station météo', shortLabel: 'Météo', icon: Thermometer, tone: 'text-sun-300 bg-sun-500/10', defaultPayload: '{"temperature":28.5,"rainProbability":12}' },
];

const INITIAL_NODES: CanvasNode[] = [
  { id: 'dev-soil-02', materialType: 'soil_sensor', label: 'Sonde sol B2', x: 45, y: 80, status: 'warning', device: DEMO_DEVICES.find((device) => device.id === 'dev-soil-02') },
  { id: 'dev-soil-04', materialType: 'soil_sensor', label: 'Sonde sol D4', x: 45, y: 325, status: 'alert', device: DEMO_DEVICES.find((device) => device.id === 'dev-soil-04') },
  { id: 'dev-gw-01', materialType: 'esp32_gateway', label: 'Gateway centrale', x: 340, y: 205, status: 'online', device: DEMO_DEVICES.find((device) => device.id === 'dev-gw-01') },
  { id: 'dev-solar-01', materialType: 'solar_inverter', label: 'Onduleur PV', x: 620, y: 55, status: 'online', device: DEMO_DEVICES.find((device) => device.id === 'dev-solar-01') },
  { id: 'dev-bms-01', materialType: 'battery_bms', label: 'Batterie', x: 770, y: 205, status: 'online', device: DEMO_DEVICES.find((device) => device.id === 'dev-bms-01') },
  { id: 'dev-pump-01', materialType: 'irrigation_pump', label: 'Pompe solaire', x: 620, y: 350, status: 'online', device: DEMO_DEVICES.find((device) => device.id === 'dev-pump-01') },
  { id: 'valve-zone-b', materialType: 'irrigation_valve', label: 'Vanne Zone B', x: 345, y: 405, status: 'ready' },
];

const CONNECTIONS: Connection[] = [
  { id: 'soil-gateway', from: 'dev-soil-02', to: 'dev-gw-01', kind: 'data', label: 'Mesure humidité', topic: 'qatra/zone-b/soil', payload: '{"moisture":22,"threshold":35}', frequency: 'toutes les 60 s' },
  { id: 'soil-alert', from: 'dev-soil-04', to: 'dev-gw-01', kind: 'data', label: 'Alerte stress', topic: 'qatra/zone-d/alert', payload: '{"moisture":14,"severity":"critical"}', frequency: 'sur événement' },
  { id: 'gateway-pump', from: 'dev-gw-01', to: 'dev-pump-01', kind: 'data', label: 'Commande irrigation', topic: 'qatra/pump/command', payload: '{"action":"start","durationMin":45}', frequency: 'sur décision' },
  { id: 'pump-valve', from: 'dev-pump-01', to: 'valve-zone-b', kind: 'water', label: 'Pression / débit', topic: 'qatra/zone-b/flow', payload: '{"flowRate":26.4,"pressure":3.8}', frequency: 'toutes les 5 s' },
  { id: 'solar-pump', from: 'dev-solar-01', to: 'dev-pump-01', kind: 'power', label: 'Énergie disponible', topic: 'qatra/energy/available', payload: '{"solarKw":14.8,"pumpDemandKw":6.8}', frequency: 'toutes les 10 s' },
  { id: 'solar-battery', from: 'dev-solar-01', to: 'dev-bms-01', kind: 'power', label: 'Charge batterie', topic: 'qatra/battery/telemetry', payload: '{"soc":89,"chargeKw":4.5}', frequency: 'toutes les 10 s' },
  { id: 'gateway-solar', from: 'dev-gw-01', to: 'dev-solar-01', kind: 'data', label: 'État énergie', topic: 'qatra/energy/status', payload: '{"grid":"available","mode":"self-consumption"}', frequency: 'toutes les 30 s' },
];

const STATUS_LABEL = { online: 'En ligne', warning: 'Attention', alert: 'Alerte', ready: 'Prêt' };
const CONNECTION_STYLE = {
  data: { color: '#2b8ca2', label: 'Données' },
  power: { color: '#c88a29', label: 'Énergie' },
  water: { color: '#247eaa', label: 'Eau / hydraulique' },
};

function connectionPriority(connection: Connection): 1 | 2 | 3 {
  if (connection.id.includes('alert') || connection.id.includes('gateway-pump') || connection.id.includes('solar-pump') || connection.id.includes('pump-valve')) return 1;
  if (connection.id.includes('soil') || connection.id.includes('battery') || connection.id.includes('custom')) return 2;
  return 3;
}

export default function DevicesPage() {
  const [liveDevices, setLiveDevices] = useState(DEMO_DEVICES);
  const [nodes, setNodes] = useState<CanvasNode[]>(INITIAL_NODES);
  const [connections, setConnections] = useState<Connection[]>(CONNECTIONS);
  const [isSimulating, setIsSimulating] = useState(true);
  const [activeEvent, setActiveEvent] = useState(0);
  const [cableMode, setCableMode] = useState(false);
  const [cableStartId, setCableStartId] = useState<string | null>(null);
  const [selectedConnectionId, setSelectedConnectionId] = useState<string | null>(CONNECTIONS[0].id);

  const nodeById = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);
  const onlineCount = nodes.filter((node) => node.status === 'online').length;
  const { farm, emergencyStopActive } = useFarmStore();
  const criticalZones = farm.zones.filter((zone) => zone.status === 'critical');
  const attentionDevices = liveDevices.filter((device) => device.status === 'alert' || device.status === 'warning' || device.status === 'offline');

  useEffect(() => {
    void fetchDevices().then((remoteDevices) => {
      const merged = DEMO_DEVICES.map((demo) => {
        const remote = remoteDevices.find((item) => item.kind === demo.type && (!item.zone_id || item.zone_id === demo.zoneId));
        return remote ? { ...demo, id: remote.id, status: remote.status as typeof demo.status } : demo;
      });
      setLiveDevices(merged);
    }).catch(() => {
      // Keep the existing demo workflow visible when the API is unavailable.
    });
  }, []);

  useEffect(() => {
    if (!isSimulating) return;
    const interval = setInterval(() => {
      setActiveEvent((current) => {
        const next = (current + 1) % connections.length;
        return next;
      });
    }, 2600);
    return () => clearInterval(interval);
  }, [isSimulating, connections.length]);

  const resetSimulation = () => {
    setNodes(INITIAL_NODES);
    setConnections(CONNECTIONS);
    setActiveEvent(0);
    setIsSimulating(true);
    setCableMode(false);
    setCableStartId(null);
    setSelectedConnectionId(CONNECTIONS[0].id);
  };

  const handleNodeClick = (nodeId: string) => {
    if (!cableMode) {
      const related = connections.find((connection) => connection.from === nodeId || connection.to === nodeId);
      if (related) setSelectedConnectionId(related.id);
      return;
    }
    if (!cableStartId) {
      setCableStartId(nodeId);
      return;
    }
    if (cableStartId === nodeId) return;
    const exists = connections.some((connection) => connection.from === cableStartId && connection.to === nodeId);
    if (!exists) {
      const source = nodeById.get(cableStartId);
      const target = nodeById.get(nodeId);
      setConnections((current) => [...current, {
        id: 'custom-' + Date.now(),
        from: cableStartId,
        to: nodeId,
        kind: 'data',
        label: 'Câble personnalisé',
        topic: 'qatra/custom/' + (source?.label ?? 'source').toLowerCase().replaceAll(' ', '-'),
        payload: '{"link":"custom","status":"connected"}',
        frequency: 'sur événement',
      }]);
    }
    setCableStartId(null);
    setCableMode(false);
  };

  const selectedConnection = connections.find((connection) => connection.id === selectedConnectionId) ?? null;

  const addMaterial = (materialType: MaterialType, x: number, y: number) => {
    const material = MATERIALS.find((item) => item.type === materialType);
    if (!material) return;
    const id = materialType + '-' + Date.now();
    setNodes((current) => [...current, {
      id,
      materialType,
      label: material.label,
      x: Math.max(10, Math.min(790, x - 75)),
      y: Math.max(10, Math.min(435, y - 38)),
      status: 'ready',
    }]);
  };

  const handleCanvasDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const rect = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * 900;
    const y = ((event.clientY - rect.top) / rect.height) * 520;
    const nodeId = event.dataTransfer.getData('nodeId');
    const materialType = event.dataTransfer.getData('materialType') as MaterialType;

    if (nodeId) {
      setNodes((current) => current.map((node) => node.id === nodeId ? {
        ...node,
        x: Math.max(10, Math.min(790, x - 75)),
        y: Math.max(10, Math.min(435, y - 38)),
      } : node));
    } else if (materialType) {
      addMaterial(materialType, x, y);
    }
  };

  return (
    <AppShell>
      <div className="space-y-4">
        <header className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-water-400">Architecture IoT & simulation</p>
            <h1 className="mt-1 text-2xl font-black tracking-tight text-ink">Flux des appareils</h1>
            <p className="mt-1 max-w-3xl text-sm text-earth-300">Placez les équipements, observez les échanges et comprenez le chemin d’une décision jusqu’à l’action sur le terrain.</p>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setIsSimulating((current) => !current)} className={cn('inline-flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-semibold transition-colors', isSimulating ? 'bg-brand-500/15 text-brand-400' : 'bg-earth-800 text-earth-300')}>
              {isSimulating ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
              {isSimulating ? 'Simulation active' : 'Simulation en pause'}
            </button>
            <button onClick={resetSimulation} className="inline-flex items-center gap-2 rounded-xl border border-line px-3 py-2 text-xs font-semibold text-earth-300 transition-colors hover:bg-earth-800 hover:text-ink">
              <RotateCcw className="h-3.5 w-3.5" /> Réinitialiser
            </button>
          </div>
        </header>

        <div className="grid gap-4 xl:grid-cols-[210px_minmax(0,1fr)_270px]">
          <aside className="rounded-glass border border-line bg-surface p-3">
            <div className="flex items-center justify-between border-b border-line pb-3">
              <div>
                <h2 className="text-sm font-bold text-ink">Matériel</h2>
                <p className="mt-0.5 text-[11px] text-earth-400">Glisser vers le plan</p>
              </div>
              <Plus className="h-4 w-4 text-water-400" />
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 xl:grid-cols-1">
              {MATERIALS.map((material) => {
                const Icon = material.icon;
                return (
                  <div key={material.type} draggable onDragStart={(event) => event.dataTransfer.setData('materialType', material.type)} className="group flex cursor-grab items-center gap-2 rounded-xl border border-line bg-raised p-2 active:cursor-grabbing">
                    <span className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded-lg', material.tone)}><Icon className="h-4 w-4" /></span>
                    <span className="min-w-0 text-[11px] font-semibold text-earth-200 group-hover:text-ink">{material.shortLabel}</span>
                  </div>
                );
              })}
            </div>
            <div className="mt-3 flex items-start gap-2 rounded-lg bg-water-500/5 p-2 text-[10px] leading-4 text-earth-400">
              <Move className="mt-0.5 h-3.5 w-3.5 shrink-0 text-water-400" />
              Déplacez aussi les appareils déjà posés pour refaire le workflow.
            </div>
            <button onClick={() => { setCableMode((current) => !current); setCableStartId(null); }} className={cn('mt-2 flex w-full items-center gap-2 rounded-lg border p-2 text-left text-[10px] font-semibold transition-colors', cableMode ? 'border-water-400 bg-water-500/15 text-water-400' : 'border-line bg-raised text-earth-300 hover:bg-earth-800')}>
              <Cable className="h-3.5 w-3.5" />
              {cableMode ? (cableStartId ? 'Choisir la destination' : 'Choisir la source') : 'Créer une connexion'}
            </button>
            <div className="mt-3 border-t border-line pt-3">
              <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-earth-400">Câbles & interconnexions</p>
              <div className="space-y-2 text-[10px] text-earth-300">
                {Object.entries(CONNECTION_STYLE).map(([kind, style]) => (
                  <div key={kind} className="flex items-center gap-2">
                    <span className="h-0.5 w-7 rounded-full" style={{ backgroundColor: style.color }} />
                    <span>{style.label}</span>
                  </div>
                ))}
              </div>
            </div>
          </aside>

          <section className="min-w-0 rounded-glass border border-line bg-surface p-3">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="text-sm font-bold text-ink">Simulation 2D du système</h2>
                <p className="mt-0.5 text-[11px] text-earth-400">Les points animés représentent les messages qui circulent.</p>
              </div>
              <div className="flex items-center gap-3 text-[11px] text-earth-400">
                <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-brand-400" /> {onlineCount} en ligne</span>
                <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-water-400" /> Interconnexions actives</span>
              </div>
            </div>

            <div onDragOver={(event) => event.preventDefault()} onDrop={handleCanvasDrop} className="relative aspect-[900/520] min-h-[380px] overflow-hidden rounded-2xl border border-line bg-sunken" aria-label="Plan de simulation 2D des appareils">
              <div className="pointer-events-none absolute inset-0 opacity-40" style={{ backgroundImage: 'linear-gradient(rgba(93, 142, 151, .12) 1px, transparent 1px), linear-gradient(90deg, rgba(93, 142, 151, .12) 1px, transparent 1px)', backgroundSize: '36px 36px' }} />
              <div className="pointer-events-none absolute left-4 top-4 text-[10px] font-semibold uppercase tracking-[0.16em] text-earth-500">Zone de travail · glisser-déposer</div>
              <svg viewBox="0 0 900 520" preserveAspectRatio="none" className="absolute inset-0 h-full w-full" role="img" aria-label="Connexions animées entre les appareils">
                <defs>
                  {Object.entries(CONNECTION_STYLE).map(([kind, style]) => (
                    <marker key={kind} id={'arrow-' + kind} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
                      <path d="M 0 0 L 10 5 L 0 10 z" fill={style.color} />
                    </marker>
                  ))}
                </defs>
                {connections.map((connection, index) => {
                  const from = nodeById.get(connection.from);
                  const to = nodeById.get(connection.to);
                  if (!from || !to) return null;
                  const x1 = from.x + 75;
                  const y1 = from.y + 38;
                  const x2 = to.x + 75;
                  const y2 = to.y + 38;
                  const curve = Math.max(35, Math.abs(x2 - x1) * 0.35);
                  const path = 'M ' + x1 + ' ' + y1 + ' C ' + (x1 + curve) + ' ' + y1 + ', ' + (x2 - curve) + ' ' + y2 + ', ' + x2 + ' ' + y2;
                  const priority = connectionPriority(connection);
                  const active = isSimulating;
                  const focused = index === activeEvent;
                  const animationDuration = priority === 1 ? '1.4s' : priority === 2 ? '2.2s' : '3.2s';
                  const connectionStyle = CONNECTION_STYLE[connection.kind];
                  return (
                    <g key={connection.id} onClick={() => setSelectedConnectionId(connection.id)} className="cursor-pointer">
                      <path d={path} fill="none" stroke="transparent" strokeWidth="14" />
                      <path d={path} fill="none" stroke={connectionStyle.color} strokeOpacity={selectedConnectionId === connection.id ? 1 : focused ? 1 : priority === 1 ? 0.92 : priority === 2 ? 0.72 : 0.42} strokeWidth={selectedConnectionId === connection.id ? 5 : priority === 1 ? 3.5 : priority === 2 ? 2.8 : 2} strokeDasharray={connection.kind === 'data' ? '7 5' : undefined} markerEnd={'url(#arrow-' + connection.kind + ')'} />
                      {active && <circle r={priority === 1 ? 5 : 3.5} fill={connectionStyle.color}><animateMotion dur={animationDuration} repeatCount="indefinite" path={path} /></circle>}
                    </g>
                  );
                })}
              </svg>

              {nodes.map((node) => <DeviceNode key={node.id} node={node} cableMode={cableMode} cableStart={cableStartId === node.id} onClick={() => handleNodeClick(node.id)} onDragStart={(event) => event.dataTransfer.setData('nodeId', node.id)} />)}
            </div>
          </section>

          <div className="space-y-4">
            <WorkflowInspector connection={selectedConnection} source={selectedConnection ? nodeById.get(selectedConnection.from) : undefined} target={selectedConnection ? nodeById.get(selectedConnection.to) : undefined} />
            <EnvironmentAlerts farmName={farm.name} criticalZones={criticalZones} attentionDevices={attentionDevices} emergencyStopActive={emergencyStopActive} />
          </div>
        </div>
      </div>
    </AppShell>
  );
}

function WorkflowInspector({ connection, source, target }: { connection: Connection | null; source?: CanvasNode; target?: CanvasNode }) {
  if (!connection) return <aside className="rounded-xl border border-line bg-surface p-4"><div className="flex items-center gap-2"><Database className="h-4 w-4 text-water-400" /><h2 className="text-sm font-bold text-ink">Lecture du workflow</h2></div><p className="mt-3 text-[11px] leading-5 text-earth-400">Cliquez sur un câble ou un appareil pour voir les données qui circulent et pourquoi cette étape existe.</p></aside>;
  const reason = connection.kind === 'data' ? connection.label.includes('Commande') ? 'La gateway a validé les mesures et transmet une consigne à l’actionneur.' : 'Le système collecte cette mesure pour comparer le terrain aux seuils et décider.' : connection.kind === 'power' ? 'L’énergie disponible est vérifiée avant de lancer la pompe ou de charger la batterie.' : 'Le débit et la pression confirment que l’eau arrive réellement à la zone.';
  const step = connection.kind === 'data' && connection.label.includes('Commande') ? '4 · Agir sur le terrain' : connection.kind === 'power' ? '3 · Vérifier l’énergie' : connection.kind === 'water' ? '5 · Contrôler le résultat' : '1–2 · Mesurer puis comparer';
  return <aside className="rounded-xl border border-water-500/30 bg-surface p-4 shadow-lg"><div className="flex items-start justify-between gap-2 border-b border-line pb-3"><div><p className="text-[10px] font-bold uppercase tracking-wider text-water-400">Flux sélectionné</p><h2 className="mt-1 text-sm font-bold text-ink">{connection.label}</h2></div><span className="rounded-full px-2 py-1 text-[9px] font-bold" style={{ color: CONNECTION_STYLE[connection.kind].color, backgroundColor: CONNECTION_STYLE[connection.kind].color + '18' }}>{CONNECTION_STYLE[connection.kind].label}</span></div><div className="mt-3 flex items-center gap-2 text-[10px] font-bold text-ink"><span className="min-w-0 truncate rounded-lg bg-raised px-2 py-1.5">{source?.label ?? connection.from}</span><ArrowRight className="h-3.5 w-3.5 shrink-0 text-water-400" /><span className="min-w-0 truncate rounded-lg bg-raised px-2 py-1.5">{target?.label ?? connection.to}</span></div><div className="mt-3 space-y-2 text-[10px]"><div className="flex items-center justify-between gap-2"><span className="text-earth-500">Topic</span><code className="max-w-[170px] truncate rounded bg-sunken px-1.5 py-1 text-water-400">{connection.topic}</code></div><div className="flex items-center justify-between gap-2"><span className="flex items-center gap-1 text-earth-500"><Clock3 className="h-3 w-3" />Fréquence</span><span className="font-semibold text-ink">{connection.frequency}</span></div></div><div className="mt-3 rounded-lg bg-[#071d24] p-2.5"><p className="mb-1 text-[9px] font-semibold uppercase tracking-wider text-water-300">Payload transporté</p><pre className="overflow-x-auto whitespace-pre-wrap text-[10px] leading-4 text-brand-300">{connection.payload}</pre></div><div className="mt-3 rounded-lg border border-line bg-raised p-2.5"><p className="text-[9px] font-semibold uppercase tracking-wider text-earth-500">Pourquoi cette étape ?</p><p className="mt-1 text-[11px] leading-4 text-earth-300">{reason}</p><p className="mt-2 flex items-center gap-1 text-[10px] font-bold text-brand-400">Étape du workflow : {step}</p></div></aside>;
}

function EnvironmentAlerts({ farmName, criticalZones, attentionDevices, emergencyStopActive }: { farmName: string; criticalZones: FarmZone[]; attentionDevices: Device[]; emergencyStopActive: boolean }) {
  const hasAlerts = emergencyStopActive || criticalZones.length > 0 || attentionDevices.length > 0;

  return (
    <aside className="rounded-xl border border-line bg-surface p-4">
      <div className="flex items-center justify-between border-b border-line pb-3">
        <div className="flex items-center gap-2">
          <Bell className={cn('h-4 w-4', hasAlerts ? 'text-alert-400' : 'text-brand-400')} />
          <div>
            <h2 className="text-sm font-bold text-ink">État de l’environnement</h2>
            <p className="mt-0.5 text-[11px] text-earth-400">Données actuelles · {farmName}</p>
          </div>
        </div>
        <span className={cn('rounded-full px-2 py-1 text-[10px] font-semibold', hasAlerts ? 'bg-alert-500/10 text-alert-400' : 'bg-brand-500/10 text-brand-400')}>
          {hasAlerts ? 'Action requise' : 'Normal'}
        </span>
      </div>

      {emergencyStopActive && (
        <div className="mt-3 flex gap-2 rounded-lg border border-alert-500/40 bg-alert-500/10 p-2.5 text-[11px] text-alert-300">
          <ShieldAlert className="h-4 w-4 shrink-0" />
          <span><strong>Arrêt d’urgence actif.</strong> Toutes les opérations d’irrigation sont suspendues.</span>
        </div>
      )}

      <div className="mt-3 space-y-2">
        {criticalZones.map((zone) => (
          <Link key={zone.id} href={'/farm/zones/' + zone.id} className="flex gap-2 rounded-lg border border-alert-500/35 bg-alert-500/10 p-2.5 transition-colors hover:bg-alert-500/15">
            <ShieldAlert className="h-4 w-4 shrink-0 text-alert-400" />
            <span className="min-w-0"><strong className="block truncate text-[11px] text-alert-300">{zone.name}</strong><span className="mt-0.5 block text-[10px] leading-4 text-alert-300/80">Humidité {zone.soilMoisturePercent}% · seuil {zone.targetMoistureMin}% · décision immédiate</span></span>
          </Link>
        ))}

        {attentionDevices.map((device) => (
          <div key={device.id} className={cn('flex gap-2 rounded-lg border p-2.5', device.status === 'alert' ? 'border-alert-500/35 bg-alert-500/10' : 'border-sun-500/35 bg-sun-500/10')}>
            {device.status === 'offline' ? <WifiOff className="h-4 w-4 shrink-0 text-alert-400" /> : <TriangleAlert className="h-4 w-4 shrink-0 text-sun-400" />}
            <span className="min-w-0"><strong className={cn('block truncate text-[11px]', device.status === 'alert' ? 'text-alert-300' : 'text-sun-300')}>{device.name}</strong><span className="mt-0.5 block text-[10px] leading-4 text-earth-300">État : {device.status === 'offline' ? 'hors ligne' : device.status === 'alert' ? 'alerte' : 'à surveiller'} · dernier ping {device.lastPing}</span></span>
          </div>
        ))}

        {!hasAlerts && <div className="rounded-lg bg-brand-500/10 p-3 text-[11px] text-brand-300">Tous les appareils et toutes les zones fonctionnent normalement.</div>}
      </div>
    </aside>
  );
}

function DeviceNode({ node, cableMode, cableStart, onClick, onDragStart }: { node: CanvasNode; cableMode: boolean; cableStart: boolean; onClick: () => void; onDragStart: (event: DragEvent<HTMLDivElement>) => void }) {
  const material = MATERIALS.find((item) => item.type === node.materialType) ?? MATERIALS[0];
  const Icon = material.icon;
  return (
    <div
      draggable
      onDragStart={onDragStart}
      onClick={onClick}
      className={cn('absolute flex w-[150px] items-center gap-2 rounded-xl border bg-surface/95 p-2.5 shadow-lg backdrop-blur-md active:cursor-grabbing', cableMode ? 'cursor-crosshair' : 'cursor-grab', cableStart ? 'border-water-400 ring-2 ring-water-400/40' : 'border-line')}
      style={{ left: (node.x / 900) * 100 + '%', top: (node.y / 520) * 100 + '%' }}
    >
      <span className={cn('flex h-9 w-9 shrink-0 items-center justify-center rounded-lg', material.tone)}><Icon className="h-4 w-4" /></span>
      <div className="min-w-0">
        <p className="truncate text-[11px] font-bold text-ink">{node.label}</p>
        <p className={cn('mt-0.5 text-[10px]', node.status === 'alert' ? 'text-alert-400' : node.status === 'warning' ? 'text-sun-400' : 'text-brand-400')}>{STATUS_LABEL[node.status]}</p>
      </div>
      <span className={cn('ml-auto h-2 w-2 shrink-0 rounded-full', node.status === 'alert' ? 'bg-alert-500' : node.status === 'warning' ? 'bg-sun-500' : 'bg-brand-500')} />
    </div>
  );
}
