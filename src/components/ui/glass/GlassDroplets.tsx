'use client';

import React from 'react';
import { usePathname } from 'next/navigation';

/* ───────────────────────────── Tunable values ─────────────────────────────
 * DROPS        one entry per drop. Keep the scene sparse (≤ 5).
 *   x, y       position, % of the viewport (top-left corner of the drop box)
 *   width      drop width in px (height = width × DROP_ASPECT)
 *   rotate     resting tilt, degrees
 *   floatY     slow vertical float, px (negative = up)
 *   swayX      slow horizontal drift, px
 *   tilt       extra tilt reached at the end of the float, degrees
 *   duration   seconds per float (6–9); the loop mirrors, ease-in-out
 *   delay      seconds offset so drops never move in sync (negative = mid-cycle at load)
 *   shimmer    seconds per slow highlight shimmer
 *   scope      'public' = landing / login / onboarding (open background)
 *              'app'    = app pages, where the frosted UI covers most of the
 *                         screen: only drops in truly empty areas are kept
 * DROP_ASPECT  height / width of the teardrop (tail included)
 * REFRACTION   feDisplacementMap scale of the lens distortion
 * Glass card opacity, blur and border live in globals.css (search "Glass recipe").
 * ────────────────────────────────────────────────────────────────────────── */
type Drop = {
  x: number;
  y: number;
  width: number;
  rotate: number;
  floatY: number;
  swayX: number;
  tilt: number;
  duration: number;
  delay: number;
  shimmer: number;
  scope: 'public' | 'app';
};

const DROPS: Drop[] = [
  { x: 4, y: 9, width: 140, rotate: -7, floatY: -26, swayX: 12, tilt: 3, duration: 8, delay: -2, shimmer: 3.5, scope: 'public' },
  { x: 86, y: 22, width: 118, rotate: 6, floatY: -22, swayX: -10, tilt: -2.5, duration: 7, delay: -4.5, shimmer: 4.5, scope: 'public' },
  { x: 8, y: 58, width: 100, rotate: 4, floatY: -18, swayX: 9, tilt: -2, duration: 6, delay: -1, shimmer: 4, scope: 'public' },
  { x: 87, y: 60, width: 150, rotate: -5, floatY: -28, swayX: -12, tilt: 2.5, duration: 9, delay: -6, shimmer: 5, scope: 'public' },
  { x: 66, y: 12, width: 74, rotate: -4, floatY: -14, swayX: 7, tilt: 2, duration: 7, delay: -3, shimmer: 4, scope: 'app' },
];

const DROP_ASPECT = 1.5;
const REFRACTION = 9;
const PUBLIC_ROUTES = ['/', '/login', '/onboarding'];

/** Teardrop in a 100 × 150 box: thin pointed tail, full round body. */
const TEAR_PATH =
  'M50 7 C51.5 24 58 40 70 56 C84 73 92 88 92 104 C92 128 73 146 50 146 C27 146 8 128 8 104 C8 88 16 73 30 56 C42 40 48.5 24 50 7 Z';

/**
 * Fixed background layer: aqua gradient, 3 blurred colour blobs and a few
 * clear glass water drops floating slowly. Mounted once in layout.tsx behind
 * every page (z-index -1, pointer-events none, aria-hidden).
 * Motion is CSS (transform + highlight opacity only) and stops under
 * prefers-reduced-motion.
 */
export function GlassDroplets() {
  const pathname = usePathname() ?? '/';
  const scope = PUBLIC_ROUTES.includes(pathname) ? 'public' : 'app';
  const drops = DROPS.filter((d) => d.scope === scope);

  return (
    <div className="qa-water-bg" aria-hidden="true">
      <span className="qa-blob qa-blob-1" />
      <span className="qa-blob qa-blob-2" />
      <span className="qa-blob qa-blob-3" />

      <svg width="0" height="0" className="absolute">
        <defs>
          {/* unit-space clip for the HTML refraction layer */}
          <clipPath id="qa-tear-clip-unit" clipPathUnits="objectBoundingBox">
            <path d={TEAR_PATH} transform="scale(0.01 0.0066667)" />
          </clipPath>
          {/* user-space clip for the painted inner layers */}
          <clipPath id="qa-tear-clip">
            <path d={TEAR_PATH} />
          </clipPath>

          {/* faint body tint: clear centre, slightly denser water at the sides */}
          <linearGradient id="qa-tear-body" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="rgb(18 58 88)" stopOpacity="0.34" />
            <stop offset="14%" stopColor="rgb(60 112 148)" stopOpacity="0.14" />
            <stop offset="50%" stopColor="rgb(255 255 255)" stopOpacity="0.03" />
            <stop offset="86%" stopColor="rgb(60 112 148)" stopOpacity="0.16" />
            <stop offset="100%" stopColor="rgb(16 50 80)" stopOpacity="0.4" />
          </linearGradient>
          {/* the drop is a lens: the scene appears flipped — dark above, bright below */}
          <linearGradient id="qa-tear-lens" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgb(20 66 98)" stopOpacity="0.22" />
            <stop offset="42%" stopColor="rgb(40 96 130)" stopOpacity="0.12" />
            <stop offset="60%" stopColor="rgb(24 70 104)" stopOpacity="0.26" />
            <stop offset="82%" stopColor="rgb(255 255 255)" stopOpacity="0.32" />
            <stop offset="100%" stopColor="rgb(190 236 246)" stopOpacity="0.45" />
          </linearGradient>
          {/* light focused by the drop, pooling in the lower body */}
          <radialGradient id="qa-tear-caustic" cx="50%" cy="78%" r="40%">
            <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.7" />
            <stop offset="45%" stopColor="rgb(214 240 248)" stopOpacity="0.3" />
            <stop offset="100%" stopColor="rgb(214 240 248)" stopOpacity="0" />
          </radialGradient>

          {/* organic lens distortion (droplets only, never the page) */}
          <filter id="qa-tear-refract" x="-10%" y="-10%" width="120%" height="120%">
            <feTurbulence type="fractalNoise" baseFrequency="0.045" numOctaves="2" seed="11" result="noise" />
            <feDisplacementMap in="SourceGraphic" in2="noise" scale={REFRACTION} xChannelSelector="R" yChannelSelector="G" />
          </filter>
          <filter id="qa-tear-soft" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="0.7" />
          </filter>
          <filter id="qa-tear-softer" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="2.4" />
          </filter>
          <filter id="qa-tear-shadow" x="-40%" y="-300%" width="180%" height="700%">
            <feGaussianBlur stdDeviation="3.2" />
          </filter>
        </defs>
      </svg>

      {drops.map((d, i) => (
        <div
          key={i}
          className="qa-tear"
          style={
            {
              left: `${d.x}%`,
              top: `${d.y}%`,
              width: d.width,
              height: d.width * DROP_ASPECT,
              '--rot': `${d.rotate}deg`,
              '--rot-end': `${d.rotate + d.tilt}deg`,
              '--fy': `${d.floatY}px`,
              '--sx': `${d.swayX}px`,
              animationDuration: `${d.duration}s`,
              animationDelay: `${d.delay}s`,
            } as React.CSSProperties
          }
        >
          <span className="qa-tear-glass" />
          <TearDrop shimmer={d.shimmer} />
        </div>
      ))}
    </div>
  );
}

function TearDrop({ shimmer }: { shimmer: number }) {
  return (
    <svg viewBox="0 0 100 150" className="qa-tear-art">
      {/* shadow beneath, with the bright spot a real drop focuses into it */}
      <ellipse cx="55" cy="148" rx="30" ry="3.8" fill="rgb(18 52 72 / 0.22)" filter="url(#qa-tear-shadow)" />
      <ellipse cx="52" cy="147.5" rx="11" ry="1.8" fill="#FFFFFF" fillOpacity="0.55" filter="url(#qa-tear-soft)" />

      {/* faint body tint */}
      <path d={TEAR_PATH} fill="url(#qa-tear-body)" />

      <g clipPath="url(#qa-tear-clip)">
        {/* flipped, slightly distorted scene seen through the drop */}
        <rect x="0" y="0" width="100" height="150" fill="url(#qa-tear-lens)" filter="url(#qa-tear-refract)" />
        {/* focused light at the bottom */}
        <ellipse cx="52" cy="126" rx="30" ry="17" fill="url(#qa-tear-caustic)" />
        {/* dark refracted edge (total internal reflection) */}
        <path d={TEAR_PATH} fill="none" stroke="rgb(14 46 74 / 0.42)" strokeWidth="7" filter="url(#qa-tear-softer)" />
        {/* thin bright inner rim */}
        <path d={TEAR_PATH} fill="none" stroke="#FFFFFF" strokeOpacity="0.55" strokeWidth="1.6" filter="url(#qa-tear-soft)" />
      </g>

      {/* hairline outer edge */}
      <path d={TEAR_PATH} fill="none" stroke="rgb(16 52 80 / 0.32)" strokeWidth="0.8" />

      {/* highlights — shimmer very slowly, like light moving across water */}
      <g className="qa-tear-shine" style={{ animationDuration: `${shimmer}s` }}>
        <ellipse cx="31" cy="82" rx="9" ry="15" fill="#FFFFFF" fillOpacity="0.28" transform="rotate(24 31 82)" filter="url(#qa-tear-softer)" />
        {/* window-shaped specular reflection */}
        <rect x="26.5" y="71" width="8" height="15" rx="3.6" fill="#FFFFFF" fillOpacity="0.92" transform="rotate(24 30.5 78.5)" />
        <path d="M22 92 C18 104 20 116 27 124" fill="none" stroke="#FFFFFF" strokeOpacity="0.55" strokeWidth="2" strokeLinecap="round" filter="url(#qa-tear-soft)" />
        <path d="M77 110 C75 123 68 133 58 138" fill="none" stroke="#FFFFFF" strokeOpacity="0.6" strokeWidth="2" strokeLinecap="round" filter="url(#qa-tear-soft)" />
        <circle cx="64" cy="134" r="1.5" fill="#FFFFFF" />
        <path d="M49.4 15 C50 30 46.5 43 38 56" fill="none" stroke="#FFFFFF" strokeOpacity="0.6" strokeWidth="1.1" strokeLinecap="round" />
      </g>

      {/* bead at the tip of the tail */}
      <circle cx="50" cy="6" r="3.2" fill="rgb(120 180 210 / 0.25)" stroke="rgb(16 52 80 / 0.35)" strokeWidth="0.7" />
      <circle cx="49" cy="5" r="1" fill="#FFFFFF" />
    </svg>
  );
}
