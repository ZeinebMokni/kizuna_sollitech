"use client";

import { useState } from "react";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { zoneName } from "@/components/decision-card";
import { Card, ErrorNote, Loading, PageHeader, Provenance, Stat } from "@/components/ui";
import { type BalanceRow, useApi } from "@/lib/api";
import { useDay } from "@/lib/day";

export default function WaterBalance() {
  const { day } = useDay();
  const wb = useApi<Record<string, BalanceRow[]>>(`/api/water-balance?day=${day}`);
  const zones = wb.data ? Object.keys(wb.data.data) : [];
  const [zone, setZone] = useState("tomato-east");
  const rows = wb.data?.data[zone] ?? [];
  const last = rows[rows.length - 1];
  const stressedDays = rows.filter((r) => r.ks < 1).length;
  const chart = rows.map((r) => ({
    date: r.date.slice(5),
    depletion: r.dr_end_mm,
    raw: r.raw_mm,
    taw: r.taw_mm,
    irrigation: r.irrigation_gross_mm,
    rain: r.peff_mm,
  }));

  return (
    <>
      <PageHeader
        title="Root-zone water balance"
        lead="How much water the crop has used from the root zone (depletion). Above the readily available water line, the crop is stressed; at total available water, the soil is at wilting point. Modelled from weather (FAO-56), no sensors yet."
      />
      {wb.error && <ErrorNote message={wb.error} />}
      {wb.loading && <Loading what="water balance" />}
      {wb.data && (
        <div className="space-y-6">
          <div className="flex flex-wrap gap-2">
            {zones.map((z) => (
              <button
                key={z}
                onClick={() => setZone(z)}
                className={`rounded-md border px-3 py-1.5 text-sm ${z === zone ? "border-green-deep bg-green-deep text-white" : "border-line bg-surface"}`}
              >
                {zoneName(z)}
              </button>
            ))}
          </div>
          {last && (
            <div className="grid gap-4 md:grid-cols-4">
              <Card><Stat label="Depletion now" value={last.dr_end_mm.toFixed(1)} unit="mm" note={`stage: ${last.stage}`} /></Card>
              <Card><Stat label="Stress threshold (RAW)" value={last.raw_mm.toFixed(1)} unit="mm" /></Card>
              <Card><Stat label="Total available (TAW)" value={last.taw_mm.toFixed(1)} unit="mm" /></Card>
              <Card><Stat label="Days with stress" value={stressedDays} note={`of ${rows.length} days simulated`} /></Card>
            </div>
          )}
          <Card
            title={`${zoneName(zone)}: depletion vs thresholds`}
            subtitle={<>Season start to the day before {day}. Weather <Provenance dataClass="inferred" source="NASA POWER" />; past irrigation is a hypothetical 12 mm every 4 days.</>}
          >
            <div className="h-96">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chart} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
                  <CartesianGrid stroke="#e2ddd1" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={24} />
                  <YAxis tick={{ fontSize: 11 }} unit=" mm" width={60} />
                  <Tooltip formatter={(v) => (typeof v === "number" ? `${v.toFixed(1)} mm` : v)} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="irrigation" name="Irrigation (gross)" fill="#2f6f9f" barSize={3} />
                  <Bar dataKey="rain" name="Effective rain" fill="#8fb8d8" barSize={3} />
                  <Line dataKey="taw" name="Total available water" stroke="#a63a2b" dot={false} strokeDasharray="4 3" />
                  <Line dataKey="raw" name="Stress threshold (RAW)" stroke="#b5651d" dot={false} strokeDasharray="6 3" />
                  <Line dataKey="depletion" name="Root-zone depletion" stroke="#1f4d3a" dot={false} strokeWidth={2} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>
      )}
    </>
  );
}
