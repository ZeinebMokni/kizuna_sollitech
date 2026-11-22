/**
 * Soil-moisture colour scale shared by the map zones and the legend.
 * Dry soil = coral, then sand, olive, mint, water blue, deep blue (well irrigated).
 * Colours are fixed (not theme tokens) because they sit on satellite imagery.
 */
export const MOISTURE_STOPS: { at: number; rgb: [number, number, number]; alpha: number }[] = [
  { at: 10, rgb: [214, 96, 72], alpha: 0.55 },
  { at: 22, rgb: [232, 160, 70], alpha: 0.48 },
  { at: 35, rgb: [190, 200, 110], alpha: 0.42 },
  { at: 50, rgb: [90, 190, 170], alpha: 0.44 },
  { at: 65, rgb: [45, 160, 215], alpha: 0.5 },
  { at: 85, rgb: [25, 110, 190], alpha: 0.58 },
];

/** Continuous colour for a moisture percentage (linear between stops). */
export function moistureColor(percent: number, alphaScale = 1): string {
  const stops = MOISTURE_STOPS;
  const m = Math.max(stops[0].at, Math.min(stops[stops.length - 1].at, percent));
  let i = 0;
  while (i < stops.length - 2 && m > stops[i + 1].at) i++;
  const a = stops[i];
  const b = stops[i + 1];
  const t = (m - a.at) / (b.at - a.at);
  const mix = (x: number, y: number) => Math.round(x + (y - x) * t);
  const alpha = (a.alpha + (b.alpha - a.alpha) * t) * alphaScale;
  return `rgba(${mix(a.rgb[0], b.rgb[0])}, ${mix(a.rgb[1], b.rgb[1])}, ${mix(a.rgb[2], b.rgb[2])}, ${alpha.toFixed(3)})`;
}

/** CSS linear-gradient of the scale, for legends. */
export function moistureGradientCss(): string {
  const first = MOISTURE_STOPS[0].at;
  const span = MOISTURE_STOPS[MOISTURE_STOPS.length - 1].at - first;
  const parts = MOISTURE_STOPS.map(
    (s) => `rgb(${s.rgb.join(' ')}) ${(((s.at - first) / span) * 100).toFixed(1)}%`
  );
  return `linear-gradient(90deg, ${parts.join(', ')})`;
}
