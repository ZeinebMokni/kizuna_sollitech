'use client';

import React from 'react';
import { Zap, Sun, Battery, TrendingUp } from 'lucide-react';
import { DEMO_DEVICES, DEMO_ENERGY_TELEMETRY } from '@/lib/mockData';

export function SolarEnergyLegend() {
  const telemetry = DEMO_ENERGY_TELEMETRY;
  const inverter = DEMO_DEVICES.find((d) => d.type === 'solar_inverter');
  const battery = DEMO_DEVICES.find((d) => d.type === 'battery_bms');

  const pvKw = telemetry.solarProductionKw;
  const pumpKw = telemetry.pumpConsumptionKw;
  const socPct = telemetry.batterySoCPercent;
  const efficiency = inverter
    ? Math.round(((inverter.readings.efficiencyPercent as number) ?? 97))
    : 97;
  const dailyKwh = inverter
    ? (inverter.readings.dailyYieldKwh as number)
    : 76.4;

  const selfPowered = pumpKw > 0 ? Math.min(100, Math.round((pvKw / pumpKw) * 100)) : 100;

  return (
    <div
      className="glass-panel rounded-2xl border border-line overflow-hidden"
      style={{ minWidth: 220, maxWidth: 240 }}
    >
      {/* Header */}
      <div
        className="flex items-center gap-2 px-3.5 py-2.5"
        style={{
          background: 'linear-gradient(135deg, rgba(251,191,36,0.15) 0%, rgba(245,158,11,0.08) 100%)',
          borderBottom: '1px solid rgba(251,191,36,0.2)',
        }}
      >
        <div className="h-6 w-6 rounded-lg flex items-center justify-center bg-sun-500/20 border border-sun-400/30">
          <Sun className="h-3.5 w-3.5 text-sun-400" />
        </div>
        <div>
          <p className="text-[11px] font-bold text-sun-300 leading-tight">Énergie Solaire</p>
          <p className="text-[9px] text-earth-400 leading-tight">Système photovoltaïque 18.5 kWc</p>
        </div>
        {/* Live dot */}
        <div className="ml-auto flex items-center gap-1">
          <div className="h-1.5 w-1.5 rounded-full bg-green-400 animate-pulse" />
          <span className="text-[9px] text-green-400 font-semibold">LIVE</span>
        </div>
      </div>

      {/* Stats grid */}
      <div className="p-3 grid grid-cols-2 gap-2">
        {/* Production */}
        <div className="bg-sun-500/10 border border-sun-500/20 rounded-xl p-2.5">
          <div className="flex items-center gap-1 mb-1">
            <Zap className="h-3 w-3 text-sun-400" />
            <p className="text-[9px] text-earth-400">Production</p>
          </div>
          <p className="text-sm font-black text-sun-300" style={{ fontFamily: 'monospace' }}>
            {pvKw.toFixed(1)} <span className="text-[9px] font-normal text-earth-400">kW</span>
          </p>
        </div>

        {/* Battery SoC */}
        <div className="bg-brand-500/10 border border-brand-500/20 rounded-xl p-2.5">
          <div className="flex items-center gap-1 mb-1">
            <Battery className="h-3 w-3 text-brand-400" />
            <p className="text-[9px] text-earth-400">Batterie</p>
          </div>
          <p className="text-sm font-black text-brand-300" style={{ fontFamily: 'monospace' }}>
            {socPct} <span className="text-[9px] font-normal text-earth-400">%</span>
          </p>
        </div>

        {/* Rendement */}
        <div className="bg-water-500/10 border border-water-500/20 rounded-xl p-2.5">
          <div className="flex items-center gap-1 mb-1">
            <TrendingUp className="h-3 w-3 text-water-400" />
            <p className="text-[9px] text-earth-400">Rendement</p>
          </div>
          <p className="text-sm font-black text-water-300" style={{ fontFamily: 'monospace' }}>
            {efficiency} <span className="text-[9px] font-normal text-earth-400">%</span>
          </p>
        </div>

        {/* Daily yield */}
        <div className="bg-clay-500/10 border border-clay-500/20 rounded-xl p-2.5">
          <div className="flex items-center gap-1 mb-1">
            <Sun className="h-3 w-3 text-clay-400" />
            <p className="text-[9px] text-earth-400">Prod. jour</p>
          </div>
          <p className="text-sm font-black text-clay-300" style={{ fontFamily: 'monospace' }}>
            {dailyKwh} <span className="text-[9px] font-normal text-earth-400">kWh</span>
          </p>
        </div>
      </div>

      {/* Self-powered bar */}
      <div className="px-3 pb-3">
        <div className="flex items-center justify-between mb-1">
          <p className="text-[9px] text-earth-400">Auto-alimentation pompage</p>
          <p className="text-[9px] font-bold text-sun-300">{selfPowered}%</p>
        </div>
        <div className="h-2 rounded-full bg-earth-800 overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-1000"
            style={{
              width: `${selfPowered}%`,
              background: 'linear-gradient(90deg, #FBBF24 0%, #F59E0B 50%, #FCD34D 100%)',
              boxShadow: '0 0 8px rgba(251,191,36,0.6)',
            }}
          />
        </div>
      </div>

      {/* Legend key */}
      <div
        className="px-3 py-2.5 flex flex-col gap-1.5"
        style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}
      >
        <p className="text-[9px] text-earth-500 font-semibold uppercase tracking-wide mb-0.5">Légende</p>
        {[
          { color: '#FCD34D', label: 'Array Principal (8 kW)' },
          { color: '#60A5FA', label: 'Array secondaire (5 kW)' },
          { color: '#34D399', label: 'Tracker solaire (4 kW)' },
          { color: '#A78BFA', label: 'Array auxiliaire (1.5 kW)' },
        ].map((item) => (
          <div key={item.label} className="flex items-center gap-2">
            <div
              className="h-2.5 w-2.5 rounded-sm flex-shrink-0"
              style={{
                background: item.color,
                boxShadow: `0 0 4px ${item.color}80`,
              }}
            />
            <span className="text-[9px] text-earth-400">{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
