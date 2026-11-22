"use client";

import { useState } from "react";
import { Card, PageHeader } from "@/components/ui";
import { useDay } from "@/lib/day";

interface Answer {
  text: string;
  language: string;
  verified: boolean;
  used_fallback: boolean;
  fallback_reason: string | null;
  violations: string[];
  citations: string[];
  tool_calls: string[];
  provider: string | null;
  model: string | null;
}

const EXAMPLES = [
  "What should I do first today, and why?",
  "Pourquoi la zone tomate est-elle prioritaire ?",
  "لماذا لا نسقي البطاطا اليوم؟",
];

export default function Assistant() {
  const { day } = useDay();
  const [q, setQ] = useState(EXAMPLES[0]);
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function ask(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await fetch("/api/assistant", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, day }),
      });
      const body = await r.json();
      if (!r.ok) throw new Error(body?.detail ? JSON.stringify(body.detail) : `HTTP ${r.status}`);
      setAnswer(body.data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Assistant"
        lead="Ask about today's decisions in Arabic, French or English. Answers use only QATRA's own results; every number is checked against them before it is shown."
      />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <form onSubmit={ask} className="space-y-3">
            <textarea
              value={q}
              onChange={(e) => setQ(e.target.value)}
              rows={3}
              dir="auto"
              className="w-full rounded-md border border-line bg-white p-3 text-base"
            />
            <div className="flex flex-wrap items-center gap-2">
              <button disabled={busy || q.trim().length < 2} className="rounded-md bg-green-deep px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
                {busy ? "Asking…" : "Ask"}
              </button>
              {EXAMPLES.map((ex) => (
                <button type="button" key={ex} onClick={() => setQ(ex)} dir="auto" className="rounded-md border border-line px-2 py-1 text-xs text-muted hover:bg-stone-50">
                  {ex}
                </button>
              ))}
            </div>
          </form>
          {error && <p className="mt-4 text-sm text-red-800">{error}</p>}
          {answer && (
            <div className="mt-5 border-t border-line pt-4">
              <div className="mb-2 flex flex-wrap gap-2 text-xs">
                {answer.verified ? (
                  <span className="rounded bg-emerald-100 px-1.5 py-0.5 font-medium text-emerald-900">checked against QATRA results</span>
                ) : (
                  <span className="rounded bg-amber-100 px-1.5 py-0.5 font-medium text-amber-900">fallback: {answer.fallback_reason}</span>
                )}
                {answer.tool_calls.length > 0 && <span className="rounded bg-stone-100 px-1.5 py-0.5">tools: {answer.tool_calls.join(", ")}</span>}
                {answer.model && <span className="rounded bg-stone-100 px-1.5 py-0.5">{answer.provider}: {answer.model}</span>}
              </div>
              <p dir="auto" className="whitespace-pre-wrap text-sm leading-relaxed">{answer.text}</p>
            </div>
          )}
        </Card>
        <Card title="How it works">
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
            <li>The configured model (Gemini or Claude) reads QATRA&apos;s decisions, suitability and anomaly results through read-only tools.</li>
            <li>A checker compares every number in the answer with those results and rejects accusatory or &quot;guaranteed&quot; wording.</li>
            <li>If the check fails twice, or no API key is set, you get the engine&apos;s ranked proposals instead.</li>
            <li>Needs <code>GEMINI_API_KEY</code> (or <code>ANTHROPIC_API_KEY</code>) on the engine API; each question is billed by the provider.</li>
          </ul>
        </Card>
      </div>
    </>
  );
}
