'use client';

import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { LandPlot, SquareDashed, WandSparkles, X, Loader2, AlertTriangle, CheckCircle2, ArrowRight, MapPinned } from 'lucide-react';
import { useParcelStore } from '@/stores/useParcelStore';
import { useFarmStore } from '@/stores/useFarmStore';
import { calculatePolygonAreaHectares } from '@/lib/geo/geodesic';
import { closeRing } from '@/lib/parcels/geometry';
import { findConflict } from '@/lib/parcels/conflicts';
import { formatNumber, cn } from '@/lib/utils';
import { ParcelQRCode } from './ParcelQRCode';
import { CopyIdButton } from './CopyIdButton';

export const CROP_OPTIONS = ['Blé dur', 'Orge', 'Oliviers', 'Maraîchage', 'Agrumes', 'Fourrage', 'Jachère'];
export const IRRIGATION_OPTIONS = ['Goutte-à-goutte', 'Pivot', 'Micro-aspersion', 'Pluvial (sans irrigation)'];

const MODE_HINT = {
  rectangle: 'Cliquez-glissez sur la carte pour entourer votre terre.',
  auto: 'Cliquez au milieu d’un champ : son contour est détecté sur l’image satellite.',
} as const;

/** Map toolbar to claim land (rectangle or automatic field detection). */
export function ParcelTools() {
  const { mode, setMode } = useParcelStore();

  return (
    <>
      <div className="glass-panel rounded-2xl p-1.5 flex items-center gap-1 text-xs">
        <span className="hidden xl:flex items-center gap-1.5 px-2 font-semibold text-ink">
          <LandPlot className="h-4 w-4 text-water-400" /> Revendiquer une terre
        </span>
        <ModeButton active={mode === 'rectangle'} onClick={() => setMode(mode === 'rectangle' ? 'idle' : 'rectangle')} icon={SquareDashed}>
          Rectangle
        </ModeButton>
        <ModeButton active={mode === 'auto'} onClick={() => setMode(mode === 'auto' ? 'idle' : 'auto')} icon={WandSparkles}>
          Détection auto
        </ModeButton>
        {mode !== 'idle' && (
          <button
            onClick={() => setMode('idle')}
            aria-label="Annuler la sélection"
            className="p-1.5 rounded-xl text-earth-300 hover:text-ink hover:bg-white/40 dark:hover:bg-white/5"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

    </>
  );
}

/** Hint, save dialog and success dialog — rendered over the whole map. */
export function ParcelOverlays() {
  const { mode, detecting, detectError, draft } = useParcelStore();
  return (
    <>
      {mode !== 'idle' && !draft?.ready && (
        <div className="absolute top-[8.5rem] left-1/2 -translate-x-1/2 z-30 pointer-events-none">
          <div
            className={cn(
              'glass-panel rounded-xl px-4 py-2 text-xs font-semibold flex items-center gap-2 shadow-glass',
              detectError ? 'text-alert-400' : 'text-ink'
            )}
          >
            {detecting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin text-water-400" /> Analyse de l’image satellite…
              </>
            ) : detectError ? (
              <>
                <AlertTriangle className="h-4 w-4" /> {detectError}
              </>
            ) : (
              MODE_HINT[mode]
            )}
          </div>
        </div>
      )}

      <SaveParcelDialog />
      <ParcelCreatedDialog />
    </>
  );
}

function ModeButton({
  active,
  onClick,
  icon: Icon,
  children,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ElementType;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'px-3 py-1.5 rounded-xl font-semibold flex items-center gap-1.5 transition-colors',
        active ? 'bg-accent text-on-accent' : 'text-earth-200 hover:text-ink hover:bg-white/40 dark:hover:bg-white/5'
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      {children}
    </button>
  );
}

/** Shown once an outline is drawn or detected: name the land and its owner, then save. */
function SaveParcelDialog() {
  const { draft, mode, setDraft, currentOwner, parcels, createParcelFromDraft } = useParcelStore();
  const { farm } = useFarmStore();
  const [name, setName] = useState('');
  const [owner, setOwner] = useState(currentOwner);
  const [crop, setCrop] = useState(CROP_OPTIONS[0]);
  const [irrigation, setIrrigation] = useState(IRRIGATION_OPTIONS[0]);
  useEffect(() => setOwner(currentOwner), [currentOwner]);

  const areaHa = useMemo(() => (draft ? calculatePolygonAreaHectares(closeRing(draft.polygon)) : 0), [draft]);
  const conflict = useMemo(() => (draft ? findConflict(draft.polygon, parcels, farm, owner) : null), [draft, parcels, farm, owner]);

  if (!draft || !draft.ready || mode === 'idle') return null;

  const save = (e: React.FormEvent) => {
    e.preventDefault();
    if (conflict) return;
    createParcelFromDraft({ name, ownerName: owner, cropType: crop, irrigationMethod: irrigation });
    setName('');
  };

  return (
    <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-40 w-[min(26rem,calc(100%-2rem))]">
      <form onSubmit={save} className="glass-panel rounded-glass p-5 space-y-4 text-sm">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-water-400">
              {draft.source === 'auto' ? 'Champ détecté' : 'Terre sélectionnée'}
            </p>
            <h3 className="text-base font-bold text-ink mt-0.5">Enregistrer cette terre</h3>
          </div>
          <span className="rounded-xl bg-water-500/10 px-3 py-1.5 text-right">
            <span className="block text-lg font-black text-ink tabular-nums">{formatNumber(areaHa, 2)}</span>
            <span className="block text-[11px] text-earth-300 -mt-0.5">hectares</span>
          </span>
        </div>

        {conflict ? (
          <p className="flex items-start gap-2 rounded-xl bg-alert-950/60 px-3 py-2 text-xs font-medium text-alert-400 ring-1 ring-inset ring-alert-500/30">
            <AlertTriangle className="h-4 w-4 flex-shrink-0 mt-0.5" />
            Cette sélection chevauche {conflict}. Une terre ne peut appartenir qu’à un seul propriétaire : resserrez la sélection.
          </p>
        ) : (
          <p className="flex items-center gap-2 text-xs text-earth-300">
            <CheckCircle2 className="h-4 w-4 text-brand-400" /> Terre libre : elle recevra un identifiant unique.
          </p>
        )}

        <div className="grid grid-cols-2 gap-3">
          <Field label="Nom de la terre" className="col-span-2">
            <input id="parcel-name" value={name} onChange={(e) => setName(e.target.value)} placeholder={`Parcelle ${parcels.length + 1}`} className="qa-input" />
          </Field>
          <Field label="Propriétaire" className="col-span-2">
            <input id="parcel-owner" value={owner} onChange={(e) => setOwner(e.target.value)} required className="qa-input" />
          </Field>
          <Field label="Culture">
            <select id="parcel-crop" value={crop} onChange={(e) => setCrop(e.target.value)} className="qa-input">
              {CROP_OPTIONS.map((c) => <option key={c}>{c}</option>)}
            </select>
          </Field>
          <Field label="Irrigation">
            <select id="parcel-irrigation" value={irrigation} onChange={(e) => setIrrigation(e.target.value)} className="qa-input">
              {IRRIGATION_OPTIONS.map((c) => <option key={c}>{c}</option>)}
            </select>
          </Field>
        </div>

        <div className="flex gap-2 pt-1">
          <button type="button" onClick={() => setDraft(null)} className="flex-1 py-2.5 rounded-xl bg-white/40 dark:bg-white/5 ring-1 ring-inset ring-line text-xs font-semibold text-earth-200 hover:bg-white/60">
            Recommencer
          </button>
          <button type="submit" disabled={!!conflict} className="flex-1 py-2.5 rounded-xl bg-accent hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed text-on-accent text-xs font-bold">
            Créer la parcelle
          </button>
        </div>
      </form>
    </div>
  );
}

function Field({ label, className, children }: { label: string; className?: string; children: React.ReactNode }) {
  return (
    <label className={cn('block space-y-1', className)}>
      <span className="text-[11px] font-semibold text-earth-300">{label}</span>
      {children}
    </label>
  );
}

/** Confirmation with the new unique ID and its QR code. */
function ParcelCreatedDialog() {
  const { lastCreatedId, parcels, clearLastCreated } = useParcelStore();
  const parcel = parcels.find((p) => p.id === lastCreatedId);
  if (!parcel) return null;

  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center bg-earth-900/30 backdrop-blur-sm p-4">
      <div className="glass-panel rounded-glass p-6 w-full max-w-md text-center space-y-4">
        <div className="mx-auto h-12 w-12 rounded-full bg-brand-500/15 flex items-center justify-center text-brand-400">
          <CheckCircle2 className="h-6 w-6" />
        </div>
        <div>
          <h3 className="text-lg font-bold text-ink">Parcelle créée</h3>
          <p className="text-sm text-earth-300 mt-1">
            {parcel.name} · {formatNumber(parcel.areaHa, 2)} ha · {parcel.ownerName}
          </p>
        </div>
        <div className="rounded-glass-sm bg-white/60 dark:bg-white/5 ring-1 ring-inset ring-line px-4 py-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-earth-300">Identifiant unique</p>
          <p className="mt-1 font-mono text-xl font-black tracking-wider text-ink">{parcel.id}</p>
        </div>
        <div className="flex justify-center">
          <ParcelQRCode parcel={parcel} size={148} />
        </div>
        <p className="text-xs text-earth-300">Scannez ce QR code pour ouvrir la fiche de la terre.</p>
        <div className="flex flex-wrap justify-center gap-2">
          <CopyIdButton value={parcel.id} />
          <Link
            href={`/parcelles/${encodeURIComponent(parcel.id)}`}
            className="inline-flex items-center gap-1.5 rounded-xl bg-accent hover:bg-accent-hover px-3 py-1.5 text-xs font-bold text-on-accent"
          >
            Voir la fiche <ArrowRight className="h-3.5 w-3.5 rtl:rotate-180" />
          </Link>
          <button onClick={clearLastCreated} className="inline-flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold text-earth-300 hover:text-ink">
            <MapPinned className="h-3.5 w-3.5" /> Rester sur la carte
          </button>
        </div>
      </div>
    </div>
  );
}
