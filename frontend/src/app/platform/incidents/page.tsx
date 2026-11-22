"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Card, ErrorNote, Loading, PageHeader } from "@/components/ui";
import { getPlatformToken, platformRequest, usePlatformApi } from "@/lib/platform-api";

interface Incident {
  id: string;
  incident_type: string;
  status: string;
  occurred_at: string;
  description: string;
  verification_status: string;
}

function PlatformIncidentsContent() {
  const token = getPlatformToken();
  const searchParams = useSearchParams();
  const farmId = searchParams.get("farm") ?? "";
  const [type, setType] = useState("pump_downtime");
  const [description, setDescription] = useState("");
  const [occurredAt, setOccurredAt] = useState("");
  const [message, setMessage] = useState("");
  const incidents = usePlatformApi<Incident[]>(token && farmId ? `/farms/${farmId}/incidents` : null);

  const report = async (event: React.FormEvent) => {
    event.preventDefault();
    setMessage("");
    try {
      await platformRequest(`/farms/${farmId}/incidents`, {
        method: "POST",
        body: JSON.stringify({
          incident_type: type,
          occurred_at: occurredAt,
          description,
        }),
      });
      setDescription("");
      setOccurredAt("");
      setMessage("Incident reported with unverified status.");
      window.location.reload();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not report incident");
    }
  };

  return (
    <>
      <PageHeader title="Incidents and evidence" lead="Farmer-controlled chronology. Reports are not legal proof and evidence remains unverified until reviewed." />
      {!token && (
        <Card>
          <p className="text-sm text-muted">Sign in to view or report incidents.</p>
          <Link href="/platform/login" className="mt-3 inline-block rounded-md bg-green-deep px-3 py-2 text-sm font-medium text-white">Go to login</Link>
        </Card>
      )}
      {token && !farmId && (
        <Card>
          <p className="text-sm text-muted">Open an incident list from a registered farm.</p>
          <Link href="/platform/farms" className="mt-3 inline-block text-sm font-medium text-leaf hover:underline">Open Platform farms</Link>
        </Card>
      )}
      {incidents.error && <ErrorNote message={incidents.error} />}
      {incidents.loading && <Loading what="incidents" />}
      {incidents.data && (
        <div className="space-y-3">
          {incidents.data.map((incident) => (
            <Card key={incident.id} title={incident.incident_type.replaceAll("_", " ")}>
              <p className="text-sm text-muted">{incident.occurred_at.replace("T", " ").slice(0, 16)} · status {incident.status} · verification {incident.verification_status}</p>
              <p className="mt-2 text-sm">{incident.description}</p>
            </Card>
          ))}
          {incidents.data.length === 0 && <Card><p className="text-sm text-muted">No incidents reported.</p></Card>}
        </div>
      )}
      {token && farmId && (
        <Card title="Report an incident" className="mt-6 max-w-xl">
          {message && <p className="mb-3 text-sm text-muted">{message}</p>}
          <form onSubmit={report} className="space-y-3">
            <select value={type} onChange={(e) => setType(e.target.value)} className="w-full rounded-md border border-line px-3 py-2 text-sm">
              <option value="pump_downtime">Pump downtime</option>
              <option value="water_interrupt">Water interruption</option>
              <option value="maintenance">Maintenance request</option>
              <option value="leak_report">Leak report</option>
              <option value="crop_damage">Crop damage</option>
            </select>
            <input required type="datetime-local" value={occurredAt} onChange={(e) => setOccurredAt(e.target.value ? `${e.target.value}:00Z` : "")} className="w-full rounded-md border border-line px-3 py-2 text-sm" />
            <textarea required minLength={10} rows={4} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Describe what happened" className="w-full rounded-md border border-line px-3 py-2 text-sm" />
            <button className="rounded-md bg-green-deep px-3 py-2 text-sm font-medium text-white">Report incident</button>
          </form>
        </Card>
      )}
    </>
  );
}

export default function PlatformIncidents() {
  return (
    <Suspense fallback={<Loading what="incidents" />}>
      <PlatformIncidentsContent />
    </Suspense>
  );
}
