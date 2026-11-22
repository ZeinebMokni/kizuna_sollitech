"use client";

import { Card, ErrorNote, Loading, PageHeader, SuitBadge } from "@/components/ui";
import { type CropSuitability, useApi } from "@/lib/api";

const FACTORS = ["water", "salinity", "heat", "frost", "energy", "soil_depth", "market"];
const CROP_NAME: Record<string, string> = {
  tomato: "Tomato", potato: "Potato", durum_wheat: "Durum wheat", olive: "Olive", citrus: "Citrus", date_palm: "Date palm",
};

export default function Crops() {
  const s = useApi<CropSuitability[]>("/api/suitability");
  const site = s.data?.meta.site as Record<string, number> | undefined;
  return (
    <>
      <PageHeader
        title="Crop suitability"
        lead="Each factor is rated S1 (highly suitable) to N (not suitable), or U when data is missing. The overall rating is the worst factor, never an average. Water need is sized for a dry year over 2015–2024."
      />
      {s.error && <ErrorNote message={s.error} />}
      {s.loading && <Loading what="suitability (10 years of weather)" />}
      {s.data && (
        <div className="space-y-6">
          <Card
            title="Ratings by factor"
            subtitle={site ? `Hypothetical site: ${site.water_m3_per_ha} m³/ha water, ${site.energy_kwh_per_ha} kWh/ha energy, irrigation water ${site.irrigation_ec_ds_m} dS/m, soil ${site.soil_depth_m} m. * = provisional (unverified threshold), not used for the overall rating.` : undefined}
          >
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-sm">
                <thead className="text-left text-xs text-muted">
                  <tr>
                    <th className="py-1">Crop</th>
                    <th>Overall</th>
                    {FACTORS.map((f) => <th key={f} className="text-center">{f.replace("_", " ")}</th>)}
                    <th className="text-right">Dry-year need</th>
                    <th className="text-right">Exp. yield</th>
                    <th className="text-center">Trade-off best</th>
                  </tr>
                </thead>
                <tbody>
                  {s.data.data.map((c) => (
                    <tr key={c.crop} className="border-t border-line">
                      <td className="py-2 font-medium">{CROP_NAME[c.crop] ?? c.crop}<p className="text-xs font-normal text-muted">planted {c.planting}</p></td>
                      <td><SuitBadge cls={c.overall} /></td>
                      {FACTORS.map((f) => {
                        const fr = c.factors.find((x) => x.factor === f);
                        return (
                          <td key={f} className="text-center" title={fr ? `${fr.rule}${fr.note ? ` — ${fr.note}` : ""}` : undefined}>
                            {fr ? <SuitBadge cls={fr.suitability} provisional={fr.provisional} /> : "–"}
                          </td>
                        );
                      })}
                      <td className="num text-right">{c.indicators.gross_irrigation_p80_m3_per_ha?.toLocaleString() ?? "–"} m³/ha</td>
                      <td className="num text-right">{c.indicators.expected_relative_yield ?? "–"}</td>
                      <td className="text-center">{c.pareto_optimal === null ? "–" : c.pareto_optimal ? "yes" : "no"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-xs text-muted">Hover a rating to see its rule and value. &quot;Trade-off best&quot; means no other suitable crop is better on water need, expected yield and energy at once.</p>
          </Card>
          <div className="grid gap-4 md:grid-cols-2">
            {s.data.data.map((c) => (
              <Card key={c.crop} title={<span className="flex items-center gap-2">{CROP_NAME[c.crop] ?? c.crop} <SuitBadge cls={c.overall} /></span>}>
                <ul className="space-y-1 text-sm text-muted">
                  {c.limiting_factors.length > 0 && <li>Limited by: <strong className="text-foreground">{c.limiting_factors.join(", ")}</strong></li>}
                  {c.undetermined_factors.length > 0 && <li>Cannot judge (missing data): {c.undetermined_factors.join(", ")}</li>}
                  {c.provisional_warnings.map((w) => <li key={w}>Warning: {w}</li>)}
                  {c.factors.filter((f) => f.factor === "water" && f.note).map((f) => <li key="w">{f.note}</li>)}
                </ul>
              </Card>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
