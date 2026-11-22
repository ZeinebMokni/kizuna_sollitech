'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { ThemeToggle } from '@/components/layout/ThemeToggle';
import { BrandMark } from '@/components/ui/BrandMark';
import { useRouter } from 'next/navigation';
import { ShieldCheck, ArrowRight, UserCheck, Sprout, Store, Award } from 'lucide-react';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('tarak.bensalem@elbaraka.tn');
  const [password, setPassword] = useState('••••••••••••');

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    router.push('/dashboard');
  };

  const handleDemoLogin = (role: string) => {
    router.push('/dashboard');
  };

  return (
    <div className="min-h-screen flex flex-col justify-center items-center px-4 py-12 relative overflow-hidden">
      <ThemeToggle className="absolute top-4 right-4 z-20" />

      {/* Background glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-brand-500/10 rounded-full blur-[140px] pointer-events-none" />

      <div className="max-w-md w-full bg-surface border border-line rounded-2xl p-8 shadow-2xl relative z-10">
        <div className="text-center mb-6">
          <Link href="/" className="inline-flex items-center gap-2 mb-3">
            <BrandMark size={44} />
            <span className="text-2xl font-black tracking-wider text-ink">QATRA</span>
          </Link>
          <h2 className="text-lg font-bold text-ink">Connexion à la Plateforme</h2>
          <p className="text-xs text-earth-400 mt-1">
            Système d'exploitation agricole intelligent pour la Tunisie
          </p>
        </div>

        {/* 1-Click Demo Profiles */}
        <div className="mb-6 bg-sunken p-3 rounded-xl border border-line">
          <span className="text-[10px] font-bold uppercase tracking-wider text-brand-400 block mb-2">
            Accès Démonstration Rapide (1 Clic)
          </span>
          <div className="space-y-1.5">
            <button
              onClick={() => handleDemoLogin('farmer')}
              className="w-full text-left px-3 py-2 rounded-lg bg-raised hover:bg-highlight border border-brand-500/20 text-xs text-ink flex items-center justify-between transition-colors"
            >
              <div className="flex items-center gap-2">
                <Sprout className="h-4 w-4 text-brand-400" />
                <div>
                  <p className="font-semibold">Tarak Ben Salem</p>
                  <p className="text-[10px] text-earth-400">Agriculteur · Sidi Bouzid (15.3 Ha)</p>
                </div>
              </div>
              <ArrowRight className="h-3.5 w-3.5 text-brand-400" />
            </button>

            <button
              onClick={() => handleDemoLogin('buyer')}
              className="w-full text-left px-3 py-2 rounded-lg bg-raised hover:bg-highlight border border-brand-500/20 text-xs text-ink flex items-center justify-between transition-colors"
            >
              <div className="flex items-center gap-2">
                <Store className="h-4 w-4 text-water-400" />
                <div>
                  <p className="font-semibold">Société Agro-Export Tunis</p>
                  <p className="text-[10px] text-earth-400">Acheteur Gros & Conditionneur</p>
                </div>
              </div>
              <ArrowRight className="h-3.5 w-3.5 text-water-400" />
            </button>
          </div>
        </div>

        {/* Regular Login Form */}
        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="text-xs text-earth-300 font-medium block mb-1">Adresse E-mail</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-sunken border border-line rounded-xl px-3.5 py-2.5 text-xs text-ink placeholder-earth-500 focus:outline-none focus:border-brand-500"
              required
            />
          </div>

          <div>
            <label className="text-xs text-earth-300 font-medium block mb-1">Mot de Passe</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-sunken border border-line rounded-xl px-3.5 py-2.5 text-xs text-ink placeholder-earth-500 focus:outline-none focus:border-brand-500"
              required
            />
          </div>

          <button
            type="submit"
            className="w-full py-3 rounded-xl bg-gradient-to-r from-accent to-accent-deep hover:from-accent-hover hover:to-accent-deep text-on-accent font-bold text-xs flex items-center justify-center gap-2 transition-all border border-brand-500/30 qa-shine"
          >
            <span>Se Connecter au Tableau de Bord</span>
            <ArrowRight className="h-4 w-4" />
          </button>
        </form>

        <div className="mt-6 text-center text-xs text-earth-400">
          Nouveau sur QATRA ?{' '}
          <Link href="/onboarding" className="text-brand-400 font-semibold hover:underline">
            Configurer mon exploitation
          </Link>
        </div>
      </div>
    </div>
  );
}
