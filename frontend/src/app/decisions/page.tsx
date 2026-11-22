"use client";

import { DecisionCard } from "@/components/decision-card";
import { Card, Confidence, ErrorNote, Loading, PageHeader } from "@/components/ui";
import { type DecisionEnvelope, useApi } from "@/lib/api";
import { useDay } from "@/lib/day";

export default function Decisions() {
  const { day } = useDay();
  const dec = useApi<DecisionEnvelope>(`/api/decision?day=${day}`);
  const env = dec.data?.data;
  return (
    <>
      <PageHeader
        title="Decisions"
        lead="Every proposal, ranked by a fixed rule: safety first, then irreversible risk, then stress expected within 72 hours. Ties go to the zone closest to damage. Nothing is executed without approval."
      />
      {dec.error && <ErrorNote message={dec.error} />}
      {dec.loading && <Loading what="decisions" />}
      {env && (
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="space-y-3 lg:col-span-2">
            {env.payload?.packages.map((p) => <DecisionCard key={p.package_id} p={p} expanded />)}
          </div>
          <Card title="About these decisions">
            <div className="space-y-3 text-sm">
              <Confidence level={env.confidence} />
              <p className="text-muted">
                Model: {env.model.model_id.replaceAll("_", " ")}, status{" "}
                <strong>{env.model.validation_status.replaceAll("_", " ")}</strong>.
              </p>
              <ul className="list-disc space-y-1 pl-5 text-muted">
                {env.limitations.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
              <button
                disabled
                title="Approval workflow is not built yet"
                className="w-full cursor-not-allowed rounded-md bg-stone-200 px-3 py-2 text-sm text-stone-600"
              >
                Approve selected (not available in the demo)
              </button>
            </div>
          </Card>
        </div>
      )}
    </>
  );
}
