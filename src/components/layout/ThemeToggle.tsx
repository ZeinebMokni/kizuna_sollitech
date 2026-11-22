'use client';

import React, { useEffect, useState } from 'react';
import { Sun, Moon } from 'lucide-react';
import { cn } from '@/lib/utils';

type Theme = 'light' | 'dark';
const STORAGE_KEY = 'qatra-theme';

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  root.classList.add('theme-transition');
  root.classList.toggle('dark', theme === 'dark');
  window.setTimeout(() => root.classList.remove('theme-transition'), 350);
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    /* storage unavailable — theme still applies for this session */
  }
}

export function ThemeToggle({ className, showLabel = false }: { className?: string; showLabel?: boolean }) {
  const [theme, setTheme] = useState<Theme>('light');

  useEffect(() => {
    setTheme(document.documentElement.classList.contains('dark') ? 'dark' : 'light');
  }, []);

  const toggle = () => {
    const next: Theme = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    applyTheme(next);
  };

  const isDark = theme === 'dark';

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={isDark ? 'Passer au thème clair' : 'Passer au thème sombre'}
      title={isDark ? 'Thème clair' : 'Thème sombre'}
      className={cn(
        'relative inline-flex items-center gap-1.5 rounded-full border border-line bg-surface p-0.5 text-[11px] font-semibold text-earth-300 transition-colors hover:border-line-strong',
        className
      )}
    >
      <span
        className={cn(
          'flex h-6 w-6 items-center justify-center rounded-full transition-all duration-300',
          !isDark ? 'bg-sun-500 text-on-accent shadow-sm shadow-shade/20' : 'text-earth-400'
        )}
      >
        <Sun className="h-3.5 w-3.5" />
      </span>
      <span
        className={cn(
          'flex h-6 w-6 items-center justify-center rounded-full transition-all duration-300',
          isDark ? 'bg-accent text-on-accent shadow-sm shadow-shade/20' : 'text-earth-400'
        )}
      >
        <Moon className="h-3.5 w-3.5" />
      </span>
      {showLabel && <span className="pr-2">{isDark ? 'Sombre' : 'Clair'}</span>}
    </button>
  );
}
