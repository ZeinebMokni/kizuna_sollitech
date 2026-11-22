'use client';

import React, { useMemo, useState } from 'react';
import Link from 'next/link';
import { LandPlot, MapPinned, ArrowRight, Trash2, Plus, SquareDashed, WandSparkles, UserRound } from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { useParcelStore } from '@/stores/useParcelStore';
import { useHydrated } from '@/lib/parcels/useHydrated';
import { ParcelShape } from '@/components/parcels/ParcelShape';
import { CopyIdButton } from '@/components/parcels/CopyIdButton';
import { formatNumber, cn } from '@/lib/utils';

const dateFmt = new Intl.DateTimeFormat('fr-TN', { day: 'numeric', month: 'long', year: 'numeric' });

export default function MyLandsPage() {
  const hydrated = useHydrated();
  const { parcels, currentOwner, setCurrentOwner, removeParcel } = useParcelStore();
  const [confirmId, setConfirmId] = useState<string | null>(null);

  const owners = useMemo(() => {
    const set = new Set(parcels.map((p) => p.ownerName));
    set.add(currentOwner);
    return Array.from(set).sort((a, b) => a.localeCompare(b, 'fr'));
  }, [parcels, currentOwner]);

  const mine = parcels.filter((p) => p.ownerName === currentOwner);
  const totalHa = mine.reduce((s, p) => s + p.areaHa, 0);

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-water-400">Registre des terres</p>
            <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-ink mt-1">Mes terres</h1>
            <p className="text-sm text-earth-300 mt-1 max-w-xl">
              Chaque terre a un identifiant unique et un seul propriétaire. Sélectionnez une nouvelle terre directement sur la carte.
            </p>
          </div>
          <Link href="/farm/map" className="qa-shine self-start sm:self-auto px-4 py-2.5 rounded-xl text-on-accent font-semibold text-sm flex items-center gap-2">
            <Plus className="h-4 w-4" /> Ajouter une terre
          </Link>
        </div>

        {/* Owner + totals */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="qa-card rounded-glass bg-surface border border-line p-5 md:col-span-1">
            <label htmlFor="owner-select" className="flex items-center gap-2 text-xs font-semibold text-earth-300">
              <UserRound className="h-4 w-4 text-water-400" /> Propriétaire
            </label>
            <select
              id="owner-select"
              value={currentOwner}
              onChange={(e) => setCurrentOwner(e.target.value)}
              className="qa-input mt-2 text-sm font-semibold"
              disabled={!hydrated}
            >
              {owners.map((o) => <option key={o}>{o}</option>)}
            </select>
          </div>
          <Stat label="Terres enregistrées" value={hydrated ? String(mine.length) : '—'} />
          <Stat label="Surface totale" value={hydrated ? `${formatNumber(totalHa, 2)} ha` : '—'} />
        </div>

        {/* List */}
        {!hydrated ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4" aria-busy="true">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-48 rounded-glass bg-surface border border-line animate-pulse" />
            ))}
          </div>
        ) : mine.length === 0 ? (
          <EmptyState owner={currentOwner} />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {mine.map((p) => (
              <article key={p.id} className="qa-card rounded-glass bg-surface border border-line p-5 flex flex-col gap-4">
                <div className="flex items-start gap-4">
                  <ParcelShape polygon={p.polygon} className="h-20 w-20 flex-shrink-0" />
                  <div className="min-w-0">
                    <p className="font-mono text-sm font-black tracking-wider text-ink break-all">{p.id}</p>
                    <p className="text-sm font-semibold text-ink mt-1 truncate">{p.name}</p>
                    <p className="text-xs text-earth-300 mt-0.5">
                      {formatNumber(p.areaHa, 2)} ha · {p.cropType}
                    </p>
                    <p className="text-[11px] text-earth-400 mt-0.5">
                      {p.irrigationMethod} · {dateFmt.format(new Date(p.createdAt))}
                    </p>
                  </div>
                </div>

                <div className="mt-auto flex flex-wrap items-center gap-2 pt-3 border-t border-line">
                  <Link
                    href={`/parcelles/${encodeURIComponent(p.id)}`}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-accent hover:bg-accent-hover px-3 py-1.5 text-xs font-bold text-on-accent"
                  >
                    Voir la fiche <ArrowRight className="h-3.5 w-3.5 rtl:rotate-180" />
                  </Link>
                  <Link
                    href={`/farm/map?parcel=${encodeURIComponent(p.id)}`}
                    className="inline-flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold text-ink ring-1 ring-inset ring-line hover:bg-highlight"
                  >
                    <MapPinned className="h-3.5 w-3.5" /> Carte
                  </Link>
                  <CopyIdButton value={p.id} label="ID" />
                  {confirmId === p.id ? (
                    <span className="ms-auto flex items-center gap-1.5 text-xs">
                      <button onClick={() => removeParcel(p.id)} className="rounded-lg bg-alert-600 px-2.5 py-1 font-bold text-on-accent">
                        Supprimer
                      </button>
                      <button onClick={() => setConfirmId(null)} className="px-2 py-1 font-semibold text-earth-300 hover:text-ink">
                        Annuler
                      </button>
                    </span>
                  ) : (
                    <button
                      onClick={() => setConfirmId(p.id)}
                      aria-label={`Supprimer la parcelle ${p.id}`}
                      className="ms-auto p-1.5 rounded-lg text-earth-400 hover:text-alert-400 hover:bg-alert-950/50"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </article>
            ))}
          </div>
        )}

        <p className="text-[11px] text-earth-400">
          Les terres sont enregistrées dans ce navigateur. Le lien et le QR code de chaque fiche contiennent ses informations, et
          s’ouvrent donc aussi sur un autre appareil.
        </p>
      </div>
    </AppShell>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="qa-card rounded-glass bg-surface border border-line p-5">
      <p className="text-xs font-semibold text-earth-300">{label}</p>
      <p className="mt-2 text-3xl font-black tracking-tight text-ink tabular-nums">{value}</p>
    </div>
  );
}

function EmptyState({ owner }: { owner: string }) {
  return (
    <div className="rounded-glass border border-dashed border-line-strong bg-surface/70 p-10 text-center">
      <div className="mx-auto h-12 w-12 rounded-full bg-water-500/10 flex items-center justify-center text-water-400">
        <LandPlot className="h-6 w-6" />
      </div>
      <h2 className="mt-4 text-lg font-bold text-ink">Aucune terre pour {owner}</h2>
      <p className="mt-1 text-sm text-earth-300 max-w-md mx-auto">
        Ouvrez la carte et choisissez « Rectangle » pour entourer votre terre, ou « Détection auto » pour cliquer sur un champ.
      </p>
      <div className={cn('mt-5 flex flex-wrap justify-center gap-2 text-xs')}>
        <Link href="/farm/map" className="inline-flex items-center gap-1.5 rounded-xl bg-accent hover:bg-accent-hover px-4 py-2 font-bold text-on-accent">
          <SquareDashed className="h-4 w-4" /> Sélectionner ma terre sur la carte
        </Link>
        <span className="inline-flex items-center gap-1.5 px-2 text-earth-400">
          <WandSparkles className="h-4 w-4" /> ou détecter un champ automatiquement
        </span>
      </div>
    </div>
  );
}
