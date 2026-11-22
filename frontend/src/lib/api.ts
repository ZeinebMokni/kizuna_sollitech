"use client";

import { useEffect, useState } from "react";

/* ---- Types mirroring the engine API (qatra_ai.service.app). Subset used by the UI. ---- */

export interface Meta {
  farm_id: string;
  demo: boolean;
  note: string;
  [key: string]: unknown;
}
export interface Envelope<T> {
  meta: Meta;
  data: T;
}
export interface Quantity {
  value: number;
  unit: string;
}

export interface Zone {
  zone_id: string;
  name: string;
  crop: string;
  crop_name: Record<string, string>;
  area_ha: number;
  season_start: string;
  design_flow_m3h: number;
  polygon: [number, number][];
}
export interface FarmInfo {
  name: string;
  latitude: number;
  longitude: number;
  default_day: string;
  day_range: [string, string];
  zones: Zone[];
  pv_rated_kw: number;
  max_volume_per_day_m3: number;
  soil: { theta_fc: number; theta_wp: number; data_class: string; source: string };
}

export interface Reason {
  code: string;
  text: string;
}
export interface DecisionPackage {
  package_id: string;
  rank: number;
  tier: number;
  tier_label: string;
  action: string;
  target: string;
  amount: Quantity | null;
  windows: string[];
  requires_human_approval: boolean;
  reasons: Reason[];
  supporting_measurements: { what?: string; quantity?: Quantity; provenance?: { data_class: string; source: string } | null }[];
  constraints: string[];
  confidence: string;
  confidence_reasons: string[];
  expected_impact: Record<string, Quantity>;
  alternatives: Record<string, string>[];
  data_limitations: string[];
  priority_trace: string[];
}
export interface SlotAction {
  zone_id: string;
  slot: number;
  start: string;
  end: string;
  volume_m3: number;
}
export interface ZonePlan {
  zone_id: string;
  volume_m3: number;
  irrigation_hours: number;
  stress_mm_h: number;
  stress_mm_h_without_irrigation: number;
  reasons: string[];
  raw_mm: number;
  taw_mm: number;
  depletion_start_mm: number;
  depletion_end_mm: number;
  weight_summary: string;
}
export interface SchedulePlan {
  status: string;
  solver: string;
  solve_time_s: number;
  actions: SlotAction[];
  zones: ZonePlan[];
  totals: Record<string, number>;
  constraints: { name: string; binding_slots: number; shadow_price: number | null; shadow_price_meaning: string | null }[];
  unweighted_comparison: Record<string, number> | null;
  assumptions: string[];
  verification_violations: string[];
}
export interface DecisionEnvelope {
  confidence: string;
  confidence_reasons: string[];
  limitations: string[];
  model: { model_id: string; validation_status: string };
  payload: {
    farm_id: string;
    as_of: string;
    packages: DecisionPackage[];
    schedule: SchedulePlan | null;
    schedule_start: string | null;
    anomalies_detected: number;
  } | null;
}

export interface BalanceRow {
  date: string;
  stage: string;
  taw_mm: number;
  raw_mm: number;
  dr_end_mm: number;
  ks: number;
  etc_mm: number;
  eta_mm: number;
  precip_mm: number;
  peff_mm: number;
  irrigation_gross_mm: number;
}

export interface Factor {
  factor: string;
  suitability: string;
  value: number | null;
  unit: string | null;
  rule: string;
  note: string | null;
  provisional: boolean;
}
export interface CropSuitability {
  crop: string;
  planting: string;
  overall: string;
  limiting_factors: string[];
  undetermined_factors: string[];
  provisional_warnings: string[];
  factors: Factor[];
  indicators: Record<string, number | null>;
  pareto_optimal: boolean | null;
  seasons_evaluated: number;
}

export interface Hypothesis {
  cause: string;
  likelihood: string;
  evidence: string[];
}
export interface AnomalyEvent {
  kind: string;
  start: string;
  end: string;
  detected_at: string;
  hours: number;
  estimated_volume_m3: number | null;
  severity: string;
  confidence: string;
  hypotheses: Hypothesis[];
  recommended_checks: string[];
  zone_id: string | null;
}

/* ---- Fetch hook ---- */

export function useApi<T>(path: string | null) {
  // Result is stored with the path it belongs to; "loading" is derived, so no setState runs
  // synchronously inside the effect.
  const [state, setState] = useState<{ path?: string; data?: Envelope<T>; error?: string }>({});
  useEffect(() => {
    if (!path) return;
    let cancelled = false;
    fetch(path)
      .then(async (r) => {
        const body = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(body?.detail ?? `HTTP ${r.status}`);
        return body as Envelope<T>;
      })
      .then((data) => !cancelled && setState({ path, data }))
      .catch(
        (e: Error) =>
          !cancelled &&
          setState({
            path,
            error: e.message.includes("fetch")
              ? "Engine API unreachable (is it running on port 8100?)"
              : e.message,
          }),
      );
    return () => {
      cancelled = true;
    };
  }, [path]);
  const current = state.path === path;
  return {
    data: current ? state.data : undefined,
    error: current ? state.error : undefined,
    loading: !!path && !current,
  };
}

export interface FarmSummary {
  farm_id: string;
  name: string;
  kind: string;
  mode: string;
  region: string;
  latitude: number;
  longitude: number;
  zones: number;
  area_ha: number;
  crops: string[];
}

export function useSelectedFarm() {
  const [farmId, setFarmIdState] = useState<string>(() =>
    typeof window === "undefined" ? "demo-farm" : window.localStorage.getItem("qatra-farm") || "demo-farm",
  );
  const setFarmId = (value: string) => {
    window.localStorage.setItem("qatra-farm", value);
    setFarmIdState(value);
  };
  return { farmId, setFarmId };
}
