"use client";

import { useState } from "react";
import type { DecisionPackage } from "@/lib/api";
import { ACTION_LABEL, Confidence, Provenance, TIER_STYLE } from "./ui";

const ZONE_NAME: Record<string, string> = {
  "olive-north": "Olive grove (north)",
  "tomato-east": "Tomato (east)",
  "potato-south": "Potato (south)",
};

/** Consecutive hourly windows -> "06:00–09:00, 13:00–15:00". */
function hourRanges(windows: string[]): string {
  const hours = windows.map((w) => Number(w.slice(11, 13)) + 24 * Number(w.slice(8, 10))).sort((a, b) => a - b);
  const fmt = (h: number) => `${String(h % 24).padStart(2, "0")}:00`;
  const out: string[] = [];
  let start = hours[0];
  let prev = hours[0];
  for (const h of [...hours.slice(1), Number.NaN]) {
    if (h - prev === 1) {
      prev = h;
      continue;
    }
    out.push(`${fmt(start)}–${fmt(prev + 1)}`);
    start = h;
    prev = h;
  }
  return out.join(", ");
}

export function zoneName(id: string) {
  return ZONE_NAME[id] ?? id;
}

export function DecisionCard({ p, expanded = false }: { p: DecisionPackage; expanded?: boolean }) {
  const [open, setOpen] = useState(expanded);
  return (
    <article className={`rounded-lg border border-line border-l-4 bg-surface p-4 ${TIER_STYLE[p.tier] ?? ""}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-xs text-muted">
            #{p.rank} · tier {p.tier}: {p.tier_label}
          </p>
          <h3 className="mt-0.5 text-lg font-semibold">
            {ACTION_LABEL[p.action] ?? p.action}
            {p.amount && (
              <span className="num">
                {" "}
                {p.amount.value} {p.amount.unit}
              </span>
            )}{" "}
            <span className="font-normal text-muted">→ {zoneName(p.target)}</span>
          </h3>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Confidence level={p.confidence} />
          {p.requires_human_approval && (
            <span className="rounded bg-green-deep px-1.5 py-0.5 text-xs font-medium text-white">needs approval</span>
          )}
        </div>
      </div>
      <ul className="mt-3 space-y-1 text-sm">
        {p.reasons.map((r) => (
          <li key={r.code}>
            <span className="font-medium">{r.code.replaceAll("_", " ").toLowerCase()}</span>
            {r.text !== r.code && <span className="text-muted">: {r.text}</span>}
          </li>
        ))}
      </ul>
      {p.windows.length > 0 && (
        <p className="mt-2 text-sm text-muted">
          Pump runs, next 24 h: {hourRanges(p.windows)} ({p.windows.length} h)
        </p>
      )}
      <button onClick={() => setOpen(!open)} className="mt-3 text-sm font-medium text-leaf hover:underline">
        {open ? "Hide details" : "Why this rank, evidence and alternatives"}
      </button>
      {open && (
        <div className="mt-3 grid gap-4 border-t border-line pt-3 text-sm md:grid-cols-2">
          <div>
            <h4 className="font-medium">Why this rank</h4>
            <ul className="mt-1 list-disc pl-5 text-muted">
              {p.priority_trace.map((t) => (
                <li key={t}>{t}</li>
              ))}
            </ul>
            {Object.keys(p.expected_impact).length > 0 && (
              <>
                <h4 className="mt-3 font-medium">Expected impact (72 h)</h4>
                <ul className="mt-1 text-muted">
                  {Object.entries(p.expected_impact).map(([k, v]) => (
                    <li key={k} className="num">
                      {k.replaceAll("_", " ")}: {v.value} {v.unit}
                    </li>
                  ))}
                </ul>
              </>
            )}
            {p.constraints.length > 0 && (
              <>
                <h4 className="mt-3 font-medium">Binding limits</h4>
                <ul className="mt-1 text-muted">
                  {p.constraints.map((c) => (
                    <li key={c}>{c.replaceAll("_", " ")}</li>
                  ))}
                </ul>
              </>
            )}
          </div>
          <div>
            <h4 className="font-medium">Evidence</h4>
            <ul className="mt-1 space-y-1 text-muted">
              {p.supporting_measurements.map((m, i) => (
                <li key={i} className="flex flex-wrap items-center gap-2">
                  <span className="num">
                    {m.what}: {m.quantity?.value} {m.quantity?.unit}
                  </span>
                  {m.provenance && <Provenance dataClass={m.provenance.data_class} source={m.provenance.source} />}
                </li>
              ))}
            </ul>
            {p.alternatives.length > 0 && (
              <>
                <h4 className="mt-3 font-medium">Alternatives</h4>
                <ul className="mt-1 text-muted">
                  {p.alternatives.map((a, i) => (
                    <li key={i}>
                      {a.action}
                      {a.consequence && ` → ${a.consequence}`}
                      {a.note && ` (${a.note})`}
                    </li>
                  ))}
                </ul>
              </>
            )}
            <h4 className="mt-3 font-medium">Data limitations</h4>
            <ul className="mt-1 list-disc pl-5 text-muted">
              {[...p.data_limitations, ...p.confidence_reasons].map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </article>
  );
}
