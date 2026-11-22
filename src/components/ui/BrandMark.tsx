import React from 'react';
import { cn } from '@/lib/utils';

/** QATRA logo tile: leaf → lagoon gradient with a rising sun accent. */
export function BrandMark({ size = 40, className }: { size?: number; className?: string }) {
  return (
    <div
      className={cn(
        'relative flex-shrink-0 overflow-hidden rounded-xl qa-gradient-bg flex items-center justify-center shadow-lg shadow-accent/30 ring-1 ring-inset ring-white/20',
        className
      )}
      style={{ width: size, height: size }}
    >
      {/* sun */}
      <span
        className="absolute rounded-full bg-sun-500 shadow-[0_0_12px_rgb(var(--sun-500))]"
        style={{ width: size * 0.22, height: size * 0.22, top: size * 0.12, right: size * 0.12 }}
      />
      {/* gloss */}
      <span className="absolute inset-x-0 top-0 h-1/2 bg-gradient-to-b from-white/25 to-transparent" />
      <span className="relative font-black text-white tracking-tighter" style={{ fontSize: size * 0.48 }}>
        قط
      </span>
    </div>
  );
}

export function BrandWordmark({ subtitle, compact = false }: { subtitle?: string; compact?: boolean }) {
  return (
    <div className="flex flex-col leading-none">
      <span className={cn('font-black tracking-[0.18em] text-ink', compact ? 'text-base' : 'text-lg')}>QATRA</span>
      {subtitle && (
        <span className="mt-1 text-[10px] font-semibold tracking-wide text-brand-400">{subtitle}</span>
      )}
    </div>
  );
}
