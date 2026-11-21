"""Unified decision orchestrator: "where should we intervene first?" (blueprint section 2.11).

Pipeline for one farm at one moment:
  1. quality gate      zones without a usable current water state -> insufficient_evidence
  2. agronomy          per zone: days to stress, severe stress within horizon, stage Ky
  3. anomalies         optional hydraulic data -> leak/burst events
  4. safety veto       zones with an open HIGH-severity leak/burst are held (not irrigated)
                       and get an "inspect" package first
  5. optimisation      72 h multi-zone schedule (verified against hard constraints)
  6. prioritisation    lexicographic tiers (no hidden score):
                         0 safety  1 irreversible risk  2 stress within horizon  3 no action
                       ties broken by time to stress, then avoided stress per m3
  7. decision packages action, reasons, measurements, constraints, confidence, impact,
                       alternatives, data limitations; physical actions ALWAYS need approval

Nothing here actuates hardware. Packages are proposals for human review.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field

from qatra_ai.agronomy.water_balance import ZoneSetup
from qatra_ai.contracts import (
    Confidence,
    DataClass,
    EngineEnvelope,
    ModelInfo,
    Provenance,
    Quantity,
    ValidationStatus,
    inputs_hash,
)
from qatra_ai.optimization.inputs import pv_slots_from_daily_radiation, zone_from_forecast
from qatra_ai.optimization.irrigation_scheduler import plan_irrigation, simulate_zone
from qatra_ai.optimization.schedule_models import (
    BatterySpec,
    EnergySupply,
    PriorityPolicy,
    PumpSystem,
    ScheduleRequest,
    WaterSource,
)
from qatra_ai.predictive.anomaly import AnomalyEvent, DetectorConfig, detect_anomalies

ENGINE = "orchestrator.farm_decision"
MODEL = ModelInfo(
    model_id="lexicographic_intervention_priority",
    version="0.1.0",
    validation_status=ValidationStatus.LITERATURE_PARAMETERISED,
    references=["AI_ENGINE_BLUEPRINT.md section 2.11"],
)
_ORDER = [Confidence.INSUFFICIENT_EVIDENCE, Confidence.LOW, Confidence.MEDIUM, Confidence.HIGH]
LEAK_KINDS = {"flow_excess", "pressure_drop", "idle_flow", "zone_mismatch", "slow_leak"}

ActionType = Literal[
    "irrigate", "accept_deficit", "no_action", "inspect", "hold_zone", "insufficient_evidence"
]


# --- Inputs ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class ZoneContext:
    zone_id: str
    setup: ZoneSetup
    design_flow_m3h: float
    depletion_mm: float | None
    depletion_provenance: Provenance | None
    depletion_std_mm: float | None = None


@dataclass(frozen=True)
class HydraulicData:
    data: pd.DataFrame  # see predictive.anomaly
    schedule: pd.DataFrame
    design_flow_m3h: dict[str, float]


@dataclass(frozen=True)
class FarmContext:
    farm_id: str
    as_of: datetime  # start of the planning horizon (local time)
    zones: list[ZoneContext]
    forecast_daily: pd.DataFrame  # et0, precip, rs for >= 3 days from as_of
    forecast_source: str
    pump: PumpSystem
    pv_rated_kw: float = 0.0
    battery: BatterySpec | None = None
    grid_hours: frozenset[int] = frozenset()
    grid_max_kw: float = 0.0
    max_volume_per_day_m3: float | None = None
    hydraulics: HydraulicData | None = None
    policy: PriorityPolicy = field(default_factory=PriorityPolicy)
    horizon_h: int = 72


# --- Outputs ---------------------------------------------------------------------------------


class Reason(BaseModel):
    code: str
    text: str


class DecisionPackage(BaseModel):
    package_id: str
    rank: int
    tier: int
    tier_label: str
    action: ActionType
    target: str
    amount: Quantity | None = None
    windows: list[str] = Field(default_factory=list)
    requires_human_approval: bool
    reasons: list[Reason]
    supporting_measurements: list[dict]
    constraints: list[str]
    confidence: Confidence
    confidence_reasons: list[str]
    expected_impact: dict[str, Quantity]
    alternatives: list[dict]
    data_limitations: list[str]
    priority_trace: list[str]


class FarmDecision(BaseModel):
    farm_id: str
    as_of: datetime
    packages: list[DecisionPackage]
    schedule_status: str | None
    anomalies_detected: int
    notes: list[str]


TIER_LABELS = {0: "safety", 1: "irreversible risk", 2: "stress within horizon", 3: "no action"}


@dataclass
class _ZoneView:
    ctx: ZoneContext
    days_to_stress: float | None = None
    severe_within: bool = False
    ky_now: float | None = None
    perennial: bool = False
    raw: float = 0.0
    taw: float = 0.0
    held_by: list[AnomalyEvent] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _cap(a: Confidence, b: Confidence) -> Confidence:
    return min(a, b, key=_ORDER.index)


def _q(v: float, unit: str) -> Quantity:
    return Quantity(value=round(float(v), 2), unit=unit)


def decide(ctx: FarmContext, request_id: str | None = None) -> EngineEnvelope[FarmDecision]:
    request_id = request_id or str(uuid.uuid4())
    notes: list[str] = []
    packages: list[dict] = []
    views: list[_ZoneView] = []

    # 1. quality gate ------------------------------------------------------------------------
    usable: list[ZoneContext] = []
    for z in ctx.zones:
        if z.depletion_mm is None or z.depletion_provenance is None:
            packages.append(
                dict(
                    tier=1 if z.setup.crop.perennial else 2,
                    sort=(0.0, 0.0),
                    action="insufficient_evidence",
                    target=z.zone_id,
                    approval=False,
                    reasons=[
                        Reason(code="NO_WATER_STATE", text="current root-zone water state unknown")
                    ],
                    measurements=[],
                    constraints=[],
                    confidence=Confidence.INSUFFICIENT_EVIDENCE,
                    conf_reasons=["no soil-moisture estimate or measurement available"],
                    impact={},
                    alternatives=[
                        {"action": "inspect", "note": "check soil moisture by hand or sensor"}
                    ],
                    limitations=["zone excluded from scheduling"],
                    trace=[
                        "placed high in its tier because the state is unknown, not because "
                        "stress is confirmed"
                    ],
                )
            )
        else:
            usable.append(z)

    # 3. anomalies + 4. safety veto ------------------------------------------------------------
    events: list[AnomalyEvent] = []
    if ctx.hydraulics is not None:
        h = ctx.hydraulics
        events = detect_anomalies(
            h.data, h.schedule, DetectorConfig(design_flow_m3h=h.design_flow_m3h)
        ).events
        recent_cut = pd.Timestamp(ctx.as_of) - pd.Timedelta(hours=48)
        for e in events:
            if pd.Timestamp(e.end) < recent_cut:
                continue
            high = e.severity == "high" and e.kind in LEAK_KINDS
            packages.append(
                dict(
                    tier=0 if high else 2,
                    sort=(0.0, -(e.estimated_volume_m3 or 0.0)),
                    action="inspect",
                    target=e.zone_id or "mainline/network",
                    approval=False,
                    reasons=[
                        Reason(
                            code=f"ANOMALY_{e.kind.upper()}",
                            text=e.hypotheses[0].cause if e.hypotheses else e.kind,
                        )
                    ],
                    measurements=[
                        {
                            "event": e.kind,
                            "start": str(e.start),
                            "end": str(e.end),
                            "estimated_volume_m3": e.estimated_volume_m3,
                            "evidence": [ev for hy in e.hypotheses for ev in hy.evidence][:3],
                            "data_class": DataClass.MEASURED.value,
                        }
                    ],
                    constraints=[],
                    confidence=Confidence(e.confidence),
                    conf_reasons=[f"anomaly detector confidence {e.confidence}"],
                    impact={}
                    if e.estimated_volume_m3 is None
                    else {"water_unaccounted": _q(e.estimated_volume_m3, "m3")},
                    alternatives=[
                        {
                            "action": "continue monitoring",
                            "note": "risk: further water loss if the cause is a leak",
                        }
                    ],
                    limitations=[
                        "possible causes are hypotheses; nothing is concluded about people"
                    ]
                    + [f"check: {c}" for c in e.recommended_checks],
                    trace=[
                        f"tier {'0 (high-severity leak/burst)' if high else '2'}; "
                        f"severity {e.severity}"
                    ],
                )
            )

    # 2. agronomy views ----------------------------------------------------------------------
    start = ctx.as_of
    sched_zones = []
    for z in usable:
        v = _ZoneView(ctx=z, perennial=z.setup.crop.perennial)
        sz = zone_from_forecast(
            z.zone_id,
            z.setup,
            current_depletion_mm=z.depletion_mm,
            forecast_daily=ctx.forecast_daily,
            start=start,
            n_slots=ctx.horizon_h,
            design_flow_m3h=z.design_flow_m3h,
        )
        base = simulate_zone(sz, [0] * ctx.horizon_h, 0.0)
        dsev = sz.raw_mm + ctx.policy.severe_fraction * (sz.taw_mm - sz.raw_mm)
        over = [t for t in range(1, len(base)) if base[t] > sz.raw_mm]
        v.days_to_stress = (over[0] - 1) / 24 if over else None
        if base[0] > sz.raw_mm:
            v.days_to_stress = 0.0
        v.severe_within = any(d > dsev for d in base[1:])
        v.ky_now = None if sz.ky_assumed else sz.ky[0]
        v.raw, v.taw = sz.raw_mm, sz.taw_mm
        v.held_by = [
            e
            for e in events
            if e.zone_id == z.zone_id
            and e.severity == "high"
            and e.kind in LEAK_KINDS
            and pd.Timestamp(e.end) >= pd.Timestamp(ctx.as_of) - pd.Timedelta(hours=48)
        ]
        views.append(v)
        sched_zones.append(sz)

    # 5. optimisation (zones held by the safety veto are excluded) ----------------------------
    plan_env = None
    plan = None
    held = {v.ctx.zone_id for v in views if v.held_by}
    keep = [sz for sz in sched_zones if sz.zone_id not in held]
    if keep:
        rs = ctx.forecast_daily.get("rs", None)
        pv = (
            pv_slots_from_daily_radiation(
                rs, start=start, n_slots=ctx.horizon_h, p_rated_kw=ctx.pv_rated_kw
            )
            if ctx.pv_rated_kw > 0 and rs is not None
            else [0.0] * ctx.horizon_h
        )
        req = ScheduleRequest(
            start=start,
            n_slots=ctx.horizon_h,
            zones=keep,
            pump=ctx.pump,
            water=WaterSource(max_volume_per_day_m3=ctx.max_volume_per_day_m3),
            energy=EnergySupply(
                pv_kwh=pv,
                grid_available=[
                    (start + timedelta(hours=t)).hour in ctx.grid_hours
                    for t in range(ctx.horizon_h)
                ],
                grid_max_kw=ctx.grid_max_kw,
                battery=ctx.battery,
            ),
            policy=ctx.policy,
        )
        input_conf = Confidence.HIGH
        in_reasons = []
        for v in views:
            prov = v.ctx.depletion_provenance
            if prov and prov.data_class not in (DataClass.MEASURED,):
                input_conf = _cap(input_conf, Confidence.MEDIUM)
                in_reasons.append(f"{v.ctx.zone_id}: water state is {prov.data_class.value}")
            if v.ctx.setup.crop.review_status != "reviewed":
                input_conf = _cap(input_conf, Confidence.MEDIUM)
        plan_env = plan_irrigation(
            req, input_confidence=input_conf, input_reasons=sorted(set(in_reasons))
        )
        plan = plan_env.payload
        if plan is None:
            notes.append("scheduler returned no plan: " + "; ".join(plan_env.confidence_reasons))

    # 6-7. zone packages ------------------------------------------------------------------------
    zp = {z.zone_id: z for z in plan.zones} if plan else {}
    binding = (
        [
            f"{c.name} binding in {c.binding_slots} "
            + ("day(s)" if c.name == "water_daily_cap" else "slot(s)")
            for c in plan.constraints
            if c.binding_slots
        ]
        if plan
        else []
    )
    day_end = start + timedelta(hours=24)
    for v in views:
        zid = v.ctx.zone_id
        prov = v.ctx.depletion_provenance
        meas = [
            {
                "quantity": _q(v.ctx.depletion_mm, "mm").model_dump(),
                "what": "root-zone depletion",
                "provenance": prov.model_dump(mode="json") if prov else None,
            },
            {"quantity": _q(v.raw, "mm").model_dump(), "what": "readily available water"},
        ]
        conf = plan_env.confidence if plan_env else Confidence.LOW
        conf_reasons = list(plan_env.confidence_reasons) if plan_env else []
        limitations = list(v.ctx.setup.crop.limitations)
        if v.ky_now is None:
            limitations.append("stage sensitivity (Ky) unknown for this crop; default weight used")

        if v.held_by:
            packages.append(
                dict(
                    tier=0,
                    sort=(v.days_to_stress if v.days_to_stress is not None else 99, 0.0),
                    action="hold_zone",
                    target=zid,
                    approval=True,
                    reasons=[
                        Reason(
                            code="SAFETY_HOLD",
                            text=f"high-severity {v.held_by[0].kind} detected in this zone; "
                            "irrigating could waste water or worsen damage",
                        )
                    ],
                    measurements=meas,
                    constraints=["safety veto"],
                    confidence=conf,
                    conf_reasons=conf_reasons,
                    impact={},
                    alternatives=[
                        {
                            "action": "irrigate anyway after visual check",
                            "note": "only if the anomaly is confirmed as a false alarm",
                        }
                    ],
                    limitations=limitations,
                    trace=["tier 0: safety veto overrides agronomic priority"],
                )
            )
            continue

        z = zp.get(zid)
        actions = [
            a for a in (plan.actions if plan else []) if a.zone_id == zid and a.start < day_end
        ]
        vol24 = sum(a.volume_m3 for a in actions)
        irreversible = (v.perennial and v.severe_within) or (
            (v.ky_now or 0) >= 1.0 and v.days_to_stress is not None and v.days_to_stress <= 1
        )
        stressed = v.days_to_stress is not None
        tier = 1 if irreversible else (2 if stressed else 3)
        trace = [f"tier {tier} ({TIER_LABELS[tier]})"]
        if irreversible:
            trace.append(
                "perennial heading for severe stress"
                if v.perennial and v.severe_within
                else f"sensitive stage (Ky {v.ky_now}) and stress within 1 day"
            )
        if stressed:
            trace.append(f"days to stress without action: {v.days_to_stress:.1f}")
        avoided = (z.stress_mm_h_without_irrigation - z.stress_mm_h) if z else 0.0
        per_m3 = avoided / z.volume_m3 if z and z.volume_m3 > 0 else 0.0
        if per_m3:
            trace.append(f"avoided stress per m3: {per_m3:.2f} mm h")

        impact = {}
        if z:
            impact = {"stress_avoided": _q(avoided, "mm h"), "water_72h": _q(z.volume_m3, "m3")}
        if vol24 > 0:
            action, amount = "irrigate", _q(vol24, "m3")
            reasons = [
                Reason(
                    code="STRESS_FORECAST" if stressed else "TOP_UP",
                    text=(
                        "root zone is already beyond the stress threshold"
                        if stressed and v.days_to_stress == 0
                        else f"stress expected in {v.days_to_stress:.1f} days without irrigation"
                    )
                    if stressed
                    else "scheduled to keep the zone above its threshold",
                )
            ]
            alts = [
                {
                    "action": "skip irrigation for 72 h",
                    "consequence": f"stress {z.stress_mm_h_without_irrigation:.0f} mm h"
                    if z
                    else "unknown",
                }
            ]
        elif stressed:
            action, amount = "accept_deficit", None
            codes = z.reasons if z else ["NO_PLAN"]
            details = z.reason_details if z else []
            reasons = []
            for c in codes:
                hits = [d.split(": ", 1)[-1] for d in details if d.startswith(c)]
                reasons.append(Reason(code=c, text="; ".join(hits) if hits else c))
            alts = [
                {
                    "action": "add water or energy capacity",
                    "note": "see constraint shadow prices in the schedule",
                }
            ]
        else:
            action, amount = "no_action", None
            reasons = [
                Reason(
                    code="NO_STRESS_EXPECTED", text=f"no stress expected within {ctx.horizon_h} h"
                )
            ]
            alts = []
        packages.append(
            dict(
                tier=tier,
                sort=(v.days_to_stress if v.days_to_stress is not None else 99.0, -per_m3),
                action=action,
                target=zid,
                amount=amount,
                windows=[a.start.strftime("%Y-%m-%d %H:%M") for a in actions],
                approval=action == "irrigate",
                reasons=reasons,
                measurements=meas,
                constraints=binding if action in ("irrigate", "accept_deficit") else [],
                confidence=conf,
                conf_reasons=conf_reasons,
                impact=impact,
                alternatives=alts,
                limitations=limitations,
                trace=trace,
            )
        )

    # rank ----------------------------------------------------------------------------------------
    packages.sort(key=lambda p: (p["tier"], p["sort"]))
    out = []
    for i, p in enumerate(packages, start=1):
        out.append(
            DecisionPackage(
                package_id=f"{ctx.farm_id}-{i}",
                rank=i,
                tier=p["tier"],
                tier_label=TIER_LABELS[p["tier"]],
                action=p["action"],
                target=p["target"],
                amount=p.get("amount"),
                windows=p.get("windows", []),
                requires_human_approval=p["approval"] or p["action"] in ("hold_zone", "irrigate"),
                reasons=p["reasons"],
                supporting_measurements=p["measurements"],
                constraints=p["constraints"],
                confidence=p["confidence"],
                confidence_reasons=p["conf_reasons"],
                expected_impact=p["impact"],
                alternatives=p["alternatives"],
                data_limitations=p["limitations"],
                priority_trace=p["trace"]
                + [f"rank {i}: ordered by tier, then time to stress, then avoided stress per m3"],
            )
        )
    overall = min((p.confidence for p in out), key=_ORDER.index, default=Confidence.LOW)
    payload = FarmDecision(
        farm_id=ctx.farm_id,
        as_of=ctx.as_of,
        packages=out,
        schedule_status=plan.status if plan else None,
        anomalies_detected=len(events),
        notes=notes,
    )
    snapshot = {
        "farm": ctx.farm_id,
        "as_of": str(ctx.as_of),
        "zones": [(z.zone_id, z.depletion_mm) for z in ctx.zones],
        "forecast": ctx.forecast_daily.reset_index().astype(str).to_dict("records"),
    }
    return EngineEnvelope[FarmDecision](
        request_id=request_id,
        engine=ENGINE,
        model=MODEL,
        inputs_hash=inputs_hash(snapshot),
        confidence=overall,
        confidence_reasons=["overall = weakest package confidence"],
        limitations=[
            "Packages are proposals; physical actions require human approval.",
            "Priority tiers are a documented rule, not a learned model.",
        ],
        payload=payload,
    )
