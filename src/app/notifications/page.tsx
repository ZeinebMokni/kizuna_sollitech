'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import {
  Bell,
  ShieldAlert,
  Droplets,
  Sun,
  Store,
  CheckCircle2,
  Clock,
  ArrowRight,
  Filter
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { DEMO_NOTIFICATIONS } from '@/lib/mockData';
import { NotificationItem } from '@/types';
import { cn } from '@/lib/utils';

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<NotificationItem[]>(DEMO_NOTIFICATIONS);
  const [selectedFilter, setSelectedFilter] = useState<string>('all');

  const filteredNotifs = notifications.filter((n) => {
    if (selectedFilter === 'unread') return !n.read;
    if (selectedFilter === 'alert') return n.category === 'alert';
    if (selectedFilter === 'energy') return n.category === 'energy';
    if (selectedFilter === 'market') return n.category === 'market';
    return true;
  });

  const markAllRead = () => {
    setNotifications(notifications.map(n => ({ ...n, read: true })));
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-line gap-4">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-brand-400">
              Centre de Surveillance & Journal
            </span>
            <h1 className="text-2xl font-black text-ink">Alertes & Notifications</h1>
            <p className="text-xs text-earth-400 mt-0.5">
              Événements de terrain, seuils critiques de stress hydrique et opportunités commerciales
            </p>
          </div>

          <button
            onClick={markAllRead}
            className="px-3.5 py-2 rounded-xl bg-surface border border-line text-earth-300 hover:text-ink text-xs font-semibold qa-card"
          >
            Tout marquer comme lu
          </button>
        </div>

        {/* Filter Badges */}
        <div className="flex gap-2">
          {['all', 'unread', 'alert', 'energy', 'market'].map((f) => (
            <button
              key={f}
              onClick={() => setSelectedFilter(f)}
              className={cn(
                "px-3 py-1.5 rounded-xl text-xs font-medium transition-colors capitalize",
                selectedFilter === f
                  ? "bg-accent text-on-accent font-semibold"
                  : "bg-surface text-earth-400 border border-line hover:text-ink"
              )}
            >
              {f === 'all' && 'Tous les messages'}
              {f === 'unread' && 'Non lus'}
              {f === 'alert' && 'Alertes Eau'}
              {f === 'energy' && 'Énergie & Solaire'}
              {f === 'market' && 'Place de Marché'}
            </button>
          ))}
        </div>

        {/* Notifications List */}
        <div className="space-y-3">
          {filteredNotifs.map((item) => (
            <div
              key={item.id}
              className={cn(
                "p-4 rounded-2xl border transition-all flex items-start justify-between gap-4 bg-surface",
                item.severity === 'critical' && "border-alert-500/50 bg-alert-950/15",
                item.severity === 'warning' && "border-sun-500/40 bg-sun-950/10",
                item.severity === 'info' && "border-line",
                !item.read && "ring-1 ring-brand-500/30"
              )}
            >
              <div className="flex items-start gap-3">
                <div className={cn(
                  "h-10 w-10 rounded-xl flex items-center justify-center font-bold flex-shrink-0 mt-0.5",
                  item.severity === 'critical' && "bg-alert-500/20 text-alert-400 border border-alert-500/30",
                  item.severity === 'warning' && "bg-sun-500/20 text-sun-400 border border-sun-500/30",
                  item.severity === 'info' && "bg-water-500/20 text-water-400 border border-water-500/30",
                  item.severity === 'success' && "bg-brand-500/20 text-brand-400 border border-brand-500/30"
                )}>
                  {item.category === 'alert' && <ShieldAlert className="h-5 w-5" />}
                  {item.category === 'energy' && <Sun className="h-5 w-5" />}
                  {item.category === 'market' && <Store className="h-5 w-5" />}
                  {item.category === 'irrigation' && <Droplets className="h-5 w-5" />}
                </div>

                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="text-sm font-bold text-ink">{item.title}</h4>
                    {!item.read && (
                      <span className="h-2 w-2 rounded-full bg-brand-400 animate-pulse" />
                    )}
                  </div>
                  <p className="text-xs text-earth-300 mt-1 leading-relaxed">{item.message}</p>
                  <span className="text-[10px] text-earth-500 font-mono mt-2 block">{item.timestamp}</span>
                </div>
              </div>

              {item.actionUrl && (
                <Link
                  href={item.actionUrl}
                  className="px-3 py-1.5 rounded-xl bg-raised hover:bg-highlight text-brand-300 text-xs font-semibold border border-brand-500/30 flex items-center gap-1 flex-shrink-0"
                >
                  <span>Agir</span>
                  <ArrowRight className="h-3 w-3" />
                </Link>
              )}
            </div>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
