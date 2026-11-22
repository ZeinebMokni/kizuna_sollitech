'use client';

import dynamic from 'next/dynamic';
import { AppShell } from '@/components/layout/AppShell';

const FarmMap = dynamic(
  () => import('@/components/FarmDigitalTwin/FarmMap').then(m => ({ default: m.FarmMap })),
  {
    ssr: false,
    loading: () => (
      <div className="h-[calc(100vh-12rem)] bg-sunken rounded-2xl border border-line flex items-center justify-center">
        <div className="text-center space-y-3">
          <div className="w-8 h-8 border-2 border-brand-400 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-brand-400 text-sm font-mono animate-pulse">Chargement du SIG MapLibre…</p>
          <p className="text-earth-500 text-xs">Initialisation des tuiles Sentinel-2</p>
        </div>
      </div>
    )
  }
);

export default function FarmMapPage() {
  return (
    <AppShell>
      <div className="space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-line">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-brand-400">
              SIG MapLibre GL · Sentinel-2 · Copernicus CDSE
            </span>
            <h1 className="text-xl font-bold text-ink">Jumeau Numérique Géoréférencé en Direct</h1>
          </div>
          <div className="flex items-center gap-2 text-xs text-earth-400">
            <span>WGS84 / EPSG:3857</span>
            <span>•</span>
            <span className="text-brand-400 font-medium">Sentinel-2 T32SMF Tunisie</span>
          </div>
        </div>
        <FarmMap />
      </div>
    </AppShell>
  );
}
