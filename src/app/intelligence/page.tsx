'use client';

import React from 'react';
import Link from 'next/link';
import {
  Globe2,
  TrendingUp,
  Droplets,
  Sun,
  ShieldAlert,
  ArrowRight,
  Info
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { TunisiaIntelligenceMap } from '@/components/maps/TunisiaIntelligenceMap';

export default function IntelligencePage() {
  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-line gap-4">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-brand-400">
              Observatoire National & Sécurité Alimentaire
            </span>
            <h1 className="text-2xl font-black text-ink">Intelligence Agricole & Territoriale de Tunisie</h1>
            <p className="text-xs text-earth-400 mt-0.5">
              Agrégation des bassins de production · Stress hydrique par gouvernorat · Anticipation des flux
            </p>
          </div>

          <Link
            href="/intelligence/forecast"
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-accent to-accent-deep hover:from-accent-hover text-on-accent font-bold text-xs flex items-center gap-2 border border-brand-500/30 qa-shine"
          >
            <TrendingUp className="h-4 w-4" />
            <span>Consulter les Prévisions de Prix</span>
          </Link>
        </div>

        {/* Interactive Tunisia GIS Map */}
        <TunisiaIntelligenceMap />
      </div>
    </AppShell>
  );
}
