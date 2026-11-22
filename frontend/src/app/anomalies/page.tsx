"use client";

import { useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, ErrorNote, Loading, PageHeader, Provenance } from "@/components/ui";
import { type AnomalyEvent, useApi } from "@/lib/api";

interface AnomalyData {
  events: AnomalyEvent[];
  series: { time: string; inlet_m3h: number; scheduled_m3h: number; pressure_kpa: number }[];
  assumptions: string[];
}
const SEV: Record<string, string> = { high: "bg-red-100 text-red-900", medium: "bg-amber-100 text-amber-900", low: "bg-stone-100 text-stone-800" };

export default function Anomalies() {
  const a = useApi<AnomalyData>("/api/anomalies");
  const [showAll, setShowAll] = useState(false);
  const d = a.data?.data;
  // Series at 3-hour resolution; event bands snap to the nearest plotted point.
  const STEP = 3;
  const series = d?.series.filter((_, i) => i % STEP === 0).map((r) => ({ ...r, t: r.time.slice(5, 13).replace("T", " ") })) ?? [];
  const index = new Map((d?.series ?? []).map((r, i) => [r.time.slice(0, 13).replace(" ", "T"), i]));
  const snap = (iso: string) => {
    const i = index.get(iso.slice(0, 13).replace(" ", "T"));
    if (i === undefined || !series.length) return undefined;
    return series[Math.min(series.length - 1, Math.floor(i / STEP))].t;
  };
  const RANK: Record<string, number> = { high: 0, medium: 1, low: 2 };
  const events = [...(d?.events ?? [])].sort((x, y) => RANK[x.severity] - RANK[y.severity] || x.start.localeCompare(y.start));
  const visible = showAll ? events : events.filter((e) => e.severity !== "low");
  return (
    <>
      <PageHeader
        title="Water anomalies"
        lead="Flow at the well compared with what the irrigation schedule should draw. Each alert lists possible causes with evidence and checks to make on site; none concludes who or what is responsible."
      />
      <p className="mb-4 flex items-center gap-2 text-sm text-orange-900">
        <Provenance dataClass="simulated" /> No real meter data yet: this page runs the detectors on synthetic data with injected, labelled faults.
      </p>
      {a.error && <ErrorNote message={a.error} />}
      {a.loading && <Loading what="anomalies" />}
      {d && (
        <div className="space-y-6">
          <Card title="Well flow vs scheduled flow" subtitle="Shaded bands = detected events (first 7 days calibrate the detector).">
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={series} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
                  <CartesianGrid stroke="#e2ddd1" vertical={false} />
                  <XAxis dataKey="t" tick={{ fontSize: 10 }} minTickGap={40} />
                  <YAxis tick={{ fontSize: 11 }} unit=" m³/h" width={70} />
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  {events.map((e, i) => {
                    const x1 = snap(e.start);
                    const x2 = snap(e.end);
                    return x1 && x2 ? (
                      <ReferenceArea key={i} x1={x1} x2={x2} fill={e.severity === "high" ? "#a63a2b" : "#b5651d"} fillOpacity={e.severity === "low" ? 0.08 : 0.18} ifOverflow="extendDomain" />
                    ) : null;
                  })}
                  <Line dataKey="scheduled_m3h" name="Scheduled (design flow)" stroke="#b5651d" dot={false} strokeWidth={1} />
                  <Line dataKey="inlet_m3h" name="Measured at well" stroke="#2f6f9f" dot={false} strokeWidth={1.5} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-muted">
              {events.length} alerts: {events.filter((e) => e.severity === "high").length} high, {events.filter((e) => e.severity === "medium").length} medium, {events.filter((e) => e.severity === "low").length} low. Most severe first.
            </p>
            <button onClick={() => setShowAll(!showAll)} className="text-sm font-medium text-leaf hover:underline">
              {showAll ? "Hide low-severity alerts" : "Show low-severity alerts too"}
            </button>
          </div>
          <div className="space-y-3">
            {visible.map((e, i) => (
              <article key={i} className="rounded-lg border border-line bg-surface p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="font-semibold">
                    {e.kind.replaceAll("_", " ")}
                    {e.zone_id && <span className="font-normal text-muted"> · zone {e.zone_id}</span>}
                  </h3>
                  <div className="flex gap-2 text-xs">
                    <span className={`rounded px-1.5 py-0.5 font-medium ${SEV[e.severity]}`}>severity {e.severity}</span>
                    <span className="rounded bg-stone-100 px-1.5 py-0.5">confidence {e.confidence}</span>
                  </div>
                </div>
                <p className="num mt-1 text-sm text-muted">
                  {e.start.slice(0, 16).replace("T", " ")} → {e.end.slice(11, 16)} · {e.hours} h
                  {e.estimated_volume_m3 !== null && ` · ~${e.estimated_volume_m3} m³`} · alert at {e.detected_at.slice(11, 16)}
                </p>
                <div className="mt-2 grid gap-3 text-sm md:grid-cols-2">
                  <div>
                    <p className="font-medium">Possible causes</p>
                    <ul className="mt-1 space-y-1 text-muted">
                      {e.hypotheses.map((h) => (
                        <li key={h.cause}>{h.cause} <span className="text-xs">({h.likelihood})</span></li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <p className="font-medium">Check on site</p>
                    <ul className="mt-1 list-disc pl-5 text-muted">
                      {e.recommended_checks.map((c) => <li key={c}>{c}</li>)}
                    </ul>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
