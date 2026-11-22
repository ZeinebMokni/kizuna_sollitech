'use client';

import React, { useState } from 'react';
import {
  Settings,
  Globe2,
  Cpu,
  ShieldCheck,
  Save,
  CheckCircle2,
  Radio,
  Sliders,
  Server
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { useLanguageStore } from '@/stores/useLanguageStore';
import { Language } from '@/types';
import { cn } from '@/lib/utils';

export default function SettingsPage() {
  const { language, setLanguage } = useLanguageStore();
  const [mqttBroker, setMqttBroker] = useState('mqtt://broker.qatra.tn:8883');
  const [loraChannel, setLoraChannel] = useState('868.1 MHz (Tunisie / Europe)');
  const [saved, setSaved] = useState(false);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  return (
    <AppShell>
      <div className="space-y-6 max-w-4xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-line gap-4">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-brand-400">
              Configuration du Système
            </span>
            <h1 className="text-2xl font-black text-ink">Paramètres & Passerelles Matérielles</h1>
            <p className="text-xs text-earth-400 mt-0.5">
              Langues, protocoles de communication IoT (MQTT/LoRa) et sécurités agronomiques
            </p>
          </div>

          <button
            onClick={handleSave}
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-accent to-accent-deep hover:from-accent-hover text-on-accent font-bold text-xs flex items-center gap-2 border border-brand-500/30 qa-shine"
          >
            <Save className="h-4 w-4" />
            <span>{saved ? 'Modifications Enregistrées !' : 'Enregistrer les Paramètres'}</span>
          </button>
        </div>

        {/* Language & Regionalization */}
        <div className="bg-surface border border-line p-5 rounded-2xl space-y-4 shadow-xl qa-card">
          <div className="flex items-center gap-2 pb-2 border-b border-line">
            <Globe2 className="h-4 w-4 text-brand-400" />
            <h3 className="text-sm font-bold text-ink">Langue de l'Interface & Typographie</h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {[
              { id: 'fr', label: 'Français', desc: 'Langue par défaut (Hackathon Kizuna 2026)' },
              { id: 'ar', label: 'العربية (RTL)', desc: 'Support complet de l\'arabe et de l\'orientation droite-à-gauche' },
              { id: 'en', label: 'English', desc: 'International agricultural specification' },
            ].map((item) => (
              <button
                key={item.id}
                onClick={() => setLanguage(item.id as Language)}
                className={cn(
                  "p-4 rounded-xl border text-left transition-all",
                  language === item.id
                    ? "bg-raised border-brand-500 shadow-lg shadow-shade/20"
                    : "bg-sunken border-line text-earth-400 hover:text-ink"
                )}
              >
                <p className="font-bold text-ink text-sm">{item.label}</p>
                <p className="text-[11px] text-earth-400 mt-1">{item.desc}</p>
              </button>
            ))}
          </div>
        </div>

        {/* IoT & ESP32 Telemetry Gateway Settings */}
        <div className="bg-surface border border-line p-5 rounded-2xl space-y-4 shadow-xl qa-card">
          <div className="flex items-center gap-2 pb-2 border-b border-line">
            <Server className="h-4 w-4 text-water-400" />
            <h3 className="text-sm font-bold text-ink">Connexion Passerelle ESP32 & Broker MQTT</h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div>
              <label className="text-earth-300 font-semibold block mb-1">Serveur / Broker MQTT Sécurisé</label>
              <input
                type="text"
                value={mqttBroker}
                onChange={(e) => setMqttBroker(e.target.value)}
                className="w-full bg-sunken border border-line rounded-xl px-3 py-2 text-ink font-mono focus:outline-none focus:border-brand-500"
              />
            </div>

            <div>
              <label className="text-earth-300 font-semibold block mb-1">Fréquence LoRa Régionale</label>
              <input
                type="text"
                value={loraChannel}
                onChange={(e) => setLoraChannel(e.target.value)}
                className="w-full bg-sunken border border-line rounded-xl px-3 py-2 text-ink font-mono focus:outline-none focus:border-brand-500"
              />
            </div>
          </div>

          <div className="p-3 bg-sunken rounded-xl border border-brand-500/20 text-xs text-earth-300 flex items-center gap-2">
            <Radio className="h-4 w-4 text-brand-400 animate-pulse flex-shrink-0" />
            <span>Passerelle active : Microcontrôleur ESP32-S3 station Sidi Bouzid A1 appairé avec 5 nœuds parcellaires.</span>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
