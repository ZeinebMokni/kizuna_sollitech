import type { Farm } from '@/types';
import type { LngLat, Parcel } from './types';
import { polygonsOverlap, openRing } from './geometry';

/**
 * Returns a description of the land a new outline would overlap, or null.
 * Registered parcels can never overlap. The demo farm's zones belong to the
 * farm owner, so only someone else is blocked from claiming them.
 */
export function findConflict(outline: LngLat[], parcels: Parcel[], farm: Farm, owner: string): string | null {
  for (const p of parcels) {
    if (polygonsOverlap(outline, p.polygon)) return `la parcelle ${p.id} (${p.ownerName})`;
  }
  if (owner.trim().toLowerCase() !== farm.ownerName.trim().toLowerCase()) {
    for (const z of farm.zones) {
      if (polygonsOverlap(outline, openRing(z.polygon.coordinates[0] as LngLat[]))) {
        return `${z.name.split(' - ')[0]} de ${farm.name} (${farm.ownerName})`;
      }
    }
  }
  return null;
}
