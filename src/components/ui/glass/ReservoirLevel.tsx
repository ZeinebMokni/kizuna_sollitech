'use client';

import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';

interface ReservoirLevelProps {
  /** Fill level, 0–100. */
  percent: number;
  className?: string;
  label?: string;
}

// One wave period repeated twice so a -50% translate loops seamlessly.
const WAVE =
  'M0 6 Q 12.5 0 25 6 T 50 6 T 75 6 T 100 6 T 125 6 T 150 6 T 175 6 T 200 6 V 40 H 0 Z';

/**
 * Tank gauge: the water rises to `percent` on mount, and two offset waves
 * drift slowly on its surface (7 s / 11 s, ease-in-out).
 */
export function ReservoirLevel({ percent, className, label }: ReservoirLevelProps) {
  const reduce = useReducedMotion();
  const level = Math.max(0, Math.min(100, percent));

  return (
    <div
      className={className}
      role="img"
      aria-label={label ?? `Niveau du réservoir : ${level} %`}
    >
      <div className="relative h-full w-full overflow-hidden rounded-glass-sm bg-water-500/10 ring-1 ring-inset ring-water-500/20">
        <motion.div
          className="absolute inset-x-0 bottom-0"
          initial={reduce ? false : { height: '0%' }}
          animate={{ height: `${level}%` }}
          transition={{ duration: 1.6, ease: [0.22, 1, 0.36, 1], delay: 0.3 }}
        >
          {/* back wave */}
          <svg className="absolute -top-[7px] left-0 h-3 w-[200%] qa-wave-slow" viewBox="0 0 200 12" preserveAspectRatio="none" aria-hidden="true">
            <path d={WAVE} className="fill-water-500/35" />
          </svg>
          {/* front wave */}
          <svg className="absolute -top-[5px] left-0 h-3 w-[200%] qa-wave" viewBox="0 0 200 12" preserveAspectRatio="none" aria-hidden="true">
            <path d={WAVE} className="fill-water-500/70" />
          </svg>
          <div className="h-full w-full bg-gradient-to-b from-water-500/70 to-water-600/90" />
        </motion.div>
      </div>
    </div>
  );
}
