import React from 'react';
import { cn } from '@/lib/utils';

type PanelRadius = 'none' | 'small' | 'card';

interface GlassPanelProps extends React.HTMLAttributes<HTMLElement> {
  as?: 'div' | 'aside' | 'header' | 'nav' | 'section';
  /** none = flush edges (sidebar, top bar), small = 16px (dropdowns, map panels), card = 24px (modals). */
  radius?: PanelRadius;
  reflect?: boolean;
}

const RADIUS: Record<PanelRadius, string> = {
  none: 'rounded-none',
  small: 'rounded-glass-sm',
  card: 'rounded-glass',
};

/**
 * Static frosted-glass surface for chrome and overlays: sidebar, top bar,
 * modals, dropdowns, tooltips and the floating digital-twin panels.
 * Uses the stronger glass tint so dense controls stay readable. No hover motion.
 */
export const GlassPanel = React.forwardRef<HTMLElement, GlassPanelProps>(function GlassPanel(
  { as: Tag = 'div', radius = 'small', reflect = false, className, children, ...rest },
  ref
) {
  return (
    <Tag
      ref={ref as React.Ref<HTMLDivElement>}
      className={cn('glass-panel', RADIUS[radius], reflect && 'relative isolate glass-reflect', className)}
      {...rest}
    >
      {children}
    </Tag>
  );
});
