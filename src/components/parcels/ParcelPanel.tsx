'use client';

import React from 'react';
import Link from 'next/link';
import { X, ArrowRight, LandPlot } from 'lucide-react';
import { useParcelStore } from '@/stores/useParcelStore';
import { formatNumber } from '@/lib/utils';
import { CopyIdButton } from './CopyIdButton';

/** Compact card for the parcel selected on the map. */
export function ParcelPanel() {
  const { parcels, selectedParcelId, selectParcel, mode, lastCreatedId } = useParcelStore();
  const parcel = parcels.find((p) => p.id === selectedParcelId);
  if (!parcel || mode !== 'idle' || lastCreatedId) return null;

  return (
    <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-30 w-[min(24rem,calc(100%-2rem))]">
      <div className="glass-panel rounded-glass-sm p-4 text-sm space-y-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-water-400">
              <LandPlot className="h-3.5 w-3.5" /> Parcelle
            </p>
            <p className="font-mono text-base font-black tracking-wider text-ink mt-0.5">{parcel.id}</p>
            <p className="text-xs text-earth-300 truncate">
              {parcel.name} · {formatNumber(parcel.areaHa, 2)} ha · {parcel.cropType}
            </p>
            <p className="text-xs text-earth-300">Propriétaire : <span className="font-semibold text-ink">{parcel.ownerName}</span></p>
          </div>
          <button onClick={() => selectParcel(null)} aria-label="Fermer" className="p-1 rounded-lg text-earth-400 hover:text-ink">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex gap-2">
          <CopyIdButton value={parcel.id} />
          <Link
            href={`/parcelles/${encodeURIComponent(parcel.id)}`}
            className="inline-flex items-center gap-1.5 rounded-xl bg-accent hover:bg-accent-hover px-3 py-1.5 text-xs font-bold text-on-accent"
          >
            Voir la fiche <ArrowRight className="h-3.5 w-3.5 rtl:rotate-180" />
          </Link>
        </div>
      </div>
    </div>
  );
}
