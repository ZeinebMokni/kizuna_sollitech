'use client';

import Link from 'next/link';
import {
  ArrowRight,
  CheckCircle2,
  Clock3,
  Droplets,
  History,
  MapPin,
  Play,
  Route,
  Sprout,
  Square,
  TriangleAlert,
  Waves,
  Zap,
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { useFarmStore } from '@/stores/useFarmStore';
import { cn, formatNumber } from '@/lib/utils';
import type { FarmZone, HealthStatus } from '@/types';

type HistoryItem = { date: string; title: string; detail: string; result: string; tone: 'warning' | 'success' | 'info' };

const ZONE_HISTORY: Record<string, HistoryItem[]> = {
  'zone-1': [
    { date: '18 nov. 2026', title: 'Sol suffisamment humide', detail: 'Le capteur est resté au-dessus du seuil de 30 %.', result: 'Arrosage reporté.', tone: 'info' },
    { date: '14 nov. 2026', title: 'Baisse légère d’humidité', detail: 'Le sol est descendu à 29 %.', result: 'Cycle goutte-à-goutte de 25 min terminé.', tone: 'success' },
  ],
  'zone-2': [
    { date: 'Aujourd’hui', title: 'Humidité sous le seuil', detail: '22 % mesurés pour un minimum attendu de 35 %.', result: 'Cycle prioritaire programmé.', tone: 'warning' },
    { date: '09 nov. 2026', title: 'Température élevée sous serre', detail: '32,1 °C et humidité de l’air à 38 %.', result: 'Arrosage fractionné activé.', tone: 'success' },
  ],
  'zone-3': [
    { date: '16 nov. 2026', title: 'État stable', detail: 'Humidité à 44 %, dans la plage cible 32–55 %.', result: 'Aucune intervention.', tone: 'info' },
    { date: '02 nov. 2026', title: 'Sol trop sec', detail: 'Le capteur a détecté 30 %.', result: 'Micro-aspersion arrêtée à 36 %.', tone: 'success' },
  ],
  'zone-4': [
    { date: 'Aujourd’hui', title: 'Alerte sécheresse', detail: 'Humidité à 14 %, sous le seuil critique de 35 %.', result: 'Irrigation solaire recommandée · 45 min.', tone: 'warning' },
    { date: '11 nov. 2026', title: 'Stress hydrique détecté', detail: 'NDVI en baisse et température du sol élevée.', result: 'Arrosage ciblé effectué.', tone: 'success' },
  ],
  'zone-5': [
    { date: 'En cours', title: 'Cycle d’irrigation actif', detail: 'Le pivot fonctionne à 56 % d’humidité.', result: 'Arrêt automatique dans la plage cible.', tone: 'info' },
    { date: '12 nov. 2026', title: 'Besoin d’eau confirmé', detail: 'La météo sèche a augmenté la demande.', result: 'Cycle lancé pendant le pic solaire.', tone: 'success' },
  ],
};

const STATUS_LABEL: Record<HealthStatus, string> = {
  healthy: 'Saine',
  warning: 'À surveiller',
  critical: 'Critique',
  irrigating: 'Irrigation',
  nodata: 'Sans données',
};

const STATUS_CLASS: Record<HealthStatus, string> = {
  healthy: 'bg-brand-500/10 text-brand-400',
  warning: 'bg-sun-500/10 text-sun-400',
  critical: 'bg-alert-500/10 text-alert-400',
  irrigating: 'bg-water-500/10 text-water-400',
  nodata: 'bg-earth-800 text-earth-300',
};

function decisionFor(zone: FarmZone) {
  if (zone.irrigationStatus === 'active') return 'Cycle en cours';
  if (zone.soilMoisturePercent < zone.targetMoistureMin - 10) return 'Arroser maintenant';
  if (zone.soilMoisturePercent < zone.targetMoistureMin) return 'Arrosage prioritaire';
  if (zone.soilMoisturePercent > zone.targetMoistureMax) return 'Reporter l’arrosage';
  return 'Surveiller';
}

export default function DashboardPage() {
  const { farm, selectedZoneId, selectZone, startIrrigation, stopIrrigation } = useFarmStore();
  const selectedZone = farm.zones.find((zone) => zone.id === selectedZoneId) ?? farm.zones[0];
  const healthyCount = farm.zones.filter((zone) => zone.status === 'healthy').length;
  const attentionCount = farm.zones.filter((zone) => zone.status === 'warning' || zone.status === 'critical').length;
  const activeCount = farm.zones.filter((zone) => zone.irrigationStatus === 'active').length;

  return (
    <AppShell>
      <main className="h-full overflow-y-auto px-4 pb-8 pt-4 sm:px-5 lg:px-6">
        <div className="mx-auto max-w-[1500px] space-y-4">
          <header className="flex flex-col gap-3 border-b border-line pb-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-water-400">
                <Sprout className="h-3.5 w-3.5" /> Vue opérationnelle
              </div>
              <h1 className="mt-1 truncate text-xl font-black tracking-tight text-ink sm:text-2xl">{farm.name}</h1>
              <p className="mt-1 text-xs text-earth-400">{formatNumber(farm.totalAreaHa, 1)} ha · {farm.delegation} · {farm.zones.length} zones · puits {farm.wellDepthMeters} m</p>
            </div>
            <Link href="/farm/map" className="inline-flex items-center gap-2 self-start rounded-lg bg-accent px-3 py-2 text-xs font-semibold text-on-accent transition-colors hover:bg-accent-hover">
              <MapPin className="h-3.5 w-3.5" /> Ouvrir la carte <ArrowRight className="h-3.5 w-3.5 rtl:rotate-180" />
            </Link>
          </header>

          <section className="grid grid-cols-2 divide-x divide-line overflow-hidden rounded-xl border border-line bg-surface sm:grid-cols-4">
            <Summary label="Zones" value={String(farm.zones.length)} detail={formatNumber(farm.totalAreaHa, 1) + ' ha'} icon={Sprout} />
            <Summary label="Saines" value={String(healthyCount)} detail="aucune action" icon={CheckCircle2} />
            <Summary label="À traiter" value={String(attentionCount)} detail="décision requise" icon={TriangleAlert} tone="warning" />
            <Summary label="En irrigation" value={String(activeCount)} detail="cycle actuel" icon={Droplets} tone="water" />
          </section>

          <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(300px,.8fr)]">
            <section className="overflow-hidden rounded-xl border border-line bg-surface">
              <div className="flex items-center justify-between border-b border-line px-4 py-3">
                <div>
                  <h2 className="text-sm font-bold text-ink">Zones et opérations maintenant</h2>
                  <p className="mt-0.5 text-[11px] text-earth-400">État, décision et action au même endroit.</p>
                </div>
                <span className="hidden items-center gap-1.5 text-[11px] text-earth-400 sm:flex"><Waves className="h-3.5 w-3.5 text-water-400" /> télémétrie live</span>
              </div>
              <div className="divide-y divide-line">
                {farm.zones.map((zone) => (
                  <ZoneRow
                    key={zone.id}
                    zone={zone}
                    selected={zone.id === selectedZone?.id}
                    onSelect={() => selectZone(zone.id)}
                    onStart={() => startIrrigation(zone.id)}
                    onStop={() => stopIrrigation(zone.id)}
                  />
                ))}
              </div>
            </section>

            <aside className="space-y-4">
              {selectedZone && (
                <section className="rounded-xl border border-line bg-surface p-4">
                  <div className="flex items-center justify-between border-b border-line pb-3">
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-water-400">Décision active</p>
                      <h2 className="mt-1 text-sm font-bold text-ink">{selectedZone.name}</h2>
                    </div>
                    <span className={cn('rounded-full px-2 py-1 text-[10px] font-semibold', STATUS_CLASS[selectedZone.status])}>{STATUS_LABEL[selectedZone.status]}</span>
                  </div>
                  <div className="mt-3 flex items-center justify-between gap-3">
                    <div>
                      <p className="text-2xl font-black text-ink">{selectedZone.soilMoisturePercent}%</p>
                      <p className="text-[11px] text-earth-400">cible {selectedZone.targetMoistureMin}–{selectedZone.targetMoistureMax}%</p>
                    </div>
                    <p className={cn('text-right text-xs font-bold', selectedZone.status === 'critical' ? 'text-alert-400' : selectedZone.status === 'warning' ? 'text-sun-400' : 'text-water-400')}>{decisionFor(selectedZone)}</p>
                  </div>
                  <div className="mt-3 flex items-center gap-2 rounded-lg bg-raised p-2.5 text-[11px] text-earth-300">
                    <Route className="h-4 w-4 shrink-0 text-water-400" />
                    <span>Mesure → seuil culture → météo/solaire → action</span>
                  </div>
                  <Link href={'/farm/zones/' + selectedZone.id} className="mt-3 inline-flex items-center gap-1 text-[11px] font-semibold text-water-400 hover:underline">
                    Voir la fiche de la zone <ArrowRight className="h-3 w-3 rtl:rotate-180" />
                  </Link>
                </section>
              )}

              <section className="rounded-xl border border-line bg-surface p-4">
                <div className="flex items-center gap-2 border-b border-line pb-3">
                  <History className="h-4 w-4 text-water-400" />
                  <div>
                    <h2 className="text-sm font-bold text-ink">Historique récent</h2>
                    <p className="mt-0.5 text-[11px] text-earth-400">{selectedZone?.name ?? 'Sélectionnez une zone'}</p>
                  </div>
                </div>
                <div className="mt-3 space-y-3">
                  {(selectedZone ? ZONE_HISTORY[selectedZone.id] : []).map((item) => (
                    <div key={item.date + item.title} className="border-l-2 border-line pl-3">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-[11px] font-semibold text-ink">{item.title}</p>
                        <time className="shrink-0 text-[10px] text-earth-500">{item.date}</time>
                      </div>
                      <p className="mt-1 text-[10px] leading-4 text-earth-400">{item.detail}</p>
                      <p className={cn('mt-1 text-[10px] font-semibold', item.tone === 'warning' ? 'text-sun-400' : item.tone === 'success' ? 'text-brand-400' : 'text-water-400')}>→ {item.result}</p>
                    </div>
                  ))}
                </div>
              </section>
            </aside>
          </div>
        </div>
      </main>
    </AppShell>
  );
}

function Summary({ label, value, detail, icon: Icon, tone = 'default' }: { label: string; value: string; detail: string; icon: typeof Sprout; tone?: 'default' | 'warning' | 'water' }) {
  return (
    <div className="min-w-0 px-3 py-2.5 sm:px-4">
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-[11px] text-earth-400">{label}</span>
        <Icon className={cn('h-3.5 w-3.5 shrink-0', tone === 'warning' ? 'text-sun-400' : tone === 'water' ? 'text-water-400' : 'text-brand-400')} />
      </div>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="text-lg font-black text-ink">{value}</span>
        <span className="truncate text-[10px] text-earth-500">{detail}</span>
      </div>
    </div>
  );
}

function ZoneRow({ zone, selected, onSelect, onStart, onStop }: { zone: FarmZone; selected: boolean; onSelect: () => void; onStart: () => void; onStop: () => void }) {
  const moistureWidth = Math.min(100, Math.max(0, (zone.soilMoisturePercent / zone.targetMoistureMax) * 100));
  const isActive = zone.irrigationStatus === 'active';
  const needsAction = zone.status === 'critical' || zone.status === 'warning';

  return (
    <div className={cn('grid gap-3 px-4 py-3 transition-colors lg:grid-cols-[minmax(180px,1.25fr)_130px_minmax(120px,.8fr)_auto] lg:items-center', selected ? 'bg-water-500/5' : 'hover:bg-raised')}>
      <button onClick={onSelect} className="min-w-0 text-left">
        <div className="flex items-center gap-2">
          <span className={cn('h-2 w-2 shrink-0 rounded-full', zone.status === 'critical' ? 'bg-alert-500' : zone.status === 'warning' ? 'bg-sun-500' : isActive ? 'bg-water-500' : 'bg-brand-500')} />
          <p className="truncate text-xs font-bold text-ink">{zone.name}</p>
          <span className={cn('shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-semibold', STATUS_CLASS[zone.status])}>{STATUS_LABEL[zone.status]}</span>
        </div>
        <p className="mt-1 pl-4 text-[10px] text-earth-500">{formatNumber(zone.areaHa, 1)} ha · {zone.irrigationMethod}</p>
      </button>

      <div>
        <div className="flex items-baseline justify-between gap-2">
          <span className={cn('text-lg font-black tabular-nums', zone.status === 'critical' ? 'text-alert-400' : 'text-ink')}>{zone.soilMoisturePercent}%</span>
          <span className="text-[10px] text-earth-500">cible {zone.targetMoistureMin}–{zone.targetMoistureMax}</span>
        </div>
        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-earth-800"><div className={cn('h-full rounded-full', zone.status === 'critical' ? 'bg-alert-500' : zone.status === 'warning' ? 'bg-sun-500' : 'bg-water-500')} style={{ width: moistureWidth + '%' }} /></div>
      </div>

      <div className="flex items-center gap-2 text-[11px]">
        {needsAction ? <Zap className={cn('h-3.5 w-3.5 shrink-0', zone.status === 'critical' ? 'text-alert-400' : 'text-sun-400')} /> : <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-brand-400" />}
        <span className={cn('font-semibold', zone.status === 'critical' ? 'text-alert-400' : zone.status === 'warning' ? 'text-sun-400' : 'text-earth-300')}>{decisionFor(zone)}</span>
      </div>

      <div className="flex items-center gap-2 lg:justify-end">
        {isActive ? (
          <button onClick={onStop} className="inline-flex items-center gap-1.5 rounded-lg border border-alert-500/30 px-2.5 py-1.5 text-[10px] font-semibold text-alert-400 hover:bg-alert-500/10"><Square className="h-3 w-3 fill-current" /> Arrêter</button>
        ) : (
          <button onClick={onStart} className={cn('inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[10px] font-semibold', needsAction ? 'bg-accent text-on-accent hover:bg-accent-hover' : 'border border-line text-earth-300 hover:bg-earth-800')}><Play className="h-3 w-3 fill-current" /> Arroser</button>
        )}
        <button onClick={onSelect} aria-label={'Voir ' + zone.name} className="rounded-lg p-1.5 text-earth-500 hover:bg-earth-800 hover:text-ink"><ArrowRight className="h-3.5 w-3.5 rtl:rotate-180" /></button>
      </div>
    </div>
  );
}
