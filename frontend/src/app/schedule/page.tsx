"use client";

import { zoneName } from "@/components/decision-card";
import { Card, ErrorNote, Loading, PageHeader, Stat } from "@/components/ui";
import { type DecisionEnvelope, useApi } from "@/lib/api";
import { useDay } from "@/lib/day";

const HOURS = 72;
const UNIT: Record<string, string> = {
  pump_flow: "m³/h of pump capacity in every hour",
  energy: "kWh available in every hour",
  water_daily_cap: "m³ on each daily well cap",
  water_volume_cap: "m³ of allowed volume",
};

export default function Schedule() {
  const { day } = useDay();
  const dec = useApi<DecisionEnvelope>(`/api/decision?day=${day}`);
  const plan = dec.data?.data.payload?.schedule;
  const start = dec.data?.data.payload?.schedule_start;

  return (
    <>
      <PageHeader
        title="Irrigation schedule, next 72 hours"
        lead="Which zone the pump serves each hour, within the pump, the well cap, solar, battery and operating hours. Stress is weighted by crop-stage sensitivity, with extra weight for tree crops."
      />
      {dec.error && <ErrorNote message={dec.error} />}
      {dec.loading && <Loading what="schedule" />}
      {plan && start && (
        <div className="space-y-6">
          <div className="grid gap-4 md:grid-cols-4">
            <Card><Stat label="Water" value={plan.totals.water_m3} unit="m³" /></Card>
            <Card><Stat label="Pump energy" value={Math.round(plan.totals.pump_energy_kwh)} unit="kWh" /></Card>
            <Card><Stat label="Solar used" value={Math.round(plan.totals.pv_used_kwh)} unit="kWh" note={`of ${Math.round(plan.totals.pv_available_kwh)} kWh available`} /></Card>
            <Card><Stat label="Plan" value={plan.status} note={`${plan.solver}, ${plan.solve_time_s} s; ${plan.verification_violations.length} limit violations`} /></Card>
          </div>

          <Card title="Pump timeline" subtitle={`Each cell is one hour from ${start.slice(0, 10)} 00:00. Filled = zone irrigating.`}>
            <div className="overflow-x-auto">
              <div className="min-w-[760px]">
                <div className="ml-40 grid text-[10px] text-muted" style={{ gridTemplateColumns: `repeat(${HOURS}, 1fr)` }}>
                  {Array.from({ length: HOURS }, (_, h) => (
                    <span key={h} className={h % 6 === 0 ? "" : "invisible"}>
                      {h % 24 === 0 ? `D+${h / 24}` : `${h % 24}h`}
                    </span>
                  ))}
                </div>
                {plan.zones.map((z) => {
                  const on = new Set(plan.actions.filter((a) => a.zone_id === z.zone_id).map((a) => a.slot));
                  return (
                    <div key={z.zone_id} className="mt-1 flex items-center">
                      <span className="w-40 shrink-0 truncate pr-2 text-sm">{zoneName(z.zone_id)}</span>
                      <div className="grid flex-1 gap-px" style={{ gridTemplateColumns: `repeat(${HOURS}, 1fr)` }}>
                        {Array.from({ length: HOURS }, (_, h) => (
                          <span
                            key={h}
                            title={`${zoneName(z.zone_id)} · hour ${h}${on.has(h) ? " · irrigating" : ""}`}
                            className={`h-6 ${on.has(h) ? "bg-water" : h % 24 >= 6 && h % 24 < 18 ? "bg-amber-50" : "bg-stone-100"}`}
                          />
                        ))}
                      </div>
                    </div>
                  );
                })}
                <p className="mt-2 ml-40 text-xs text-muted">Pale yellow = daylight hours (06–18), when solar is available.</p>
              </div>
            </div>
          </Card>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card title="Outcome by zone" subtitle="Stress = depletion beyond the readily available water, summed over hours (mm·h).">
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-muted">
                  <tr><th className="py-1">Zone</th><th className="pl-4 text-right">Water m³</th><th className="pl-4 text-right">Stress</th><th className="pl-4 text-right">Without plan</th></tr>
                </thead>
                <tbody>
                  {plan.zones.map((z) => (
                    <tr key={z.zone_id} className="border-t border-line align-top">
                      <td className="py-2">
                        {zoneName(z.zone_id)}
                        <p className="text-xs text-muted">{z.reasons.map((r) => r.replaceAll("_", " ").toLowerCase()).join(" · ")}</p>
                      </td>
                      <td className="num py-2 pl-4 text-right">{z.volume_m3}</td>
                      <td className="num py-2 pl-4 text-right">{Math.round(z.stress_mm_h)}</td>
                      <td className="num py-2 pl-4 text-right text-muted">{Math.round(z.stress_mm_h_without_irrigation)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {plan.unweighted_comparison && (
                <p className="mt-3 text-xs text-muted">
                  With all zones weighted equally the split would be:{" "}
                  {Object.entries(plan.unweighted_comparison).map(([k, v]) => `${zoneName(k)} ${v} m³`).join(", ")}.
                </p>
              )}
            </Card>
            <Card title="What limits the plan" subtitle="A shadow price shows how much weighted stress one more unit of that resource would avoid (approximate).">
              <ul className="space-y-3 text-sm">
                {plan.constraints.map((c) => (
                  <li key={c.name}>
                    <div className="flex justify-between gap-2">
                      <span className="font-medium">{c.name.replaceAll("_", " ")}</span>
                      <span className="num text-muted">
                        binding {c.binding_slots} {c.name === "water_daily_cap" ? "day(s)" : "hour(s)"}
                      </span>
                    </div>
                    {c.shadow_price !== null && (
                      <p className="num text-xs text-muted">
                        shadow price {c.shadow_price.toFixed(2)}
                        {c.shadow_price < 0.01 ? ": not limiting the plan" : `: weighted stress avoided per extra ${UNIT[c.name] ?? "unit"}`}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
              <h3 className="mt-4 text-sm font-medium">Assumptions</h3>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-muted">
                {plan.assumptions.map((a) => <li key={a}>{a}</li>)}
              </ul>
            </Card>
          </div>
        </div>
      )}
    </>
  );
}
