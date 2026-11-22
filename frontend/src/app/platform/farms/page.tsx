"use client";

import { useState } from "react";
import Link from "next/link";
import { Card, ErrorNote, Loading, PageHeader, Provenance } from "@/components/ui";
import { getPlatformToken, platformRequest, usePlatformApi } from "@/lib/platform-api";
import type { PlatformFarm } from "@/lib/platform-api";

export default function PlatformFarms() {
  const token = getPlatformToken();
  const farms = usePlatformApi<PlatformFarm[]>(token ? "/farms" : null);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const createFarm = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      await platformRequest("/farms", {
        method: "POST",
        body: JSON.stringify({ name, code, country_code: "TN", timezone: "Africa/Tunis" }),
      });
      setName("");
      setCode("");
      setMessage("Farm created.");
      window.location.reload();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not create farm");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader title="Platform farms" lead="Authorized farm records stored in PostgreSQL/PostGIS. These records are separate from the engine's YAML demo profiles." />
      {!token && (
        <Card>
          <p className="text-sm text-muted">Sign in to view and create platform farms.</p>
          <Link href="/platform/login" className="mt-3 inline-block rounded-md bg-green-deep px-3 py-2 text-sm font-medium text-white">Go to login</Link>
        </Card>
      )}
      {farms.error && <ErrorNote message={farms.error} />}
      {farms.loading && <Loading what="platform farms" />}
      {farms.data && (
        <div className="grid gap-4 md:grid-cols-2">
          {farms.data.map((farm) => (
            <Card key={farm.id} title={farm.name} subtitle={`${farm.code} · ${farm.governorate ?? "governorate not set"} · ${farm.timezone}`}>
              <div className="flex items-center justify-between">
                <Provenance dataClass={farm.data_class} />
                <div className="flex gap-3 text-sm font-medium">
                  <Link href={`/platform/live?farm=${farm.id}`} className="text-leaf hover:underline">Live monitoring</Link>
                  <Link href={`/platform/incidents?farm=${farm.id}`} className="text-leaf hover:underline">Incidents</Link>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
      {token && (
        <Card title="Register a farm" className="mt-6 max-w-xl">
          {message && <p className="mb-3 text-sm text-muted">{message}</p>}
          <form onSubmit={createFarm} className="grid gap-3 md:grid-cols-2">
            <input required placeholder="Farm name" value={name} onChange={(e) => setName(e.target.value)} className="rounded-md border border-line px-3 py-2 text-sm" />
            <input required placeholder="Code" value={code} onChange={(e) => setCode(e.target.value)} className="rounded-md border border-line px-3 py-2 text-sm" />
            <button disabled={busy} className="rounded-md bg-green-deep px-3 py-2 text-sm font-medium text-white md:col-span-2">{busy ? "Creating…" : "Create farm"}</button>
          </form>
        </Card>
      )}
    </>
  );
}
