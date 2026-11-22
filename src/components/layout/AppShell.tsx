'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  LayoutDashboard,
  Map as MapIcon,
  Cpu,
  Droplets,
  Sun,
  Globe2,
  TrendingUp,
  Brain,
  BarChart3,
  Store,
  Tag,
  Bell,
  Settings,
  Menu,
  X,
  BatteryCharging,
  ShieldAlert,
  Radio,
  ChevronRight,
  Layers,
  LandPlot,
  Power,
} from 'lucide-react';
import { useLanguageStore } from '@/stores/useLanguageStore';
import { useFarmStore } from '@/stores/useFarmStore';
import { DEMO_NOTIFICATIONS, DEMO_ENERGY_TELEMETRY } from '@/lib/mockData';
import { cn, formatNumber } from '@/lib/utils';
import { ThemeToggle } from './ThemeToggle';
import { BrandMark } from '@/components/ui/BrandMark';
import { GlassPanel } from '@/components/ui/glass';

interface AppShellProps {
  children: React.ReactNode;
}

const EASE_OUT = [0.22, 1, 0.36, 1] as const;

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const { language, direction, setLanguage, t } = useLanguageStore();
  const {
    farm,
    isPowerOutage,
    togglePowerOutage,
    emergencyStopActive,
    toggleEmergencyStop,
    isSimulating,
    toggleSimulation,
    tickSimulation,
  } = useFarmStore();

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [notifDropdownOpen, setNotifDropdownOpen] = useState(false);
  const [emergencyModalOpen, setEmergencyModalOpen] = useState(false);

  // Simulation timer
  useEffect(() => {
    const interval = setInterval(() => {
      tickSimulation();
    }, 2000);
    return () => clearInterval(interval);
  }, [tickSimulation]);

  const navItems = [
    { label: t('nav.dashboard'), href: '/dashboard', icon: LayoutDashboard },
    { label: t('nav.digital_twin'), href: '/farm/map', icon: MapIcon, badge: 'Flagship' },
    { label: t('nav.farm'), href: '/farm', icon: Layers },
    { label: t('nav.my_lands'), href: '/parcelles', icon: LandPlot },
    { label: t('nav.devices'), href: '/farm/devices', icon: Cpu },
    { label: t('nav.irrigation'), href: '/farm/irrigation', icon: Droplets },
    { label: t('nav.energy'), href: '/farm/energy', icon: Sun },
    { label: t('nav.intelligence'), href: '/intelligence', icon: Globe2 },
    { label: t('nav.forecast'), href: '/intelligence/forecast', icon: TrendingUp },
    { label: t('nav.planning'), href: '/planning', icon: Brain, badge: 'IA' },
    { label: t('nav.analytics'), href: '/analytics', icon: BarChart3 },
    { label: t('nav.marketplace'), href: '/marketplace', icon: Store },
    { label: t('nav.my_listings'), href: '/marketplace/listings', icon: Tag },
    { label: t('nav.notifications'), href: '/notifications', icon: Bell, badgeCount: DEMO_NOTIFICATIONS.filter(n => !n.read).length },
    { label: t('nav.settings'), href: '/settings', icon: Settings },
  ];

  const unreadAlerts = DEMO_NOTIFICATIONS.filter(n => !n.read);

  // Live quick metrics from store / telemetry (no hard-coded values)
  const dailyWaterM3 = farm.zones.reduce((sum, z) => sum + z.dailyWaterLiters, 0) / 1000;
  const solarKw = DEMO_ENERGY_TELEMETRY.solarProductionKw;
  const batteryPct = DEMO_ENERGY_TELEMETRY.batterySoCPercent;

  return (
    <div className={cn("relative h-screen flex flex-col overflow-hidden text-earth-100", direction === 'rtl' ? 'font-arabic' : 'font-sans')}>

      {/* Status strip: context + simulation controls + safety */}
      <header className="relative z-40 px-4 pt-3 text-xs flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2.5 text-earth-300">
          <span className="px-2.5 py-1 rounded-full glass-panel font-semibold text-ink flex items-center gap-2">
            <span className="qa-live-dot !h-1.5 !w-1.5 !bg-water-500" />
            KIZUNA 2026 · Tunisie × Japon
          </span>
          <span className="hidden md:inline">
            Eau · Énergie · Alimentation <span className="text-earth-600 mx-1">|</span> {farm.name}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Simulation Status */}
          <button
            onClick={toggleSimulation}
            className={cn(
              "px-3 py-1 rounded-full text-[11px] font-medium flex items-center gap-1.5 transition-colors duration-200 glass-panel",
              isSimulating ? "text-water-400" : "text-earth-400"
            )}
            title="Activer/Pause flux de télémétrie simulé"
          >
            <Radio className="h-3 w-3" />
            {isSimulating ? 'Télémétrie Live' : 'Simulation en Pause'}
          </button>

          {/* Grid Outage Simulation Button */}
          <button
            onClick={togglePowerOutage}
            className={cn(
              "px-3 py-1 rounded-full text-[11px] font-medium flex items-center gap-1.5 transition-colors duration-200",
              isPowerOutage
                ? "bg-sun-900 text-sun-300 ring-1 ring-inset ring-sun-500/50"
                : "glass-panel text-earth-300 hover:text-ink"
            )}
            title="Simuler une coupure du réseau électrique national"
          >
            <Power className="h-3 w-3" />
            {isPowerOutage ? 'Réseau STEG COUPÉ (Secours Solaire Actif)' : 'Réseau STEG Connecté'}
          </button>

          {/* Emergency Stop: calm by default, soft pulse only while ACTIVE */}
          <button
            onClick={() => setEmergencyModalOpen(true)}
            className={cn(
              "px-3 py-1 rounded-full text-[11px] font-bold uppercase tracking-wider flex items-center gap-1.5 transition-colors duration-200",
              emergencyStopActive
                ? "bg-alert-600 text-on-accent animate-pulse"
                : "glass-panel text-alert-400 ring-1 ring-inset ring-alert-500/40 hover:bg-alert-950"
            )}
          >
            <ShieldAlert className="h-3.5 w-3.5" />
            {emergencyStopActive ? 'ARRÊT D\'URGENCE ACTIF' : 'Arrêt d\'Urgence'}
          </button>
        </div>
      </header>

      {/* Main Container */}
      <div className="relative z-10 flex flex-1 min-h-0">
        {/* Desktop Sidebar — floating glass panel */}
        <GlassPanel
          as="aside"
          radius="card"
          className={cn(
            "hidden md:flex flex-col m-3 me-0 transition-[width] duration-300 ease-out-soft select-none z-30 overflow-hidden",
            sidebarOpen ? "w-64" : "w-20"
          )}
        >
          {/* Logo & Brand */}
          <div className="p-4 flex items-center justify-between border-b border-line/70">
            <Link href="/" className="flex items-center gap-2.5 overflow-hidden">
              <BrandMark size={40} />
              {sidebarOpen && (
                <div className="flex flex-col leading-none">
                  <span className="text-lg font-black tracking-[0.18em] text-ink">QATRA</span>
                  <span className="text-[10px] text-earth-400 font-semibold tracking-tight mt-1">
                    Système d'Exploitation Agricole
                  </span>
                </div>
              )}
            </Link>
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              aria-label={sidebarOpen ? 'Réduire la barre latérale' : 'Déployer la barre latérale'}
              className="p-1.5 rounded-lg text-earth-400 hover:text-ink hover:bg-highlight/60 transition-colors"
            >
              <Menu className="h-5 w-5" />
            </button>
          </div>

          {/* Nav List */}
          <nav className="flex-1 overflow-y-auto p-3 space-y-1">
            {navItems.map((item) => {
              const active = pathname === item.href;
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  title={sidebarOpen ? undefined : item.label}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors duration-200 relative isolate",
                    active ? "text-on-accent" : "text-earth-300 hover:bg-white/40 dark:hover:bg-white/5 hover:text-ink"
                  )}
                >
                  {active && (
                    <motion.span
                      layoutId="qa-nav-active"
                      className="absolute inset-0 -z-10 rounded-xl bg-accent shadow-[0_8px_20px_-10px_rgb(var(--accent)/0.6)]"
                      transition={{ duration: 0.35, ease: EASE_OUT }}
                    />
                  )}
                  <Icon className={cn("h-5 w-5 flex-shrink-0", active ? "text-on-accent" : "text-water-400")} />
                  {sidebarOpen && <span className="flex-1 truncate">{item.label}</span>}

                  {sidebarOpen && item.badge && (
                    <span className={cn(
                      "px-1.5 py-0.5 text-[10px] font-semibold rounded-md",
                      active ? "bg-white/20 text-on-accent" : "bg-water-500/10 text-water-400"
                    )}>
                      {item.badge}
                    </span>
                  )}
                  {sidebarOpen && item.badgeCount !== undefined && item.badgeCount > 0 && (
                    <span className="px-1.5 py-0.5 text-[10px] font-bold rounded-full bg-alert-600 text-on-accent">
                      {item.badgeCount}
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>

          {/* Bottom Profile / Quick Info */}
          {sidebarOpen ? (
            <div className="p-3 border-t border-line/70">
              <div className="flex items-center gap-3 p-2 rounded-glass-sm bg-white/30 dark:bg-white/5">
                <div className="relative h-9 w-9 rounded-full bg-accent flex items-center justify-center font-bold text-on-accent text-xs">
                  TB
                  <span className="absolute -bottom-0.5 -end-0.5 h-2.5 w-2.5 rounded-full bg-brand-500 ring-2 ring-surface" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-semibold text-ink truncate">{farm.ownerName}</p>
                  <p className="text-[11px] text-earth-400 truncate">{farm.governorate} · {formatNumber(farm.totalAreaHa)} ha</p>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-3 border-t border-line/70 flex justify-center">
              <div className="h-8 w-8 rounded-full bg-accent flex items-center justify-center font-bold text-on-accent text-xs">
                TB
              </div>
            </div>
          )}
        </GlassPanel>

        {/* Content Wrapper */}
        <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
          {/* Top navigation bar — glass */}
          <GlassPanel
            radius="small"
            className="h-14 mx-3 mt-3 px-4 flex items-center justify-between sticky top-3 z-20"
          >
            {/* Mobile hamburger & breadcrumb */}
            <div className="flex items-center gap-3">
              <button
                onClick={() => setMobileMenuOpen(true)}
                aria-label="Ouvrir le menu"
                className="md:hidden p-2 rounded-lg text-earth-300 hover:text-ink"
              >
                <Menu className="h-5 w-5" />
              </button>
              <div className="hidden sm:flex items-center gap-2 text-xs text-earth-400">
                <Link href="/dashboard" className="hover:text-water-400">QATRA</Link>
                <ChevronRight className="h-3 w-3 rtl:rotate-180" />
                <span className="text-ink font-medium capitalize">
                  {pathname.split('/')[1] || 'Accueil'}
                </span>
              </div>
            </div>

            {/* Quick Metrics & Settings */}
            <div className="flex items-center gap-3">
              <div className="hidden lg:flex items-center gap-4 text-xs font-medium text-earth-300 pe-1">
                <span className="flex items-center gap-1.5">
                  <Sun className="h-3.5 w-3.5 text-sun-400" />
                  <span className="tabular-nums">{formatNumber(solarKw)} kW</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <Droplets className="h-3.5 w-3.5 text-water-400" />
                  <span className="tabular-nums">{formatNumber(dailyWaterM3)} m³</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <BatteryCharging className="h-3.5 w-3.5 text-brand-400" />
                  <span className="tabular-nums">{batteryPct} %</span>
                </span>
              </div>

              <ThemeToggle />

              {/* Language Switcher */}
              <div className="flex items-center gap-0.5 p-1 rounded-xl bg-white/30 dark:bg-white/5 ring-1 ring-inset ring-line/60">
                {(['fr', 'ar', 'en'] as const).map((lang) => (
                  <button
                    key={lang}
                    onClick={() => setLanguage(lang)}
                    className={cn(
                      "px-2 py-0.5 text-xs font-semibold rounded-lg uppercase transition-colors duration-200",
                      language === lang ? "bg-accent text-on-accent" : "text-earth-400 hover:text-ink"
                    )}
                  >
                    {lang}
                  </button>
                ))}
              </div>

              {/* Notifications */}
              <div className="relative">
                <button
                  onClick={() => setNotifDropdownOpen(!notifDropdownOpen)}
                  aria-label="Notifications"
                  className="p-2 rounded-xl bg-white/30 dark:bg-white/5 ring-1 ring-inset ring-line/60 text-earth-300 hover:text-ink relative transition-colors"
                >
                  <Bell className="h-4 w-4" />
                  {unreadAlerts.length > 0 && (
                    <span className="absolute -top-1 -end-1 h-4 w-4 bg-alert-600 rounded-full text-[10px] font-bold text-on-accent flex items-center justify-center">
                      {unreadAlerts.length}
                    </span>
                  )}
                </button>

                {notifDropdownOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: -6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.25, ease: EASE_OUT }}
                    className="absolute end-0 mt-3 w-80 z-50"
                  >
                    <GlassPanel radius="small" className="p-3">
                      <div className="flex items-center justify-between pb-2 border-b border-line/70">
                        <span className="text-xs font-bold text-ink">Notifications Récentes</span>
                        <Link
                          href="/notifications"
                          onClick={() => setNotifDropdownOpen(false)}
                          className="text-[11px] text-water-400 hover:underline"
                        >
                          Voir tout
                        </Link>
                      </div>
                      <div className="divide-y divide-line/70 max-h-64 overflow-y-auto mt-2">
                        {DEMO_NOTIFICATIONS.slice(0, 3).map((n) => (
                          <div key={n.id} className="py-2 text-xs">
                            <p className="font-semibold text-ink">{n.title}</p>
                            <p className="text-[11px] text-earth-300 mt-0.5">{n.message}</p>
                            <span className="text-[11px] text-earth-400 font-mono mt-1 block">{n.timestamp}</span>
                          </div>
                        ))}
                      </div>
                    </GlassPanel>
                  </motion.div>
                )}
              </div>
            </div>
          </GlassPanel>

          {/* Child Page Rendering */}
          <main className="flex-1 p-4 md:p-6">
            <motion.div
              key={pathname}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, ease: EASE_OUT }}
            >
              {children}
            </motion.div>
          </main>
        </div>
      </div>

      {/* Emergency Stop Confirmation Modal */}
      {emergencyModalOpen && (
        <div className="fixed inset-0 bg-earth-900/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <motion.div
            initial={{ opacity: 0, y: 12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.35, ease: EASE_OUT }}
            className="max-w-md w-full"
          >
            <GlassPanel radius="card" reflect className="p-6 text-center">
              <div className="h-16 w-16 mx-auto rounded-full bg-alert-500/15 ring-1 ring-inset ring-alert-500/40 flex items-center justify-center text-alert-400 mb-4">
                <ShieldAlert className="h-8 w-8" />
              </div>
              <h3 className="text-lg font-bold text-ink mb-2">
                {emergencyStopActive ? "Désactiver l'Arrêt d'Urgence ?" : "CONFIRMATION ARRÊT D'URGENCE"}
              </h3>
              <p className="text-sm text-earth-300 mb-6">
                {emergencyStopActive
                  ? "La sécurité d'urgence est actuellement enclenchée. Les pompes et vannes étaient bloquées. Êtes-vous sûr de vouloir réautoriser les opérations d'irrigation ?"
                  : "Cette action physique coupe instantanément toutes les vannes électromagnétiques et arrête la pompe solaire 7.5kW pour protéger l'aquifère et le matériel."}
              </p>
              <div className="flex gap-3">
                <button
                  onClick={() => setEmergencyModalOpen(false)}
                  className="flex-1 py-2.5 rounded-xl bg-white/40 dark:bg-white/5 ring-1 ring-inset ring-line text-xs font-semibold text-earth-200 hover:bg-white/60 dark:hover:bg-white/10 transition-colors"
                >
                  Annuler
                </button>
                <button
                  onClick={() => {
                    toggleEmergencyStop();
                    setEmergencyModalOpen(false);
                  }}
                  className={cn(
                    "flex-1 py-2.5 rounded-xl text-xs font-bold text-on-accent transition-colors duration-200",
                    emergencyStopActive ? "bg-accent hover:bg-accent-hover" : "bg-alert-600 hover:bg-alert-700"
                  )}
                >
                  {emergencyStopActive ? "Réactiver le Système" : "DÉCLENCHER L'ARRÊT"}
                </button>
              </div>
            </GlassPanel>
          </motion.div>
        </div>
      )}

      {/* Mobile Drawer Menu */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 bg-earth-900/40 backdrop-blur-sm z-50 md:hidden flex">
          <GlassPanel radius="none" className="w-72 h-full p-4 flex flex-col justify-between overflow-y-auto">
            <div>
              <div className="flex items-center justify-between pb-4 border-b border-line/70">
                <div className="flex items-center gap-2">
                  <BrandMark size={32} />
                  <span className="font-bold text-ink tracking-wider">QATRA</span>
                </div>
                <button onClick={() => setMobileMenuOpen(false)} aria-label="Fermer le menu" className="text-earth-400">
                  <X className="h-5 w-5" />
                </button>
              </div>
              <nav className="mt-4 space-y-1">
                {navItems.map((item) => {
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setMobileMenuOpen(false)}
                      className={cn(
                        "flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium",
                        pathname === item.href ? "bg-accent text-on-accent" : "text-earth-300 hover:bg-white/40 dark:hover:bg-white/5"
                      )}
                    >
                      <Icon className="h-4 w-4" />
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
              </nav>
            </div>
          </GlassPanel>
          <div className="flex-1" onClick={() => setMobileMenuOpen(false)} />
        </div>
      )}
    </div>
  );
}
