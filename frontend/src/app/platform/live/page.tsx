"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Card, ErrorNote, Loading, PageHeader, Provenance } from "@/components/ui";
import { getPlatformToken, usePlatformApi } from "@/lib/platform-api";

interface Device {
  id: string;
  external_id: string;
  name: string;
  status: string;
  firmware_version: string | null;
  last_seen_at: string | null;
  sensors: {
    id: string;
    external_id: string;
    kind: string;
    unit: string;
    calibration_status: string;
    is_active: boolean;
  }[];
}

interface Measurement {
  id: string;
  sensor_external_id: string;
  sensor_kind: string;
  observed_at: string;
  value: number;
  unit: string;
  quality: string;
  data_class: string;
  quality_note: string | null;
}

function PlatformLiveContent() {
  const token = getPlatformToken();
  const searchParams = useSearchParams();
  const farmId = searchParams.get("farm") ?? "";
  const devices = usePlatformApi<Device[]>(token && farmId ? `/farms/${farmId}/devices` : null);
  const measurements = usePlatformApi<Measurement[]>(token && farmId ? `/farms/${farmId}/measurements?limit=50` : null);

  return (
    <>
      <PageHeader title="Live monitoring" lead="Registered devices and their latest authenticated measurements. Missing or invalid readings remain visible; no chart is filled with invented values." />
      {!token && (
        <Card>
          <p className="text-sm text-muted">Sign in and open a farm from Platform farms.</p>
          <Link href="/platform/login" className="mt-3 inline-block rounded-md bg-green-deep px-3 py-2 text-sm font-medium text-white">Go to login</Link>
        </Card>
      )}
      {token && !farmId && (
        <Card>
          <p className="text-sm text-muted">Select a registered farm.</p>
          <Link href="/platform/farms" className="mt-3 inline-block text-sm font-medium text-leaf hover:underline">Open Platform farms</Link>
        </Card>
      )}
      {devices.error && <ErrorNote message={devices.error} />}
      {measurements.error && <ErrorNote message={measurements.error} />}
      {devices.loading && <Loading what="devices" />}
      {devices.data && (
        <div className="grid gap-4 md:grid-cols-2">
          {devices.data.map((device) => (
            <Card key={device.id} title={device.name} subtitle={`${device.external_id} · firmware ${device.firmware_version ?? "unknown"}`}>
              <p className="text-sm"><strong>Status:</strong> {device.status.replace("_", " ")}</p>
              <p className="mt-1 text-xs text-muted">Last seen: {device.last_seen_at ?? "never"}</p>
              <ul className="mt-3 space-y-1 text-sm">
                {device.sensors.map((sensor) => (
                  <li key={sensor.id} className="flex justify-between gap-2">
                    <span>{sensor.external_id} · {sensor.kind.replaceAll("_", " ")}</span>
                    <span className="text-muted">{sensor.calibration_status} · {sensor.unit}</span>
                  </li>
                ))}
              </ul>
            </Card>
          ))}
          {devices.data.length === 0 && <Card><p className="text-sm text-muted">No devices registered for this farm.</p></Card>}
        </div>
      )}
      {measurements.data && (
        <Card title="Recent measurements" className="mt-6">
          {measurements.data.length === 0 ? (
            <p className="text-sm text-muted">No sensor measurements received.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-xs uppercase text-muted">
                  <tr><th className="py-2">Time</th><th>Sensor</th><th>Value</th><th>Quality</th><th>Origin</th></tr>
                </thead>
                <tbody>
                  {measurements.data.map((row) => (
                    <tr key={row.id} className="border-t border-line">
                      <td className="py-2 pr-3">{row.observed_at.replace("T", " ").slice(0, 16)}</td>
                      <td className="pr-3">{row.sensor_external_id}</td>
                      <td className="num pr-3">{row.value} {row.unit}</td>
                      <td className="pr-3">{row.quality}{row.quality_note ? ` · ${row.quality_note}` : ""}</td>
                      <td><Provenance dataClass={row.data_class} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
    </>
  );
}

export default function PlatformLive() {
  return (
    <Suspense fallback={<Loading what="live monitoring" />}>
      <PlatformLiveContent />
    </Suspense>
  );
}
