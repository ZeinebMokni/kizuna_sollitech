'use client';

import React from 'react';
import Link from 'next/link';
import { motion, type Variants } from 'framer-motion';
import {
  Droplets,
  Sun,
  Sprout,
  ArrowRight,
  Map as MapIcon,
  Gauge,
  Radar,
  LineChart,
  Sparkles,
  CheckCircle2,
} from 'lucide-react';
import { ThemeToggle } from '@/components/layout/ThemeToggle';
import { BrandMark } from '@/components/ui/BrandMark';
import { AnimatedNumber } from '@/components/ui/AnimatedNumber';
import { cn } from '@/lib/utils';

const ease = [0.16, 1, 0.3, 1] as const;

const stagger: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.09, delayChildren: 0.1 } },
};
const rise: Variants = {
  hidden: { opacity: 0, y: 24 },
  show: { opacity: 1, y: 0, transition: { duration: 0.8, ease } },
};


const PILLARS = [
  {
    icon: Droplets,
    tone: 'water',
    title: "Sauvegarder l'Eau",
    text: "Des capteurs capacitifs reliés à l'ESP32 surveillent l'humidité du sol en continu. L'arrosage ne se déclenche qu'au strict besoin agronomique — jusqu'à 40% d'eau économisée.",
  },
  {
    icon: Sun,
    tone: 'sun',
    title: 'Énergie Solaire Fiable',
    text: "Pompes submersibles alimentées par le photovoltaïque et le stockage batterie. En cas de coupure du réseau national, l'exploitation reste 100% opérationnelle.",
  },
  {
    icon: Sprout,
    tone: 'brand',
    title: 'Agriculture & Marché',
    text: "L'IA analyse les pénuries nationales pour conseiller quoi planter et quand récolter, puis relie l'agriculteur directement aux grossistes et transformateurs.",
  },
] as const;

const FUNCTIONS = [
  {
    icon: Gauge,
    tone: 'clay',
    title: "Réduire l'eau et l'énergie",
    text: "Analyse du sol, de la météo et des pompes pour recommander les choix les plus sobres, et prédire le plan d'exploitation le plus performant.",
  },
  {
    icon: Radar,
    tone: 'water',
    title: "Suivre l'eau en temps réel",
    text: 'Capteurs d’humidité et de débit connectés : fuites et gaspillages détectés et signalés à la seconde.',
  },
  {
    icon: Droplets,
    tone: 'brand',
    title: 'La juste dose par zone',
    text: 'Plate, dense ou en pente : chaque parcelle reçoit la quantité d’eau optimale calculée à partir de ses propres capteurs.',
  },
  {
    icon: LineChart,
    tone: 'sun',
    title: 'Cultures & pénuries',
    text: 'Prédiction des fruits et légumes les plus adaptés à la période, et veille dynamique des ruptures alimentaires par région.',
  },
] as const;

const TONE: Record<string, { chip: string; glow: string; bar: string }> = {
  water: { chip: 'from-water-500 to-water-700', glow: 'hover:shadow-water-500/25', bar: 'bg-water-500' },
  sun: { chip: 'from-sun-500 to-clay-500', glow: 'hover:shadow-sun-500/25', bar: 'bg-sun-500' },
  brand: { chip: 'from-brand-500 to-accent-deep', glow: 'hover:shadow-brand-500/25', bar: 'bg-brand-500' },
  clay: { chip: 'from-clay-500 to-alert-600', glow: 'hover:shadow-clay-500/25', bar: 'bg-clay-500' },
};

export default function LandingPage() {
  return (
    <div className="relative min-h-screen text-earth-100 selection:bg-brand-500 selection:text-on-accent overflow-x-hidden">

      {/* ── NAVBAR — theme-aware QATRA glass ── */}
      <motion.nav
        initial={{ y: -24, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.7, ease }}
        className="glass-panel fixed top-3 left-3 right-3 z-50 mx-auto flex max-w-6xl items-center justify-between rounded-2xl px-5 py-3"
      >
        <Link href="/" className="flex items-center gap-3 group">
          <BrandMark size={36} className="transition-transform duration-500 group-hover:rotate-[-6deg]" />
          <div className="leading-none">
            <span className="text-base font-black tracking-[0.18em] text-ink">QATRA</span>
            <span className="text-[10px] text-brand-400 font-semibold block mt-0.5">Intelligence for Every Drop</span>
          </div>
        </Link>

        <div className="hidden md:flex items-center gap-0.5 text-sm font-medium">
          {[
            ['#fonctions', 'Fonctions'],
            ['#nexus', 'Le Nexus'],
            ['/farm/map', 'Jumeau Numérique'],
            ['/marketplace', 'Place de Marché'],
          ].map(([href, label]) => (
            <a
              key={href}
              href={href}
              className="rounded-lg px-3 py-1.5 text-sm text-earth-300 transition-colors hover:bg-highlight hover:text-ink"
            >
              {label}
            </a>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Link
            href="/login"
            className="hidden rounded-lg px-3 py-1.5 text-xs font-semibold text-earth-300 transition-colors hover:text-ink sm:block"
          >
            Connexion
          </Link>
          <Link
            href="/dashboard"
            className="qa-gradient-bg flex items-center gap-1.5 rounded-xl px-4 py-2 text-xs font-bold text-on-accent shadow-glass transition-all hover:-translate-y-0.5"
          >
            <span>Accéder au Démo</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </motion.nav>

      {/* ── HERO — full-viewport cinematic background ── */}
      <section
        className="relative isolate flex h-screen items-center overflow-hidden"
        style={{
          height: '100svh',
          backgroundColor: 'rgb(var(--canvas))',
        }}
      >
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 overflow-hidden"
        >
          <img
            src="/hero-agriculture.jpg"
            alt=""
            className="absolute inset-0 h-full w-full scale-110 object-cover"
            style={{
              filter: 'blur(28px) brightness(1.03) saturate(1.05)',
            }}
          />
        </div>
        <div
          className="absolute left-1/2 top-1/2 aspect-[1024/571] -translate-x-1/2 -translate-y-1/2"
          style={{
            width: 'min(100%, 179.3345svh)',
            WebkitMaskImage:
              'linear-gradient(to right, transparent 0%, black 7%, black 93%, transparent 100%), linear-gradient(to bottom, transparent 0px, black 24px, black calc(100% - 24px), transparent 100%)',
            maskImage:
              'linear-gradient(to right, transparent 0%, black 7%, black 93%, transparent 100%), linear-gradient(to bottom, transparent 0px, black 24px, black calc(100% - 24px), transparent 100%)',
            WebkitMaskComposite: 'source-in',
            maskComposite: 'intersect',
          }}
        >
          <img
            src="/hero-agriculture.jpg"
            alt=""
            aria-hidden="true"
            className="h-full w-full object-contain object-center"
          />
        </div>
        {/* Keep the photograph vivid; shade only the copy area for contrast. */}
        <div
          className="pointer-events-none absolute inset-y-0 left-0 w-full sm:w-[62%]"
          style={{
            background:
              'linear-gradient(90deg, rgb(var(--shade) / 0.48) 0%, rgb(var(--shade) / 0.3) 50%, transparent 100%)',
          }}
        />

        {/* Hero content — left-aligned */}
        <div className="relative z-10 w-full px-5 pt-20 pb-8 sm:px-10 lg:px-16">
          <motion.div
            variants={stagger}
            initial="hidden"
            animate="show"
            className="max-w-[500px]"
          >
            {/* Badge */}
            <motion.div
              variants={rise}
              className="mb-5 inline-flex max-w-full items-center gap-2 rounded-full px-3.5 py-1.5 text-[11px] font-semibold sm:mb-6 sm:text-xs"
              style={{
                background: 'var(--glass-bg-strong)',
                border: '1px solid var(--glass-border)',
                color: 'rgb(var(--brand-400))',
                backdropFilter: 'blur(var(--glass-blur)) saturate(var(--glass-saturate))',
              }}
            >
              <span className="qa-live-dot" />
              <span>Hackathon Kizuna 2026 · Deux Cultures, Un Seul Fil</span>
              <Sparkles className="h-3.5 w-3.5 shrink-0 text-sun-500" />
            </motion.div>

            {/* Headline — 3 lines, left-aligned */}
            <motion.h1
              variants={rise}
              className="font-black leading-[1.05] tracking-tight text-on-accent"
              style={{ fontSize: 'clamp(2rem, 4.2vw, 4rem)' }}
            >
              Your Farm.<br />
              Your Market.<br />
              <span className="qa-gradient-text">
                Your Future.
              </span>
            </motion.h1>

            {/* Turquoise accent underline */}
            <motion.div
              variants={rise}
              className="mt-2 h-0.5 w-20 rounded-full sm:mt-3 sm:w-24"
              style={{ background: 'linear-gradient(90deg, rgb(var(--brand-500)), transparent)' }}
            />

            {/* Description */}
            <motion.p
              variants={rise}
              className="mt-4 max-w-[440px] text-sm leading-relaxed text-on-accent/90 sm:mt-5 sm:text-base"
            >
              La plateforme intelligente pour une agriculture{' '}
              <strong className="font-semibold text-on-accent">sobre en eau et en énergie</strong>{' '}
              : capteurs connectés, IA prédictive et marché équitable, réunis pour les agriculteurs tunisiens.
            </motion.p>

            {/* CTA Buttons */}
            <motion.div
              variants={rise}
              className="mt-5 flex flex-col gap-2.5 sm:mt-6 sm:flex-row sm:flex-wrap sm:gap-3"
            >
              <Link
                href="/dashboard"
                className="qa-gradient-bg group inline-flex items-center justify-center gap-2 rounded-full px-5 py-3 text-center text-xs font-bold text-on-accent shadow-accent/30 transition-all hover:-translate-y-0.5 sm:px-6 sm:py-3.5 sm:text-sm"
                style={{
                  boxShadow: '0 6px 20px rgb(var(--accent) / 0.35)',
                }}
              >
                <span>Explorer la Plateforme en Direct</span>
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </Link>

              <Link
                href="/farm/map"
                className="glass-panel group inline-flex items-center justify-center gap-2 rounded-full px-5 py-3 text-center text-xs font-semibold text-ink transition-all hover:-translate-y-0.5 sm:px-6 sm:py-3.5 sm:text-sm"
              >
                <MapIcon className="h-4 w-4 text-accent" />
                <span>Ouvrir le Jumeau Numérique</span>
              </Link>
            </motion.div>

            {/* Feature chips */}
            <motion.div
              variants={rise}
              className="mt-5 hidden flex-wrap gap-x-5 gap-y-2 text-xs text-on-accent/80 lg:flex"
            >
              {['Capteurs ESP32 / LoRa', 'Imagerie Sentinel-2', 'IA prédictive', 'Pompage 100% solaire'].map((t) => (
                <span key={t} className="flex items-center gap-1.5">
                  <CheckCircle2 className="h-3.5 w-3.5 text-brand-500" /> {t}
                </span>
              ))}
            </motion.div>
          </motion.div>
        </div>

      </section>

      {/* Impact band */}
      <section className="relative z-10 px-6 py-14">
        <motion.div
          variants={stagger}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: '-80px' }}
          className="max-w-5xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-4"
        >
          {[
            { v: 40, s: '%', l: "d'eau économisée", c: 'text-water-500' },
            { v: 100, s: '%', l: 'pompage solaire', c: 'text-sun-500' },
            { v: 24, s: '/7', l: 'télémétrie capteurs', c: 'text-brand-500' },
            { v: 5, s: ' zones', l: 'irriguées sur mesure', c: 'text-clay-500' },
          ].map((m) => (
            <motion.div key={m.l} variants={rise} className="text-center p-5 rounded-2xl bg-surface/70 backdrop-blur ring-1 ring-line">
              <AnimatedNumber value={m.v} suffix={m.s} className={cn('text-4xl font-black tracking-tight', m.c)} />
              <p className="mt-1 text-xs font-medium text-earth-400">{m.l}</p>
            </motion.div>
          ))}
        </motion.div>
      </section>

      {/* Four functions (core idea) */}
      <section id="fonctions" className="relative z-10 py-20 px-6">
        <div className="max-w-6xl mx-auto">
          <SectionHeading
            eyebrow="Une seule plateforme"
            title="Produire plus, en consommant moins"
            text="Katra réunit quatre fonctions essentielles pour piloter une exploitation sobre, connectée et tournée vers le marché."
          />
          <motion.div
            variants={stagger}
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, margin: '-80px' }}
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5"
          >
            {FUNCTIONS.map((f, i) => (
              <FeatureCard key={f.title} index={i + 1} {...f} />
            ))}
          </motion.div>
        </div>
      </section>

      {/* Nexus */}
      <section id="nexus" className="relative z-10 py-20 px-6">
        <div className="max-w-5xl mx-auto">
          <SectionHeading
            eyebrow="Un défi, trois fils conducteurs"
            title="Le Nexus Eau · Énergie · Alimentation"
            text="L'été 2026 a été le plus chaud jamais enregistré en Tunisie. QATRA apporte une réponse intégrée, inspirée de l'ingénierie et de la philosophie japonaise Mottainai."
          />
          <motion.div
            variants={stagger}
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, margin: '-80px' }}
            className="grid grid-cols-1 md:grid-cols-3 gap-6"
          >
            {PILLARS.map((p) => (
              <FeatureCard key={p.title} {...p} />
            ))}
          </motion.div>
        </div>
      </section>

      {/* CTA */}
      <section className="relative z-10 px-6 pb-24">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.9, ease }}
          className="qa-gradient-bg relative mx-auto max-w-5xl overflow-hidden rounded-3xl px-8 py-14 text-center text-on-accent shadow-[0_30px_70px_-30px_rgb(var(--accent)/0.8)]"
        >
          <div className="absolute -top-24 -right-16 h-72 w-72 rounded-full bg-sun-500/40 blur-3xl" />
          <div className="absolute -bottom-24 -left-16 h-72 w-72 rounded-full bg-water-500/40 blur-3xl" />
          <div className="relative">
            <h3 className="text-3xl sm:text-4xl font-black tracking-tight">Chaque goutte compte.</h3>
            <p className="mx-auto mt-3 max-w-xl text-on-accent/80">
              Découvrez le jumeau numérique d'une exploitation réelle de Sidi Bouzid, pilotée en direct par QATRA.
            </p>
            <Link
              href="/dashboard"
              className="group mt-8 inline-flex items-center gap-2 px-7 py-4 rounded-2xl bg-white text-accent-deep font-bold text-sm shadow-xl transition-transform hover:-translate-y-0.5"
            >
              Lancer la démonstration
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </Link>
          </div>
        </motion.div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 py-10 px-6 border-t border-line bg-surface/60 backdrop-blur text-xs text-earth-400">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <BrandMark size={28} />
            <span>
              <span className="font-bold text-ink">QATRA</span> — Hackathon Kizuna 2026 (Esprit × Tunisie–Japon × JICA)
            </span>
          </div>
          <div className="flex gap-6">
            <Link href="/dashboard" className="hover:text-brand-400 transition-colors">Tableau de bord</Link>
            <Link href="/farm/map" className="hover:text-brand-400 transition-colors">Jumeau Numérique</Link>
            <Link href="/intelligence" className="hover:text-brand-400 transition-colors">Observatoire</Link>
            <Link href="/marketplace" className="hover:text-brand-400 transition-colors">Marché</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}

function SectionHeading({ eyebrow, title, text }: { eyebrow: string; title: string; text: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-60px' }}
      transition={{ duration: 0.8, ease }}
      className="text-center space-y-3 mb-14"
    >
      <span className="inline-block text-[11px] font-bold uppercase tracking-[0.2em] text-brand-400">{eyebrow}</span>
      <h2 className="text-3xl sm:text-4xl font-black tracking-tight text-ink">{title}</h2>
      <p className="text-sm sm:text-base text-earth-300 max-w-2xl mx-auto leading-relaxed">{text}</p>
    </motion.div>
  );
}

function FeatureCard({
  icon: Icon,
  tone,
  title,
  text,
  index,
}: {
  icon: React.ElementType;
  tone: string;
  title: string;
  text: string;
  index?: number;
}) {
  const t = TONE[tone];
  return (
    <motion.div
      variants={rise}
      className={cn(
        'group relative overflow-hidden rounded-3xl bg-surface/80 backdrop-blur p-6 ring-1 ring-line transition-[transform,box-shadow] duration-500 hover:-translate-y-1.5 hover:shadow-2xl',
        t.glow
      )}
    >
      <span className={cn('absolute inset-x-0 top-0 h-1 origin-left scale-x-0 transition-transform duration-500 group-hover:scale-x-100', t.bar)} />
      <div className="flex items-start justify-between">
        <div className={cn('flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br text-on-accent shadow-lg transition-transform duration-500 group-hover:scale-110 group-hover:-rotate-6', t.chip)}>
          <Icon className="h-6 w-6" />
        </div>
        {index && <span className="text-3xl font-black text-earth-700 tabular-nums">0{index}</span>}
      </div>
      <h3 className="mt-5 text-lg font-bold text-ink">{title}</h3>
      <p className="mt-2 text-sm text-earth-300 leading-relaxed">{text}</p>
    </motion.div>
  );
}
