'use client';

import React from 'react';
import Link from 'next/link';
import {
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  Brain,
  ArrowRight,
  ShieldAlert,
  Coins
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { DEMO_MARKET_FORECASTS } from '@/lib/mockData';
import { cn, formatNumber, formatCurrencyTND } from '@/lib/utils';

export default function ForecastPage() {
  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-line gap-4">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-brand-400">
              Modélisation Prédictive & Économique
            </span>
            <h1 className="text-2xl font-black text-ink">Prévisions de l'Offre & de la Demande Nationale</h1>
            <p className="text-xs text-earth-400 mt-0.5">
              Anticipation des déséquilibres de marché pour protéger les revenus agricoles tunisiens
            </p>
          </div>

          <Link
            href="/planning"
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-accent to-accent-deep hover:from-accent-hover text-on-accent font-bold text-xs flex items-center gap-2 border border-brand-500/30 qa-shine"
          >
            <Brain className="h-4 w-4" />
            <span>Planifier mes Prochaines Cultures avec l'IA</span>
          </Link>
        </div>

        {/* Forecasts List */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {DEMO_MARKET_FORECASTS.map((item) => {
            const isDeficit = item.balanceStatus.includes('Déficit');
            const isSurplus = item.balanceStatus.includes('Surproduction');

            return (
              <div
                key={item.id}
                className={cn(
                  "p-5 rounded-2xl border bg-surface flex flex-col justify-between space-y-4 shadow-xl",
                  isDeficit && "border-brand-500/40 bg-brand-950/10",
                  isSurplus && "border-alert-500/40 bg-alert-950/10",
                  !isDeficit && !isSurplus && "border-line"
                )}
              >
                <div>
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="text-[10px] font-mono text-earth-400 uppercase tracking-wider">
                        {item.category} · {item.season}
                      </span>
                      <h3 className="text-lg font-bold text-ink mt-0.5">{item.cropName}</h3>
                    </div>
                    <span
                      className={cn(
                        "px-2.5 py-1 text-xs font-bold rounded-lg border",
                        isDeficit && "bg-brand-500/20 text-brand-300 border-brand-500/30",
                        isSurplus && "bg-alert-500/20 text-alert-300 border-alert-500/30",
                        !isDeficit && !isSurplus && "bg-earth-800 text-earth-300 border-earth-700"
                      )}
                    >
                      {item.balanceStatus}
                    </span>
                  </div>

                  <p className="text-xs text-earth-300 mt-3 leading-relaxed">
                    {item.driverInsights}
                  </p>
                </div>

                <div className="bg-sunken p-3 rounded-xl border border-line grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <span className="text-[10px] text-earth-500">Demande Nationale</span>
                    <p className="font-mono font-bold text-ink mt-0.5">{formatNumber(item.nationalDemandTons)} T</p>
                  </div>
                  <div>
                    <span className="text-[10px] text-earth-500">Offre Projetée</span>
                    <p className="font-mono font-bold text-ink mt-0.5">{formatNumber(item.projectedSupplyTons)} T</p>
                  </div>
                  <div>
                    <span className="text-[10px] text-earth-500">Prix Attendu</span>
                    <p className="font-mono font-bold text-sun-300 mt-0.5">{formatCurrencyTND(item.projectedPriceTnd)}/kg</p>
                  </div>
                </div>

                <div className="flex items-center justify-between text-[11px] text-earth-400 pt-2 border-t border-line">
                  <span>Gouvernorats clés : {item.topProducingGovernorates.join(', ')}</span>
                  <span className="text-brand-400 font-mono">Indice Confiance {item.confidenceScore}%</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </AppShell>
  );
}
