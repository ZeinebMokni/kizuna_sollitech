"use client";

import { Card, ErrorNote, Loading, PageHeader, SuitBadge } from "@/components/ui";
import { useApi } from "@/lib/api";

interface EnsembleRow {
  ssp: string;
  crop: string;
  models: number;
  irrigation_p80_m3_ha_change_pct_min: number;
  irrigation_p80_m3_ha_change_pct_median: number;
  irrigation_p80_m3_ha_change_pct_max: number;
}
interface ScenarioRow {
  scenario: string;
  kind: string;
  ssp: string | null;
  model: string | null;
  crop: string;
  overall: string;
  et0_annual_mm: number;
  irrigation_p80_m3_ha: number;
  irrigation_p80_m3_ha_change_pct: number;
  dtmax_mean_c: number | null;
  precip_ratio_mean: number | null;
}
interface ClimateData {
  models: string[];
  not_retrieved: string[];
  ensemble: EnsembleRow[];
  scenarios: ScenarioRow[];
  limitations: string[];
  farm_note: string;
}

const CROP_NAME: Record<string, string> = { tomato: "Tomato", potato: "Potato", durum_wheat: "Durum wheat", citrus: "Citrus" };
const SSP_LABEL: Record<string, string> = { ssp245: "SSP2-4.5 (moderate)", ssp585: "SSP5-8.5 (high emissions)" };
const SCALE_MAX = 35; // % axis for the range bars

function RangeBar({ r }: { r: EnsembleRow }) {
  const pos = (v: number) => `${Math.max(0, Math.min(100, (v / SCALE_MAX) * 100))}%`;
  return (
    <div className="relative h-5 flex-1 rounded bg-stone-100">
      {[0, 10, 20, 30].map((t) => (
        <span key={t} className="absolute top-0 h-full w-px bg-stone-300" style={{ left: pos(t) }} />
      ))}
      <span
        className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded bg-water/40"
        style={{ left: pos(r.irrigation_p80_m3_ha_change_pct_min), width: `calc(${pos(r.irrigation_p80_m3_ha_change_pct_max)} - ${pos(r.irrigation_p80_m3_ha_change_pct_min)})` }}
      />
      <span
        className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-water"
        style={{ left: pos(r.irrigation_p80_m3_ha_change_pct_median) }}
        title={`median ${r.irrigation_p80_m3_ha_change_pct_median}%`}
      />
    </div>
  );
}

export default function Climate() {
  const c = useApi<ClimateData>("/api/climate");
  const d = c.data?.data;
  const baseline = d?.scenarios.filter((s) => s.kind === "historical") ?? [];
  const signals = d ? Array.from(new Map(d.scenarios.filter((s) => s.kind !== "historical").map((s) => [s.scenario, s])).values()) : [];
  const crops = d ? Array.from(new Set(d.ensemble.map((e) => e.crop))) : [];
  return (
    <>
      <PageHeader
        title="Climate 2050: how much more water?"
        lead="Change in dry-year irrigation need for 2041–2060 against 1995–2014, at the same water quota. Each climate model gives a different answer; the bar shows the range across models and the dot the median. These are scenarios, not forecasts."
      />
      {c.error && <ErrorNote message={c.error} />}
      {c.loading && <Loading what="climate scenarios" />}
      {d && (
        <div className="space-y-6">
          <Card title="Change in dry-year irrigation need, % (range across models)" subtitle={`Models: ${d.models.length - d.not_retrieved.length} of ${d.models.length} retrieved. ${d.farm_note}.`}>
            <div className="space-y-4">
              {crops.map((crop) => (
                <div key={crop}>
                  <p className="text-sm font-medium">
                    {CROP_NAME[crop] ?? crop}{" "}
                    <span className="font-normal text-muted">
                      (baseline {baseline.find((b) => b.crop === crop)?.irrigation_p80_m3_ha.toLocaleString()} m³/ha, rated{" "}
                    </span>
                    <SuitBadge cls={baseline.find((b) => b.crop === crop)?.overall ?? "U"} />
                    <span className="font-normal text-muted">)</span>
                  </p>
                  {d.ensemble.filter((e) => e.crop === crop).map((r) => (
                    <div key={r.ssp} className="mt-1 flex items-center gap-3 text-xs">
                      <span className="w-44 shrink-0 text-muted">{SSP_LABEL[r.ssp] ?? r.ssp}</span>
                      <RangeBar r={r} />
                      <span className="num w-28 shrink-0 text-right">
                        +{r.irrigation_p80_m3_ha_change_pct_min} to +{r.irrigation_p80_m3_ha_change_pct_max}%
                      </span>
                    </div>
                  ))}
                </div>
              ))}
              <div className="flex items-center gap-3 text-[10px] text-muted">
                <span className="w-44 shrink-0" />
                <div className="relative h-3 flex-1">
                  {[0, 10, 20, 30].map((t) => (
                    <span key={t} className="absolute -translate-x-1/2" style={{ left: `${(t / SCALE_MAX) * 100}%` }}>+{t}%</span>
                  ))}
                </div>
                <span className="w-28 shrink-0" />
              </div>
            </div>
          </Card>
          <div className="grid gap-6 lg:grid-cols-2">
            <Card title="Climate signal per scenario" subtitle="Projected = one climate model's change applied to the real baseline. Hypothetical = chosen stress test.">
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-muted">
                  <tr><th className="py-1">Scenario</th><th className="text-right">ΔTmax</th><th className="text-right">Rain</th><th className="text-right">ET0 mm/yr</th></tr>
                </thead>
                <tbody>
                  <tr className="border-t border-line"><td className="py-1.5">Baseline 1995–2014 <span className="text-xs text-muted">historical</span></td><td className="num text-right">–</td><td className="num text-right">–</td><td className="num text-right">{baseline[0]?.et0_annual_mm}</td></tr>
                  {signals.map((s) => (
                    <tr key={s.scenario} className="border-t border-line">
                      <td className="py-1.5">{s.scenario} <span className="text-xs text-muted">{s.kind}</span></td>
                      <td className="num text-right">+{s.dtmax_mean_c?.toFixed(1)} °C</td>
                      <td className="num text-right">{s.precip_ratio_mean !== null ? `${Math.round((s.precip_ratio_mean - 1) * 100)}%` : "–"}</td>
                      <td className="num text-right">{s.et0_annual_mm}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
            <Card title="Limits of these scenarios">
              <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
                {d.not_retrieved.length > 0 && <li>Not retrieved: {d.not_retrieved.map((n) => n.split(":")[0]).join(", ")} (no historical files on the NASA service). The range rests on fewer models.</li>}
                {d.limitations.map((l) => <li key={l}>{l}</li>)}
              </ul>
            </Card>
          </div>
        </div>
      )}
    </>
  );
}
