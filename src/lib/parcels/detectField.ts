import type { LngLat } from './types';

/* ───────────────────────────── Tunable values ─────────────────────────────
 * ZOOM            satellite zoom used for detection (16 ≈ 1.9 m per pixel in Tunisia)
 * GRID            tiles per side loaded around the click (3 → ~1.4 km square)
 * BLUR_RADIUS     smoothing in px: hides crop rows, keeps paths and field edges
 * EDGE_STEPS      edge strengths tried as field boundaries, strongest first; among
 *                 field-sized results, the most stable one (area changes least
 *                 between neighbouring steps) is kept — a real field is well enclosed
 * COLOR_LIMIT     colour distance from the clicked spot that is still the same field
 * OPEN_RADIUS     px; cuts thin "leaks" through gaps in a boundary
 * MIN_AREA_HA / MAX_AREA_HA  realistic size of a single field
 * SIMPLIFY_PX     outline simplification tolerance; MAX_VERTICES caps corners
 * ────────────────────────────────────────────────────────────────────────── */
const ZOOM = 16;
const GRID = 3;
const TILE = 256;
const BLUR_RADIUS = 3;
const EDGE_STEPS = [14, 11, 9, 7.5, 6.5, 5.5, 4.7, 4, 3.4, 2.9, 2.5, 2.2, 1.9];
const COLOR_LIMIT = 34;
const OPEN_RADIUS = 2;
const MIN_AREA_HA = 0.8;
const MAX_AREA_HA = 30;
const SIZE_PENALTY = 0.004; // per hectare, when choosing between stable outlines
const SIMPLIFY_PX = 3.5;
const MAX_VERTICES = 12;
const TILE_URL = (z: number, x: number, y: number) =>
  `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${z}/${y}/${x}`;

export class FieldDetectionError extends Error {}

const worldSize = TILE * 2 ** ZOOM;
const lngToX = (lng: number) => ((lng + 180) / 360) * worldSize;
const latToY = (lat: number) => {
  const r = (lat * Math.PI) / 180;
  return ((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * worldSize;
};
const xToLng = (x: number) => (x / worldSize) * 360 - 180;
const yToLat = (y: number) => (Math.atan(Math.sinh(Math.PI * (1 - (2 * y) / worldSize))) * 180) / Math.PI;

function loadImage(src: string) {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => resolve(img);
    img.onerror = () => reject(new FieldDetectionError("Impossible de charger l'image satellite. Vérifiez la connexion internet."));
    img.src = src;
  });
}

/** Separable box blur on an RGB float buffer. */
function boxBlur(src: Float32Array, w: number, h: number, r: number) {
  const tmp = new Float32Array(src.length);
  const out = new Float32Array(src.length);
  const span = 2 * r + 1;
  for (let y = 0; y < h; y++) {
    for (let c = 0; c < 3; c++) {
      let acc = 0;
      for (let k = -r; k <= r; k++) acc += src[(y * w + Math.min(w - 1, Math.max(0, k))) * 3 + c];
      for (let x = 0; x < w; x++) {
        tmp[(y * w + x) * 3 + c] = acc / span;
        const add = Math.min(w - 1, x + r + 1);
        const sub = Math.max(0, x - r);
        acc += src[(y * w + add) * 3 + c] - src[(y * w + sub) * 3 + c];
      }
    }
  }
  for (let x = 0; x < w; x++) {
    for (let c = 0; c < 3; c++) {
      let acc = 0;
      for (let k = -r; k <= r; k++) acc += tmp[(Math.min(h - 1, Math.max(0, k)) * w + x) * 3 + c];
      for (let y = 0; y < h; y++) {
        out[(y * w + x) * 3 + c] = acc / span;
        const add = Math.min(h - 1, y + r + 1);
        const sub = Math.max(0, y - r);
        acc += tmp[(add * w + x) * 3 + c] - tmp[(sub * w + x) * 3 + c];
      }
    }
  }
  return out;
}

/** Morphological erode / dilate with a square kernel. */
function morph(mask: Uint8Array, w: number, h: number, r: number, erode: boolean) {
  const tmp = new Uint8Array(mask.length);
  const out = new Uint8Array(mask.length);
  const pick = erode ? Math.min : Math.max;
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++) {
      let v = erode ? 1 : 0;
      for (let k = -r; k <= r; k++) {
        const xx = Math.min(w - 1, Math.max(0, x + k));
        v = pick(v, mask[y * w + xx]);
      }
      tmp[y * w + x] = v;
    }
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++) {
      let v = erode ? 1 : 0;
      for (let k = -r; k <= r; k++) {
        const yy = Math.min(h - 1, Math.max(0, y + k));
        v = pick(v, tmp[yy * w + x]);
      }
      out[y * w + x] = v;
    }
  return out;
}

/** Keeps only the 4-connected component containing the seed. */
function componentFrom(mask: Uint8Array, w: number, h: number, seed: number) {
  const out = new Uint8Array(mask.length);
  if (!mask[seed]) return { mask: out, count: 0 };
  const stack = [seed];
  out[seed] = 1;
  let count = 0;
  while (stack.length) {
    const i = stack.pop()!;
    count++;
    const x = i % w;
    const y = (i - x) / w;
    const nb = [x > 0 ? i - 1 : -1, x < w - 1 ? i + 1 : -1, y > 0 ? i - w : -1, y < h - 1 ? i + w : -1];
    for (const j of nb) if (j >= 0 && mask[j] && !out[j]) { out[j] = 1; stack.push(j); }
  }
  return { mask: out, count };
}

/** Index of the nearest set pixel to (x, y) within r px, or -1. */
function nearestSet(mask: Uint8Array, w: number, h: number, x: number, y: number, r: number) {
  for (let d = 0; d <= r; d++)
    for (let dy = -d; dy <= d; dy++)
      for (let dx = -d; dx <= d; dx++) {
        if (Math.max(Math.abs(dx), Math.abs(dy)) !== d) continue;
        const xx = x + dx, yy = y + dy;
        if (xx >= 0 && yy >= 0 && xx < w && yy < h && mask[yy * w + xx]) return yy * w + xx;
      }
  return -1;
}

function convexHull(points: [number, number][]) {
  const pts = points.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cross = (o: number[], a: number[], b: number[]) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lower: [number, number][] = [];
  for (const p of pts) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) lower.pop();
    lower.push(p);
  }
  const upper: [number, number][] = [];
  for (let i = pts.length - 1; i >= 0; i--) {
    const p = pts[i];
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) upper.pop();
    upper.push(p);
  }
  return lower.slice(0, -1).concat(upper.slice(0, -1));
}

/** Drops hull corners that deviate less than `tol` px from the line through their neighbours. */
function simplifyClosed(ring: [number, number][], tol: number, maxVertices: number) {
  let pts = ring.slice();
  const deviation = (i: number) => {
    const a = pts[(i - 1 + pts.length) % pts.length];
    const b = pts[i];
    const c = pts[(i + 1) % pts.length];
    const len = Math.hypot(c[0] - a[0], c[1] - a[1]) || 1;
    return Math.abs((c[0] - a[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (c[1] - a[1])) / len;
  };
  while (pts.length > 4) {
    let minI = 0;
    let minD = Infinity;
    for (let i = 0; i < pts.length; i++) {
      const d = deviation(i);
      if (d < minD) { minD = d; minI = i; }
    }
    if (minD > tol && pts.length <= maxVertices) break;
    pts = pts.filter((_, i) => i !== minI);
  }
  return pts;
}

/**
 * Detects the agricultural field under a clicked point from satellite imagery:
 * region-grows from the click over similar colours, stops at strong edges
 * (paths, hedges, ditches, crop changes), cleans the shape and returns its
 * outline as an open ring of [lng, lat].
 */
export async function detectFieldAt(point: LngLat): Promise<LngLat[]> {
  const gx = lngToX(point[0]);
  const gy = latToY(point[1]);
  const tx0 = Math.floor(gx / TILE) - Math.floor(GRID / 2);
  const ty0 = Math.floor(gy / TILE) - Math.floor(GRID / 2);
  const W = GRID * TILE;
  const H = GRID * TILE;

  const canvas = document.createElement('canvas');
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  if (!ctx) throw new FieldDetectionError('Le navigateur ne permet pas la détection automatique.');

  const jobs: Promise<void>[] = [];
  for (let dy = 0; dy < GRID; dy++)
    for (let dx = 0; dx < GRID; dx++)
      jobs.push(loadImage(TILE_URL(ZOOM, tx0 + dx, ty0 + dy)).then((img) => ctx.drawImage(img, dx * TILE, dy * TILE)));
  await Promise.all(jobs);

  let data: Uint8ClampedArray;
  try {
    data = ctx.getImageData(0, 0, W, H).data;
  } catch {
    throw new FieldDetectionError("L'image satellite ne peut pas être analysée sur ce navigateur.");
  }

  const rgb = new Float32Array(W * H * 3);
  for (let i = 0; i < W * H; i++) {
    rgb[i * 3] = data[i * 4];
    rgb[i * 3 + 1] = data[i * 4 + 1];
    rgb[i * 3 + 2] = data[i * 4 + 2];
  }
  const blur = boxBlur(rgb, W, H, BLUR_RADIUS);

  // Edge strength (Sobel on the smoothed luminance)
  const lum = new Float32Array(W * H);
  for (let i = 0; i < W * H; i++) lum[i] = 0.299 * blur[i * 3] + 0.587 * blur[i * 3 + 1] + 0.114 * blur[i * 3 + 2];
  const edge = new Float32Array(W * H);
  for (let y = 1; y < H - 1; y++)
    for (let x = 1; x < W - 1; x++) {
      const i = y * W + x;
      const gxv = lum[i - W + 1] + 2 * lum[i + 1] + lum[i + W + 1] - lum[i - W - 1] - 2 * lum[i - 1] - lum[i + W - 1];
      const gyv = lum[i + W - 1] + 2 * lum[i + W] + lum[i + W + 1] - lum[i - W - 1] - 2 * lum[i - W] - lum[i - W + 1];
      edge[i] = Math.hypot(gxv, gyv) / 4;
    }

  const sx = Math.round(gx - tx0 * TILE);
  const sy = Math.round(gy - ty0 * TILE);

  // Seed colour = mean of a 9×9 window around the click
  let mr = 0, mg = 0, mb = 0, n = 0;
  for (let y = sy - 4; y <= sy + 4; y++)
    for (let x = sx - 4; x <= sx + 4; x++) {
      const i = (y * W + x) * 3;
      mr += blur[i]; mg += blur[i + 1]; mb += blur[i + 2]; n++;
    }
  mr /= n; mg /= n; mb /= n;

  const metresPerPx = (40075016.686 * Math.cos((point[1] * Math.PI) / 180)) / worldSize;
  const pxPerHa = 10000 / (metresPerPx * metresPerPx);
  const minPx = MIN_AREA_HA * pxPerHa;
  const maxPx = MAX_AREA_HA * pxPerHa;

  // Colour gate: pixels clearly different from the clicked spot are never part of the field.
  const sameColour = new Uint8Array(W * H);
  const c2 = COLOR_LIMIT * COLOR_LIMIT;
  for (let i = 0; i < W * H; i++) {
    const dr = blur[i * 3] - mr;
    const dg = blur[i * 3 + 1] - mg;
    const db = blur[i * 3 + 2] - mb;
    sameColour[i] = dr * dr + dg * dg + db * db <= c2 ? 1 : 0;
  }

  // Edge-bounded fill at decreasing boundary strengths. A real field stays
  // enclosed over several steps, so keep the most stable field-sized result.
  const results: { area: number; mask: Uint8Array }[] = [];
  for (const e of EDGE_STEPS) {
    const open = new Uint8Array(W * H);
    for (let i = 0; i < W * H; i++) open[i] = sameColour[i] && edge[i] < e ? 1 : 0;
    const eroded = morph(open, W, H, OPEN_RADIUS, true);
    const start = nearestSet(eroded, W, H, sx, sy, 8);
    if (start < 0) break;
    const comp = componentFrom(eroded, W, H, start);
    const filled = morph(comp.mask, W, H, OPEN_RADIUS, false);
    let area = 0;
    for (let i = 0; i < filled.length; i++) area += filled[i];
    if (area < minPx) break; // boundaries now cut inside the field
    results.push({ area, mask: filled });
  }

  let best: Uint8Array | null = null;
  let bestArea = 0;
  let bestScore = Infinity;
  results.forEach((r, i) => {
    if (r.area > maxPx) return;
    const next = results[i + 1];
    const prev = results[i - 1];
    const change = next ? Math.abs(r.area - next.area) / r.area : prev ? Math.abs(prev.area - r.area) / prev.area : 1;
    // slight preference for the tighter outline when two results are almost as stable
    const score = change + SIZE_PENALTY * (r.area / pxPerHa);
    if (score < bestScore) {
      bestScore = score;
      best = r.mask;
      bestArea = r.area;
    }
  });

  if (!best) throw new FieldDetectionError("Aucun champ net détecté à cet endroit. Cliquez au milieu d'une parcelle, ou utilisez le rectangle.");
  if (bestArea < minPx) throw new FieldDetectionError("Le champ détecté est trop petit. Cliquez au milieu d'une parcelle, ou utilisez le rectangle.");

  // Boundary pixels → convex hull → simplified outline
  const boundary: [number, number][] = [];
  for (let y = 1; y < H - 1; y++)
    for (let x = 1; x < W - 1; x++) {
      const i = y * W + x;
      if (best[i] && (!best[i - 1] || !best[i + 1] || !best[i - W] || !best[i + W])) boundary.push([x, y]);
    }
  const hull = simplifyClosed(convexHull(boundary), SIMPLIFY_PX, MAX_VERTICES);
  if (hull.length < 3) throw new FieldDetectionError('Contour du champ introuvable. Utilisez le rectangle.');

  return hull.map(([x, y]) => [
    Number(xToLng(tx0 * TILE + x).toFixed(6)),
    Number(yToLat(ty0 * TILE + y).toFixed(6)),
  ] as LngLat);
}
