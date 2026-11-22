"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { DAY_MAX, DAY_MIN, useDay } from "@/lib/day";
import { type Envelope, type FarmSummary, useSelectedFarm } from "@/lib/api";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/decisions", label: "Decisions" },
  { href: "/schedule", label: "Irrigation schedule" },
  { href: "/water", label: "Water balance" },
  { href: "/crops", label: "Crop suitability" },
  { href: "/climate", label: "Climate 2050" },
  { href: "/anomalies", label: "Water anomalies" },
  { href: "/assistant", label: "Assistant" },
];

export function Shell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const { day, setDay } = useDay();
  const { farmId, setFarmId } = useSelectedFarm();
  const [farms, setFarms] = useState<FarmSummary[]>([]);
  useEffect(() => {
    fetch("/api/farms")
      .then((r) => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then((body: Envelope<FarmSummary[]>) => setFarms(body.data))
      .catch(() => setFarms([]));
  }, []);
  const selected = farms.find((f) => f.farm_id === farmId);
  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <aside className="border-b border-line bg-green-deep text-white md:w-60 md:shrink-0 md:border-b-0">
        <div className="px-5 py-5">
          <p className="text-xl font-semibold tracking-tight">QATRA</p>
          <p className="text-xs text-emerald-100/80">Water decision support</p>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:overflow-visible">
          {NAV.map((n) => {
            const active = n.href === "/" ? path === "/" : path.startsWith(n.href);
            return (
              <Link
                key={n.href}
                href={n.href}
                className={`whitespace-nowrap rounded-md px-3 py-2 text-sm ${active ? "bg-white/15 font-medium" : "text-emerald-50/85 hover:bg-white/10"}`}
              >
                {n.label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="border-b border-amber-200 bg-amber-50 px-6 py-2 text-xs text-amber-950">
          <strong>{selected?.kind === "demo" ? "Demo farm." : "Real-farm profile."}</strong>{" "}
          {selected?.mode === "replay"
            ? "Location, weather and soil are real; the farm layout and operations are hypothetical."
            : "Weather, soil and station observations are modelled or measured as explicitly labelled."}
          {" "}No observation should be mistaken for a validated farm reading.
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-surface px-6 py-3">
          <label className="flex items-center gap-2 text-sm">
            <span className="text-muted">Farm</span>
            <select
              value={farmId}
              onChange={(e) => setFarmId(e.target.value)}
              className="rounded-md border border-line bg-white px-2 py-1 text-sm"
            >
              {farms.map((f) => (
                <option key={f.farm_id} value={f.farm_id}>
                  {f.name} ({f.crops.join(", ")})
                </option>
              ))}
              {farms.length === 0 && <option value="demo-farm">Demo farm</option>}
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <span className="text-muted">Decision day</span>
            <input
              type="date"
              value={day}
              min={DAY_MIN}
              max={DAY_MAX}
              onChange={(e) => e.target.value && setDay(e.target.value)}
              className="rounded-md border border-line bg-white px-2 py-1 text-sm"
            />
          </label>
        </div>
        <main className="flex-1 px-6 py-6">{children}</main>
      </div>
    </div>
  );
}
