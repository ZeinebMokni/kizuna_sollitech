import type { ReactNode } from "react";

export function Card({ title, subtitle, children, className = "" }: {
  title?: ReactNode;
  subtitle?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-xl border border-line bg-surface p-5 ${className}`}>
      {title && <h2 className="text-base font-semibold text-green-deep">{title}</h2>}
      {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
      <div className={title || subtitle ? "mt-4" : ""}>{children}</div>
    </section>
  );
}

export function PageHeader({ title, lead }: { title: string; lead: ReactNode }) {
  return (
    <header className="mb-6">
      <h1 className="text-2xl font-semibold tracking-tight text-green-deep">{title}</h1>
      <p className="mt-1 max-w-3xl text-sm text-muted">{lead}</p>
    </header>
  );
}

const DATA_CLASS_STYLE: Record<string, string> = {
  measured: "bg-emerald-100 text-emerald-900",
  official: "bg-sky-100 text-sky-900",
  farmer_reported: "bg-amber-100 text-amber-900",
  remote_sensed: "bg-indigo-100 text-indigo-900",
  inferred: "bg-stone-200 text-stone-800",
  simulated: "bg-orange-100 text-orange-900",
  projected: "bg-violet-100 text-violet-900",
};

/** Where a value comes from. Shown next to every figure that is not a direct measurement. */
export function Provenance({ dataClass, source }: { dataClass: string; source?: string }) {
  return (
    <span
      title={source ? `Source: ${source}` : undefined}
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${DATA_CLASS_STYLE[dataClass] ?? "bg-stone-100"}`}
    >
      {dataClass.replace("_", " ")}
    </span>
  );
}

const CONFIDENCE_STYLE: Record<string, string> = {
  high: "bg-emerald-100 text-emerald-900",
  medium: "bg-amber-100 text-amber-900",
  low: "bg-orange-100 text-orange-900",
  insufficient_evidence: "bg-red-100 text-red-900",
};

export function Confidence({ level }: { level: string }) {
  return (
    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${CONFIDENCE_STYLE[level] ?? "bg-stone-100"}`}>
      confidence: {level.replaceAll("_", " ")}
    </span>
  );
}

const SUIT_STYLE: Record<string, string> = {
  S1: "bg-emerald-600 text-white",
  S2: "bg-emerald-300 text-emerald-950",
  S3: "bg-amber-300 text-amber-950",
  N: "bg-red-600 text-white",
  U: "bg-stone-300 text-stone-800",
};

export function SuitBadge({ cls, provisional = false }: { cls: string; provisional?: boolean }) {
  return (
    <span
      title={provisional ? "Provisional: rests on an unverified threshold" : undefined}
      className={`inline-block min-w-8 rounded px-1.5 py-0.5 text-center text-xs font-semibold ${SUIT_STYLE[cls] ?? "bg-stone-200"} ${provisional ? "opacity-60 ring-1 ring-dashed ring-stone-500" : ""}`}
    >
      {cls}
      {provisional ? "*" : ""}
    </span>
  );
}

export function Loading({ what }: { what: string }) {
  return <p className="text-sm text-muted">Loading {what}…</p>;
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-900">{message}</p>
  );
}

export function Stat({ label, value, unit, note }: { label: string; value: ReactNode; unit?: string; note?: ReactNode }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="num mt-1 text-2xl font-semibold text-foreground">
        {value}
        {unit && <span className="ml-1 text-sm font-normal text-muted">{unit}</span>}
      </p>
      {note && <p className="mt-0.5 text-xs text-muted">{note}</p>}
    </div>
  );
}

export const ACTION_LABEL: Record<string, string> = {
  irrigate: "Irrigate",
  accept_deficit: "Accept deficit",
  no_action: "No action",
  inspect: "Inspect",
  hold_zone: "Hold zone",
  insufficient_evidence: "Insufficient evidence",
};

export const TIER_STYLE: Record<number, string> = {
  0: "border-l-danger",
  1: "border-l-clay",
  2: "border-l-water",
  3: "border-l-line",
};
