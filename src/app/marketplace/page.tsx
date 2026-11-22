'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import {
  Store,
  Tag,
  Search,
  Filter,
  MapPin,
  Calendar,
  ShieldCheck,
  ArrowRight,
  MessageSquare,
  Sparkles,
  Check
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { DEMO_LISTINGS } from '@/lib/mockData';
import { ProductListing } from '@/types';
import { cn, formatNumber, formatCurrencyTND } from '@/lib/utils';

export default function MarketplacePage() {
  const [listings, setListings] = useState<ProductListing[]>(DEMO_LISTINGS);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedGovernorate, setSelectedGovernorate] = useState('all');
  const [inquirySentId, setInquirySentId] = useState<string | null>(null);

  const filteredListings = listings.filter((l) => {
    const matchesSearch = l.cropName.toLowerCase().includes(searchQuery.toLowerCase()) || l.farmerName.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesGov = selectedGovernorate === 'all' || l.governorate === selectedGovernorate;
    return matchesSearch && matchesGov;
  });

  const handleSendInquiry = (id: string) => {
    setInquirySentId(id);
    setTimeout(() => setInquirySentId(null), 3000);
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-line gap-4">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-brand-400">
              Circuits Courts & Valorisation Directe (Kizuna)
            </span>
            <h1 className="text-2xl font-black text-ink">Place de Marché Agricole QATRA</h1>
            <p className="text-xs text-earth-400 mt-0.5">
              Connexion directe entre producteurs tunisiens et transformateurs, grossistes & exportateurs
            </p>
          </div>

          <Link
            href="/marketplace/listings"
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-accent to-accent-deep hover:from-accent-hover text-on-accent font-bold text-xs flex items-center gap-2 border border-brand-500/30 qa-shine"
          >
            <Tag className="h-4 w-4" />
            <span>Publier une Récolte</span>
          </Link>
        </div>

        {/* Search & Filter Bar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-surface p-3 rounded-2xl border border-line qa-card">
          <div className="relative w-full sm:w-80">
            <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-earth-400" />
            <input
              type="text"
              placeholder="Rechercher par culture, variété, producteur..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-sunken border border-line rounded-xl pl-9 pr-3 py-2 text-xs text-ink placeholder-earth-500 focus:outline-none focus:border-brand-500"
            />
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <select
              value={selectedGovernorate}
              onChange={(e) => setSelectedGovernorate(e.target.value)}
              className="bg-sunken border border-line rounded-xl px-3 py-2 text-xs text-ink focus:outline-none focus:border-brand-500"
            >
              <option value="all">Tous les gouvernorats</option>
              <option value="Sidi Bouzid">Sidi Bouzid</option>
              <option value="Kairouan">Kairouan</option>
              <option value="Sfax">Sfax</option>
              <option value="Nabeul">Nabeul</option>
              <option value="Bizerte">Bizerte</option>
            </select>
          </div>
        </div>

        {/* Listings Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredListings.map((item) => (
            <div
              key={item.id}
              className="p-5 rounded-2xl border border-line bg-surface flex flex-col justify-between space-y-4 shadow-xl hover:border-brand-500/40 transition-all qa-card"
            >
              <div>
                <div className="flex items-start justify-between">
                  <div>
                    <span className="text-[10px] font-mono text-brand-400 font-semibold flex items-center gap-1">
                      <MapPin className="h-3 w-3" /> {item.governorate} · {item.farmName}
                    </span>
                    <h3 className="text-lg font-bold text-ink mt-1">{item.cropName}</h3>
                    <p className="text-xs text-earth-400">{item.variety}</p>
                  </div>
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-brand-500/20 text-brand-300 border border-brand-500/30">
                    {item.qualityGrade}
                  </span>
                </div>

                <p className="text-xs text-earth-300 mt-3 leading-relaxed">
                  {item.description}
                </p>

                <div className="flex flex-wrap gap-1.5 mt-3">
                  {item.certifications.map((cert, i) => (
                    <span key={i} className="px-2 py-0.5 rounded bg-sunken text-[10px] text-earth-400 border border-line">
                      {cert}
                    </span>
                  ))}
                </div>
              </div>

              <div className="pt-3 border-t border-line space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <div>
                    <span className="text-[10px] text-earth-500 block">Quantité Disponible</span>
                    <span className="font-mono font-bold text-ink">{formatNumber(item.quantityKg)} kg</span>
                  </div>

                  <div className="text-right">
                    <span className="text-[10px] text-earth-500 block">Prix Demandé</span>
                    <span className="font-mono font-black text-sun-300 text-sm">
                      {formatCurrencyTND(item.askingPriceTndKg)}/kg
                    </span>
                  </div>
                </div>

                <button
                  onClick={() => handleSendInquiry(item.id)}
                  className="w-full py-2.5 rounded-xl bg-gradient-to-r from-accent to-accent-deep hover:from-accent-hover hover:to-accent-deep text-on-accent font-bold text-xs flex items-center justify-center gap-1.5 transition-all border border-brand-500/30 qa-shine"
                >
                  {inquirySentId === item.id ? (
                    <>
                      <Check className="h-4 w-4" />
                      <span>Demande d'Achat Envoyée !</span>
                    </>
                  ) : (
                    <>
                      <MessageSquare className="h-4 w-4" />
                      <span>Contacter le Producteur ({item.inquiryCount} offres)</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
