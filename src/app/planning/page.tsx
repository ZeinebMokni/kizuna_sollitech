'use client';

import React from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { AICropPlanner } from '@/components/planning/AICropPlanner';

export default function PlanningPage() {
  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-line gap-4">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-brand-400">
              Moteur d'Optimisation Décisionnelle
            </span>
            <h1 className="text-2xl font-black text-ink">Planification Prédictive des Assolements</h1>
            <p className="text-xs text-earth-400 mt-0.5">
              Recommandation de cultures par maximisation de la rentabilité par mètre cube d'eau et par kilowatt-heure
            </p>
          </div>
        </div>

        <AICropPlanner />
      </div>
    </AppShell>
  );
}
