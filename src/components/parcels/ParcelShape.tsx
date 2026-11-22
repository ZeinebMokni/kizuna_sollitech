import React from 'react';
import type { LngLat } from '@/lib/parcels/types';
import { cn } from '@/lib/utils';

/** Small to-scale outline of a parcel (north up), for lists and the fiche. */
export function ParcelShape({ polygon, className }: { polygon: LngLat[]; className?: string }) {
  if (polygon.length < 3) return null;
  const lat0 = polygon[0][1];
  const k = Math.cos((lat0 * Math.PI) / 180);
  const pts = polygon.map(([x, y]) => [x * k, -y]);
  const xs = pts.map((p) => p[0]);
  const ys = pts.map((p) => p[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const span = Math.max(maxX - minX, maxY - minY) || 1;
  const pad = 8;
  const scale = (100 - 2 * pad) / span;
  const ox = pad + (100 - 2 * pad - (maxX - minX) * scale) / 2;
  const oy = pad + (100 - 2 * pad - (maxY - minY) * scale) / 2;
  const d = pts.map(([x, y], i) => `${i ? 'L' : 'M'}${(ox + (x - minX) * scale).toFixed(1)} ${(oy + (y - minY) * scale).toFixed(1)}`).join(' ') + ' Z';

  return (
    <svg viewBox="0 0 100 100" className={cn('block', className)} aria-hidden="true">
      <rect x="0" y="0" width="100" height="100" rx="12" className="fill-brand-950" />
      <path d={d} className="fill-brand-500/30 stroke-brand-500" strokeWidth="2" strokeLinejoin="round" />
    </svg>
  );
}
