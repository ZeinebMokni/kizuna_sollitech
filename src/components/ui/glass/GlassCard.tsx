'use client';

import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { cn } from '@/lib/utils';

interface GlassCardProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Position in a group: entrance is staggered by 80 ms per index. */
  index?: number;
  /** Lift 3px + light sweep on hover. Default true. */
  interactive?: boolean;
  /** Subtle diagonal light reflection. Default true. */
  reflect?: boolean;
  /** 24px radius (default) or 16px for small elements. */
  size?: 'card' | 'small';
  /** Classes for the outer (grid item) wrapper. */
  wrapperClassName?: string;
}

/**
 * Frosted-glass card for KPI tiles.
 * Outer motion wrapper: fades in and rises 12px on mount (staggered 80 ms).
 * Inner glass surface: lifts 3px with a gentle light sweep on hover (CSS),
 * kept separate so framer-motion's inline transform never blocks the hover.
 * Text inside must use AA-safe tokens (`text-ink`, `text-earth-300`…).
 */
export function GlassCard({
  index = 0,
  interactive = true,
  reflect = true,
  size = 'card',
  className,
  wrapperClassName,
  children,
  ...rest
}: GlassCardProps) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1], delay: index * 0.08 }}
      className={cn('h-full', wrapperClassName)}
    >
      <div
        className={cn(
          'glass h-full',
          size === 'small' && 'rounded-glass-sm',
          interactive && 'glass-interactive',
          reflect && 'glass-reflect',
          className
        )}
        {...rest}
      >
        {children}
      </div>
    </motion.div>
  );
}
