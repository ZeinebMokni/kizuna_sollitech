import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(num: number, maximumFractionDigits = 1): string {
  return new Intl.NumberFormat('fr-TN', { maximumFractionDigits }).format(num);
}

export function formatCurrencyTND(amount: number): string {
  return new Intl.NumberFormat('fr-TN', {
    style: 'currency',
    currency: 'TND',
    minimumFractionDigits: 2,
    maximumFractionDigits: 3,
  }).format(amount);
}

export function formatPercent(ratio: number): string {
  return `${Math.round(ratio * 100)}%`;
}

export function getStatusColor(status: string): string {
  switch (status) {
    case 'healthy':
      return 'bg-brand-500/20 text-brand-400 border-brand-500/30';
    case 'warning':
      return 'bg-sun-500/20 text-sun-400 border-sun-500/30';
    case 'critical':
      return 'bg-alert-500/20 text-alert-400 border-alert-500/30';
    case 'irrigating':
      return 'bg-water-500/20 text-water-400 border-water-500/30 animate-pulse';
    default:
      return 'bg-earth-500/20 text-earth-400 border-earth-500/30';
  }
}
