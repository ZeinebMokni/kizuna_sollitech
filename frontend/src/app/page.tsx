"use client";

import { DecisionCard, zoneName } from "@/components/decision-card";
import { FarmMap } from "@/components/farm-map";
import { Card, ErrorNote, Loading, PageHeader, Provenance, Stat } from "@/components/ui";
import { type DecisionEnvelope, type FarmInfo, useApi, useSelectedFarm } from "@/lib/api";
import { useDay } from "@/lib/day";

export default function Overview() {
  const { day } = useDay();
  const { farmId } = useSelectedFarm();
  const farm = useApi<FarmInfo>(`/api/farms/${farmId}`);
  const dec = useApi<DecisionEnvelope>(`/api/farms/${farmId}/decision?day=${day}`);
  const payload = dec.data?.data.payload;
  const plan = payload?.schedule;
  const actions = Object.fromEntries((payload?.packages ?? []).map((p) => [p.target, p.action]));
  const top = payload?.packages.filter((p) => p.tier < 3) ?? [];
  const stressed = payload?.packages.filter((p) => p.tier <= 2 && p.action !== "inspect").length ?? 0;

  return (
    <>
      <PageHeader
        title="Where to intervene first"
        lead={
          top[0]
            ? `On ${day}, the first priority is: ${top[0].action.replace("_", " ")} ${top[0].amount ? `${top[0].amount.value} ${top[0].amount.unit} ` : ""}on ${zoneName(top[0].target)}. Every action that moves water needs your approval.`
            : "Ranked interventions for the selected day, with the evidence behind each."
        }
      />
      {dec.error && <ErrorNote message={dec.error} />}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <Stat label="Zones needing attention" value={payload ? stressed : "–"} note={`of ${farm.data?.data.zones.length ?? 3} zones`} />
        </Card>
        <Card>
          <Stat label="Water planned, 72 h" value={plan ? plan.totals.water_m3 : "–"} unit="m³" note={`well cap ${farm.data?.data.max_volume_per_day_m3 ?? "–"} m³/day`} />
        </Card>
        <Card>
          <Stat label="Pump energy, 72 h" value={plan ? Math.round(plan.totals.pump_energy_kwh) : "–"} unit="kWh" note={plan ? `solar used ${Math.round(plan.totals.pv_used_kwh)} of ${Math.round(plan.totals.pv_available_kwh)} kWh` : undefined} />
        </Card>
        <Card>
          <Stat label="Overall confidence" value={dec.data?.data.confidence.replaceAll("_", " ") ?? "–"} note={dec.data ? `model: ${dec.data.data.model.validation_status.replaceAll("_", " ")}` : undefined} />
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-5">
        <div className="space-y-3 lg:col-span-3">
          <h2 className="text-base font-semibold text-green-deep">Ranked decisions</h2>
          {dec.loading && <Loading what="decisions" />}
          {payload?.packages.map((p) => <DecisionCard key={p.package_id} p={p} />)}
        </div>
        <div className="space-y-4 lg:col-span-2">
          <Card title="Farm layout" subtitle="Zone colour = today's decision. Layout is hypothetical.">
            {farm.data ? (
              <FarmMap
                key={farmId}
                center={[farm.data.data.latitude, farm.data.data.longitude]}
                zones={farm.data.data.zones}
                actions={actions}
              />
            ) : (
              <Loading what="map" />
            )}
            <div className="mt-3 flex flex-wrap gap-3 text-xs text-muted">
              <span><i className="mr-1 inline-block h-2.5 w-2.5 rounded-sm bg-water" />irrigate</span>
              <span><i className="mr-1 inline-block h-2.5 w-2.5 rounded-sm bg-clay" />accept deficit</span>
              <span><i className="mr-1 inline-block h-2.5 w-2.5 rounded-sm bg-leaf" />no action</span>
              <span><i className="mr-1 inline-block h-2.5 w-2.5 rounded-sm bg-danger" />hold</span>
            </div>
          </Card>
          {farm.data && (
            <Card title="Data behind these decisions">
              <ul className="space-y-2 text-sm">
                <li className="flex items-center justify-between gap-2">Weather 2025 (NASA POWER) <Provenance dataClass="inferred" source="nasa_power:daily_point" /></li>
                <li className="flex items-center justify-between gap-2">Soil FC {farm.data.data.soil.theta_fc} / WP {farm.data.data.soil.theta_wp} (SoilGrids) <Provenance dataClass={farm.data.data.soil.data_class} source={farm.data.data.soil.source} /></li>
                <li className="flex items-center justify-between gap-2">Root-zone water state (no sensors) <Provenance dataClass="inferred" source="FAO-56 water balance" /></li>
                <li className="flex items-center justify-between gap-2">Crop parameters (FAO, not locally reviewed) <Provenance dataClass="inferred" source="FAO-56/33/29" /></li>
              </ul>
            </Card>
          )}
        </div>
      </div>
    </>
  );
}
