import { isPointInPolygon } from '@/lib/geo/geodesic';
import type { LngLat, Parcel } from './types';

/** Removes a repeated closing point, if any. */
export function openRing(ring: LngLat[]): LngLat[] {
  if (ring.length > 1) {
    const a = ring[0];
    const b = ring[ring.length - 1];
    if (a[0] === b[0] && a[1] === b[1]) return ring.slice(0, -1);
  }
  return ring;
}

export function closeRing(ring: LngLat[]): LngLat[] {
  const open = openRing(ring);
  return open.length ? [...open, open[0]] : open;
}

function bbox(ring: LngLat[]) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const [x, y] of ring) {
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (x > maxX) maxX = x;
    if (y > maxY) maxY = y;
  }
  return { minX, minY, maxX, maxY };
}

function orient(a: LngLat, b: LngLat, c: LngLat) {
  return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
}

function segmentsCross(p1: LngLat, p2: LngLat, q1: LngLat, q2: LngLat) {
  const d1 = orient(q1, q2, p1);
  const d2 = orient(q1, q2, p2);
  const d3 = orient(p1, p2, q1);
  const d4 = orient(p1, p2, q2);
  return ((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) && ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0));
}

/** True when two simple polygons share any area (touching edges do not count). */
export function polygonsOverlap(a: LngLat[], b: LngLat[]): boolean {
  const A = openRing(a);
  const B = openRing(b);
  if (A.length < 3 || B.length < 3) return false;
  const ba = bbox(A);
  const bb = bbox(B);
  if (ba.maxX <= bb.minX || bb.maxX <= ba.minX || ba.maxY <= bb.minY || bb.maxY <= ba.minY) return false;
  for (let i = 0; i < A.length; i++) {
    const a1 = A[i];
    const a2 = A[(i + 1) % A.length];
    for (let j = 0; j < B.length; j++) {
      if (segmentsCross(a1, a2, B[j], B[(j + 1) % B.length])) return true;
    }
  }
  const centroid = (r: LngLat[]): LngLat => [r.reduce((s, p) => s + p[0], 0) / r.length, r.reduce((s, p) => s + p[1], 0) / r.length];
  return isPointInPolygon(centroid(A), B) || isPointInPolygon(centroid(B), A) || isPointInPolygon(A[0], B) || isPointInPolygon(B[0], A);
}

/* ── Shareable payload: lets a fiche open from a QR code / link even on a
      device that does not have the parcel in its local storage. ── */
type Payload = { i: string; n: string; o: string; c: string; m: string; a: number; g: string; d: string; t: string; s: string; p: number[][] };

function toBase64Url(text: string) {
  const b64 = typeof window === 'undefined' ? Buffer.from(text, 'utf8').toString('base64') : btoa(unescape(encodeURIComponent(text)));
  return b64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
function fromBase64Url(data: string) {
  const b64 = data.replace(/-/g, '+').replace(/_/g, '/');
  return decodeURIComponent(escape(atob(b64)));
}

export function encodeParcel(p: Parcel): string {
  const payload: Payload = {
    i: p.id, n: p.name, o: p.ownerName, c: p.cropType, m: p.irrigationMethod, a: p.areaHa,
    g: p.governorate, d: p.delegation, t: p.createdAt, s: p.source,
    p: p.polygon.map(([x, y]) => [Number(x.toFixed(5)), Number(y.toFixed(5))]),
  };
  return toBase64Url(JSON.stringify(payload));
}

export function decodeParcel(data: string): Parcel | null {
  try {
    const q = JSON.parse(fromBase64Url(data)) as Payload;
    if (!q.i || !Array.isArray(q.p) || q.p.length < 3) return null;
    const polygon = q.p.map(([x, y]) => [x, y] as LngLat);
    const center: LngLat = [polygon.reduce((s, c) => s + c[0], 0) / polygon.length, polygon.reduce((s, c) => s + c[1], 0) / polygon.length];
    return {
      id: q.i, name: q.n, ownerName: q.o, cropType: q.c, irrigationMethod: q.m, areaHa: q.a,
      governorate: q.g, delegation: q.d, createdAt: q.t, source: q.s === 'auto' ? 'auto' : 'rectangle',
      polygon, center,
    };
  } catch {
    return null;
  }
}

/** Public link to a parcel fiche (works from a QR code). */
export function parcelShareUrl(p: Parcel, origin: string): string {
  return `${origin}/parcelles/${encodeURIComponent(p.id)}?d=${encodeParcel(p)}`;
}
