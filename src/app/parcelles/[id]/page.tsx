'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, MapPinned, Printer, LandPlot, UserRound, Sprout, Droplets, Ruler, CalendarDays, Navigation, SearchX } from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { useParcelStore } from '@/stores/useParcelStore';
import { useHydrated } from '@/lib/parcels/useHydrated';
import { decodeParcel } from '@/lib/parcels/geometry';
import { formatGPSCoordinates } from '@/lib/geo/geodesic';
import type { Parcel } from '@/lib/parcels/types';
import { ParcelShape } from '@/components/parcels/ParcelShape';
import { ParcelQRCode } from '@/components/parcels/ParcelQRCode';
import { CopyIdButton } from '@/components/parcels/CopyIdButton';
import { NdviTimeline } from '@/components/parcels/NdviTimeline';
import { formatNumber } from '@/lib/utils';

const dateFmt = new Intl.DateTimeFormat('fr-TN', { day: 'numeric', month: 'long', year: 'numeric' });

export default function ParcelFichePage({ params }: { params: { id: string } }) {
  const id = decodeURIComponent(params.id);
  const hydrated = useHydrated();
  const stored = useParcelStore((s) => s.parcels.find((p) => p.id === id));
  const [shared, setShared] = useState<Parcel | null>(null);

  // A fiche opened from a QR code / link carries its data in ?d=
  useEffect(() => {
    const d = new URLSearchParams(window.location.search).get('d');
    const parsed = d ? decodeParcel(d) : null;
    setShared(parsed && parsed.id === id ? parsed : null);
  }, [id]);

  const parcel = stored ?? shared;

  return (
    <AppShell>
      <div className="space-y-6">
        <Link href="/parcelles" className="inline-flex items-center gap-1.5 text-xs font-semibold text-earth-300 hover:text-ink print:hidden">
          <ArrowLeft className="h-3.5 w-3.5 rtl:rotate-180" /> Mes terres
        </Link>

        {!hydrated ? (
          <div className="h-72 rounded-glass bg-surface border border-line animate-pulse" aria-busy="true" />
        ) : !parcel ? (
          <NotFound id={id} />
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Identity */}
            <section className="lg:col-span-8 qa-card rounded-glass bg-surface border border-line p-6 space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                <div>
                  <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.14em] text-water-400">
                    <LandPlot className="h-4 w-4" /> Fiche de la terre
                  </p>
                  <h1 className="mt-2 font-mono text-2xl sm:text-3xl font-black tracking-wider text-ink break-all">{parcel.id}</h1>
                  <p className="mt-1 text-base font-semibold text-ink">{parcel.name}</p>
                </div>
                <div className="flex flex-wrap gap-2 print:hidden">
                  <CopyIdButton value={parcel.id} />
                  {stored && (
                    <Link
                      href={`/farm/map?parcel=${encodeURIComponent(parcel.id)}`}
                      className="inline-flex items-center gap-1.5 rounded-xl bg-accent hover:bg-accent-hover px-3 py-1.5 text-xs font-bold text-on-accent"
                    >
                      <MapPinned className="h-3.5 w-3.5" /> Voir sur la carte
                    </Link>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-[160px_1fr] gap-6 items-start">
                <ParcelShape polygon={parcel.polygon} className="h-40 w-40" />
                <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4 text-sm">
                  <Info icon={UserRound} label="Propriétaire" value={parcel.ownerName} />
                  <Info icon={Ruler} label="Surface" value={`${formatNumber(parcel.areaHa, 2)} ha`} />
                  <Info icon={Sprout} label="Culture" value={parcel.cropType} />
                  <Info icon={Droplets} label="Irrigation" value={parcel.irrigationMethod} />
                  <Info icon={Navigation} label="Localisation" value={`${parcel.delegation}, ${parcel.governorate}`} />
                  <Info icon={CalendarDays} label="Enregistrée le" value={dateFmt.format(new Date(parcel.createdAt))} />
                  <Info icon={MapPinned} label="Centre GPS" value={formatGPSCoordinates(parcel.center)} mono />
                  <Info
                    icon={LandPlot}
                    label="Sélection"
                    value={parcel.source === 'auto' ? 'Détection automatique du champ' : 'Rectangle tracé sur la carte'}
                  />
                </dl>
              </div>

              {!stored && (
                <p className="rounded-xl bg-water-500/10 px-4 py-3 text-xs text-earth-200">
                  Fiche ouverte depuis un lien ou un QR code. Cette terre n’est pas enregistrée dans ce navigateur.
                </p>
              )}
            </section>

            {/* QR label */}
            <section className="lg:col-span-4 qa-card rounded-glass bg-surface border border-line p-6 flex flex-col items-center text-center gap-4">
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-water-400">Étiquette QR</p>
              <ParcelQRCode parcel={parcel} size={200} />
              <p className="font-mono text-sm font-bold tracking-wider text-ink">{parcel.id}</p>
              <p className="text-xs text-earth-300 max-w-[16rem]">
                Imprimez cette étiquette et fixez-la au bord du champ. En la scannant, on ouvre directement cette fiche.
              </p>
              <button
                onClick={() => window.print()}
                className="inline-flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold text-ink ring-1 ring-inset ring-line hover:bg-highlight print:hidden"
              >
                <Printer className="h-3.5 w-3.5" /> Imprimer l’étiquette
              </button>
            </section>

            {/* Real vegetation history (Copernicus Sentinel-2) */}
            <div className="lg:col-span-12">
              <NdviTimeline polygon={parcel.polygon} />
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}

function Info({ icon: Icon, label, value, mono }: { icon: React.ElementType; label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="flex items-center gap-1.5 text-[11px] font-semibold text-earth-300">
        <Icon className="h-3.5 w-3.5 text-water-400" /> {label}
      </dt>
      <dd className={mono ? 'mt-0.5 font-mono text-xs text-ink' : 'mt-0.5 font-semibold text-ink'}>{value}</dd>
    </div>
  );
}

function NotFound({ id }: { id: string }) {
  return (
    <div className="rounded-glass border border-dashed border-line-strong bg-surface/70 p-10 text-center">
      <div className="mx-auto h-12 w-12 rounded-full bg-alert-500/10 flex items-center justify-center text-alert-400">
        <SearchX className="h-6 w-6" />
      </div>
      <h1 className="mt-4 text-lg font-bold text-ink">Terre introuvable</h1>
      <p className="mt-1 text-sm text-earth-300">
        Aucune terre avec l’identifiant <span className="font-mono font-semibold text-ink">{id}</span> dans ce navigateur.
      </p>
      <Link href="/parcelles" className="mt-5 inline-flex items-center gap-1.5 rounded-xl bg-accent px-4 py-2 text-xs font-bold text-on-accent">
        Retour à Mes terres
      </Link>
    </div>
  );
}
