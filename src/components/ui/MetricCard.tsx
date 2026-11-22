'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { AnimatedNumber } from './AnimatedNumber';
import { cn } from '@/lib/utils';

type Tone = 'brand' | 'water' | 'sun' | 'clay' | 'alert';

const TONES: Record<Tone, { chip: string; text: string; bar: string; glow: string; halo: string }> = {
  brand: { chip: 'from-brand-500 to-accent-deep', text: 'text-brand-400', bar: 'from-brand-500 to-water-500', glow: 'hover:shadow-brand-500/20', halo: 'bg-brand-500' },
  water: { chip: 'from-water-500 to-water-700', text: 'text-water-400', bar: 'from-water-500 to-brand-500', glow: 'hover:shadow-water-500/20', halo: 'bg-water-500' },
  sun: { chip: 'from-sun-500 to-clay-500', text: 'text-sun-400', bar: 'from-sun-500 to-clay-500', glow: 'hover:shadow-sun-500/20', halo: 'bg-sun-500' },
  clay: { chip: 'from-clay-500 to-alert-600', text: 'text-clay-400', bar: 'from-clay-500 to-sun-500', glow: 'hover:shadow-clay-500/20', halo: 'bg-clay-500' },
  alert: { chip: 'from-alert-500 to-clay-600', text: 'text-alert-400', bar: 'from-alert-500 to-clay-500', glow: 'hover:shadow-alert-500/20', halo: 'bg-alert-500' },
};

interface MetricCardProps {
  icon: React.ElementType;
  tone: Tone;
  label: string;
  value: number;
  decimals?: number;
  unit?: string;
  note?: string;
  /** 0-100 fill of the bottom gauge */
  progress?: number;
  pulse?: boolean;
}

/** KPI tile: gradient icon chip, count-up value, animated gauge, tinted halo. */
export function MetricCard({ icon: Icon, tone, label, value, decimals = 0, unit, note, progress, pulse }: MetricCardProps) {
  const t = TONES[tone];
  return (
    <div className={cn('qa-card group relative overflow-hidden rounded-2xl bg-surface border border-line p-4', t.glow)}>
      <span className={cn('pointer-events-none absolute -right-10 -top-10 h-28 w-28 rounded-full opacity-[0.12] blur-2xl transition-opacity duration-500 group-hover:opacity-25', t.halo)} />

      <div className="relative flex items-start justify-between gap-2">
        <span className="text-xs font-medium text-earth-400 leading-snug">{label}</span>
        <span className={cn('relative h-9 w-9 flex-shrink-0 rounded-xl bg-gradient-to-br flex items-center justify-center text-white shadow-md transition-transform duration-500 group-hover:scale-110 group-hover:-rotate-6', t.chip)}>
          <Icon className="h-4 w-4" />
          {pulse && <span className={cn('absolute inset-0 rounded-xl animate-ping opacity-30', t.halo)} />}
        </span>
      </div>

      <p className="relative mt-2 flex items-baseline gap-1.5">
        <AnimatedNumber value={value} decimals={decimals} className={cn('text-3xl font-black tracking-tight tabular-nums', tone === 'brand' ? 'text-ink' : t.text)} />
        {unit && <span className="text-xs font-medium text-earth-400">{unit}</span>}
      </p>

      {progress !== undefined && (
        <div className="relative mt-3 h-1.5 rounded-full bg-earth-800 overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            whileInView={{ width: `${Math.max(4, Math.min(100, progress))}%` }}
            viewport={{ once: true }}
            transition={{ duration: 1.3, ease: [0.16, 1, 0.3, 1], delay: 0.2 }}
            className={cn('h-full rounded-full bg-gradient-to-r', t.bar)}
          />
        </div>
      )}

      {note && <p className={cn('relative mt-2 text-xs font-medium', t.text)}>{note}</p>}
    </div>
  );
}
