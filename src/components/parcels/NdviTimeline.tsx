'use client';

import React, { useEffect, useState } from 'react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Sprout, Loader2, PlugZap } from 'lucide-react';
import { useSentinelStore } from '@/stores/useSentinelStore';
import { DataBadge } from '@/components/FarmDigitalTwin/SatelliteDateSelector';
import { getNdviTimeseries, toPolygon, type NdviStats } from '@/lib/sentinel/client';
import type { LngLat } from '@/lib/parcels/types';

const monthFmt = new Intl.DateTimeFormat('fr-TN', { month: 'short', year: '2-digit' });
const dayFmt = new Intl.DateTimeFormat('fr-TN', { day: 'numeric', month: 'long', year: 'numeric' });

/** Real NDVI over the last 12 months for one parcel (Copernicus Sentinel-2, clouds excluded). */
export function NdviTimeline({ polygon }: { polygon: LngLat[] }) {
  const { link, message, connect } = useSentinelStore();
  const [points, setPoints] = useState<NdviStats[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void connect();
  }, [connect]);

  useEffect(() => {
    if (link !== 'live') return;
    let cancelled = false;
    setPoints(null);
    setError(null);
    getNdviTimeseries(toPolygon(polygon), 12)
      .then((r) => !cancelled && setPoints(r.points))
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [link, polygon]);

  const data = (points ?? []).map((p) => ({ date: p.from, ndvi: p.mean, min: p.min, max: p.max }));
  const last = data[data.length - 1];
  const peak = data.reduce<(typeof data)[number] | null>((m, d) => (!m || d.ndvi > m.ndvi ? d : m), null);

  return (
    <section className="qa-card rounded-glass bg-surface border border-line p-6 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.14em] text-water-400">
            <Sprout className="h-4 w-4" /> Santé de la végétation
          </p>
          <h2 className="mt-1 text-lg font-bold text-ink">Évolution du NDVI sur 12 mois</h2>
          <p className="text-xs text-earth-300">Sentinel-2 L2A · une valeur tous les 10 jours · nuages exclus</p>
        </div>
        <DataBadge live={link === 'live' && !error} title={error ?? undefined} />
      </div>

      {link === 'checking' || (link === 'live' && !points && !error) ? (
        <div className="h-56 rounded-glass-sm bg-sunken animate-pulse flex items-center justify-center text-xs text-earth-400 gap-2">
          <Loader2 className="h-4 w-4 animate-spin" /> Analyse de 12 mois d’images satellite…
        </div>
      ) : link !== 'live' || error ? (
        <div className="h-56 rounded-glass-sm border border-dashed border-line-strong flex flex-col items-center justify-center text-center gap-2 px-6">
          <PlugZap className="h-6 w-6 text-earth-400" />
          <p className="text-sm font-semibold text-ink">Données satellite non disponibles</p>
          <p className="text-xs text-earth-300 max-w-sm">{error ?? message ?? 'Le backend QATRA n’est pas connecté.'}</p>
        </div>
      ) : data.length === 0 ? (
        <div className="h-56 rounded-glass-sm border border-dashed border-line-strong flex items-center justify-center text-sm text-earth-300">
          Aucune image sans nuages sur cette période.
        </div>
      ) : (
        <>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
                <defs>
                  <linearGradient id="ndviFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3BAF8C" stopOpacity={0.45} />
                    <stop offset="100%" stopColor="#3BAF8C" stopOpacity={0.03} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgb(var(--line))" strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="date"
                  tickFormatter={(d) => monthFmt.format(new Date(d))}
                  tick={{ fontSize: 11, fill: 'rgb(var(--earth-400))' }}
                  minTickGap={24}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis domain={[0, 1]} ticks={[0, 0.25, 0.5, 0.75, 1]} tick={{ fontSize: 11, fill: 'rgb(var(--earth-400))' }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ borderRadius: 12, border: '1px solid rgb(var(--line))', background: 'rgb(var(--surface))', fontSize: 12 }}
                  labelFormatter={(d) => dayFmt.format(new Date(d as string))}
                  formatter={(v: number) => [v.toFixed(2), 'NDVI moyen']}
                />
                <Area type="monotone" dataKey="ndvi" stroke="#2E9677" strokeWidth={2} fill="url(#ndviFill)" dot={{ r: 2.5 }} activeDot={{ r: 5 }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
            {last && <Figure label="Dernière mesure" value={last.ndvi.toFixed(2)} hint={dayFmt.format(new Date(last.date))} />}
            {peak && <Figure label="Pic de végétation" value={peak.ndvi.toFixed(2)} hint={dayFmt.format(new Date(peak.date))} />}
            <Figure label="Mesures exploitables" value={String(data.length)} hint="images sans nuages" />
          </div>
        </>
      )}
    </section>
  );
}

function Figure({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-glass-sm bg-sunken ring-1 ring-inset ring-line px-3 py-2">
      <p className="text-[11px] font-semibold text-earth-300">{label}</p>
      <p className="font-mono text-lg font-black text-ink">{value}</p>
      <p className="text-[11px] text-earth-400">{hint}</p>
    </div>
  );
}
