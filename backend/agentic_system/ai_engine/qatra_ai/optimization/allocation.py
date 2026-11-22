"""Critical water allocation between pump-irrigated farms sharing an aquifer
(AI_ENGINE_BLUEPRINT section 6.2, adapted to groundwater pumping).

The engine COMPARES strategies and shows their consequences. It never declares a strategy
fair, legal or authorised. Choosing one is a decision for a legitimate governing body
(e.g. a water users' association or the regional water authority) with the farmers concerned.

Per crop block b of farm f, over one period (e.g. a week or a season):
    demand d_b [m3], allocation 0 <= a_b <= d_b, deficit ratio r_b = 1 - a_b / d_b
    loss_b = A_b * Ky_b * r_b  +  kappa * A_b * max(0, r_b - tau_b)  [perennials only]
             (FAO-33 seasonal yield response + irreversibility penalty beyond a survival
              threshold tau_b; unit: hectare-equivalents of yield lost)
Constraints:
    sum_b in f a_b <= pump_capacity_f            (infrastructure)
    sum_f in k a_f <= alpha_k * SY_k - H_k       (aquifer protection; human needs served first)

Strategies:
    S1 proportional to permits (or to demand when permits are unknown), with caps
    S2 equal depth per hectare, with caps
    S3 crop priority: perennials, then annuals by descending Ky
    S4 minimum total weighted loss (LP)
    S5 minimum loss with floors: >= rho * S1 share, and satisfaction >= phi
    S6 max-min satisfaction, then minimum loss among max-min solutions
"""

from __future__ import annotations

import uuid
from typing import Literal

from ortools.linear_solver import pywraplp
from pydantic import BaseModel, ConfigDict, Field, model_validator

from qatra_ai.contracts import (
    Confidence,
    EngineEnvelope,
    ModelInfo,
    ValidationStatus,
    inputs_hash,
)

ENGINE = "optimization.water_allocation"
MODEL = ModelInfo(
    model_id="lp_aquifer_allocation",
    version="0.1.0",
    validation_status=ValidationStatus.LITERATURE_PARAMETERISED,
    references=["AI_ENGINE_BLUEPRINT.md section 6.2", "FAO-33 Ky"],
)
DISCLAIMER = (
    "Decision support only: this compares consequences of allocation strategies. It is not an "
    "allocation order and does not establish fairness, legality or water rights."
)
EPS = 1e-9
StrategyId = Literal["S1", "S2", "S3", "S4", "S5", "S6"]
STRATEGY_NAMES = {
    "S1": "Proportional to permits",
    "S2": "Equal depth per hectare",
    "S3": "Crop priority (perennials, then by Ky)",
    "S4": "Minimum total loss",
    "S5": "Minimum loss with fairness floors",
    "S6": "Max-min satisfaction, then minimum loss",
}


# --- Inputs ----------------------------------------------------------------------------------


class CropBlock(BaseModel):
    model_config = ConfigDict(frozen=True)

    block_id: str
    crop: str
    area_ha: float = Field(gt=0)
    demand_m3: float = Field(ge=0, description="Gross irrigation demand for the period")
    ky: float | None = Field(default=None, gt=0)
    perennial: bool = False
    survival_threshold: float = Field(
        default=0.5,
        gt=0,
        lt=1,
        description="Deficit ratio beyond which perennial damage is treated as long-lasting "
        "(placeholder; must be set with agronomists)",
    )


class Farm(BaseModel):
    model_config = ConfigDict(frozen=True)

    farm_id: str
    aquifer_id: str
    blocks: list[CropBlock] = Field(min_length=1)
    pump_capacity_m3: float = Field(ge=0, description="Max volume the farm can pump in the period")
    permit_m3: float | None = Field(default=None, ge=0)
    vulnerability_weight: float = Field(
        default=1.0, ge=1.0, description="Policy input (e.g. smallholder, no alternative source)"
    )

    @property
    def demand_m3(self) -> float:
        return sum(b.demand_m3 for b in self.blocks)

    @property
    def area_ha(self) -> float:
        return sum(b.area_ha for b in self.blocks)


class AquiferUnit(BaseModel):
    model_config = ConfigDict(frozen=True)

    aquifer_id: str
    sustainable_yield_m3: float = Field(ge=0, description="For the period")
    allowed_fraction: float = Field(default=1.0, gt=0, le=1)
    human_reservation_m3: float = Field(default=0.0, ge=0)
    source_note: str = Field(description="Where SY and the reservation come from")

    @property
    def available_m3(self) -> float:
        return max(
            0.0, self.allowed_fraction * self.sustainable_yield_m3 - self.human_reservation_m3
        )


class AllocationPolicy(BaseModel):
    """Every value here is a policy choice to be set by the governing body, not by QATRA."""

    model_config = ConfigDict(frozen=True)

    kappa_irreversible: float = Field(default=5.0, ge=0)
    default_ky: float = Field(default=1.0, gt=0)
    rho_permit_floor: float = Field(default=0.5, ge=0, le=1, description="S5: share of S1 kept")
    phi_min_satisfaction: float = Field(default=0.3, ge=0, le=1, description="S5 floor")


class AllocationRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    period_label: str
    farms: list[Farm] = Field(min_length=1)
    aquifers: list[AquiferUnit] = Field(min_length=1)
    policy: AllocationPolicy = AllocationPolicy()
    strategies: list[StrategyId] = ["S1", "S2", "S3", "S4", "S5", "S6"]

    @model_validator(mode="after")
    def _refs(self) -> AllocationRequest:
        ids = {a.aquifer_id for a in self.aquifers}
        for f in self.farms:
            if f.aquifer_id not in ids:
                raise ValueError(f"farm {f.farm_id}: unknown aquifer {f.aquifer_id}")
        if len({f.farm_id for f in self.farms}) != len(self.farms):
            raise ValueError("farm ids must be unique")
        return self


# --- Outputs ---------------------------------------------------------------------------------


class FarmResult(BaseModel):
    farm_id: str
    allocation_m3: float
    demand_m3: float
    satisfaction: float
    loss_ha_eq: float
    irreversible_loss_ha_eq: float
    delta_vs_s1_m3: float | None
    blocks: dict[str, float]


class StrategyResult(BaseModel):
    strategy: StrategyId
    name: str
    feasible: bool
    note: str | None = None
    farms: list[FarmResult] = []
    total_allocated_m3: float = 0.0
    total_loss_ha_eq: float = 0.0
    weighted_loss: float = Field(
        default=0.0, description="Loss x farm vulnerability weight: the quantity S4/S5/S6 minimise"
    )
    irreversible_loss_ha_eq: float = 0.0
    fairness: dict[str, float] = {}
    marginal_loss_avoided_per_m3: dict[str, float] = Field(
        default_factory=dict, description="Per aquifer: LP dual of the supply constraint"
    )


class AllocationComparison(BaseModel):
    period_label: str
    available_by_aquifer_m3: dict[str, float]
    demand_by_aquifer_m3: dict[str, float]
    strategies: list[StrategyResult]
    policy: AllocationPolicy
    assumptions: list[str]
    disclaimer: str = DISCLAIMER


ASSUMPTIONS = [
    "Loss uses the FAO-33 seasonal linear yield response; staged effects are not modelled.",
    "The irreversibility penalty and survival thresholds are placeholders to be set with "
    "agronomists; they are not scientifically calibrated values.",
    "Loss is in hectare-equivalents of yield; it is not monetary.",
    "Demands are gross volumes for the period; within-period timing is ignored.",
    "Each farm draws from exactly one aquifer unit.",
]


# --- Helpers ---------------------------------------------------------------------------------


def _ky(b: CropBlock, pol: AllocationPolicy) -> float:
    return b.ky if b.ky is not None else pol.default_ky


def _block_loss(b: CropBlock, a: float, pol: AllocationPolicy) -> tuple[float, float]:
    if b.demand_m3 <= EPS:
        return 0.0, 0.0
    r = max(0.0, 1.0 - a / b.demand_m3)
    base = b.area_ha * _ky(b, pol) * r
    irr = (
        pol.kappa_irreversible * b.area_ha * max(0.0, r - b.survival_threshold)
        if b.perennial
        else 0.0
    )
    return base + irr, irr


def water_fill(weights: dict[str, float], caps: dict[str, float], total: float) -> dict[str, float]:
    """a_i = min(cap_i, lam * w_i) with sum a_i = min(total, sum caps) (bisection on lam)."""
    keys = [k for k in weights if caps[k] > EPS and weights[k] > EPS]
    if not keys or total <= EPS:
        return dict.fromkeys(weights, 0.0)
    target = min(total, sum(caps[k] for k in keys))
    lo, hi = 0.0, max(caps[k] / weights[k] for k in keys)
    for _ in range(200):
        lam = (lo + hi) / 2
        s = sum(min(caps[k], lam * weights[k]) for k in keys)
        if s < target:
            lo = lam
        else:
            hi = lam
    out = dict.fromkeys(weights, 0.0)
    for k in keys:
        out[k] = min(caps[k], hi * weights[k])
    return out


def _split_to_blocks(farm: Farm, a_farm: float, by: Literal["demand", "area"]) -> dict[str, float]:
    w = {b.block_id: (b.demand_m3 if by == "demand" else b.area_ha) for b in farm.blocks}
    caps = {b.block_id: b.demand_m3 for b in farm.blocks}
    return water_fill(w, caps, a_farm)


def _gini(xs: list[float]) -> float:
    n = len(xs)
    if n == 0 or sum(xs) <= EPS:
        return 0.0
    s = sorted(xs)
    cum = sum((i + 1) * v for i, v in enumerate(s))
    return (2 * cum) / (n * sum(s)) - (n + 1) / n


def _jain(xs: list[float]) -> float:
    if not xs or sum(v * v for v in xs) <= EPS:
        return 1.0
    return sum(xs) ** 2 / (len(xs) * sum(v * v for v in xs))


# --- Heuristic strategies (S1-S3) -----------------------------------------------------------------


def _heuristic(req: AllocationRequest, sid: StrategyId) -> dict[str, dict[str, float]]:
    """Returns block allocations per farm."""
    out: dict[str, dict[str, float]] = {}
    for aq in req.aquifers:
        farms = [f for f in req.farms if f.aquifer_id == aq.aquifer_id]
        caps = {f.farm_id: min(f.pump_capacity_m3, f.demand_m3) for f in farms}
        if sid == "S1":
            permits_known = all(f.permit_m3 is not None for f in farms)
            w = {f.farm_id: (f.permit_m3 if permits_known else f.demand_m3) or 0.0 for f in farms}
            alloc = water_fill(w, caps, aq.available_m3)
            for f in farms:
                out[f.farm_id] = _split_to_blocks(f, alloc[f.farm_id], "demand")
        elif sid == "S2":
            # Equal depth: weight by area, but block demand caps depth per block.
            w = {f.farm_id: f.area_ha for f in farms}
            alloc = water_fill(w, caps, aq.available_m3)
            for f in farms:
                out[f.farm_id] = _split_to_blocks(f, alloc[f.farm_id], "area")
        elif sid == "S3":
            remaining = aq.available_m3
            farm_room = {f.farm_id: f.pump_capacity_m3 for f in farms}
            blocks = [(f, b) for f in farms for b in f.blocks]
            blocks.sort(key=lambda fb: (not fb[1].perennial, -_ky(fb[1], req.policy)))
            for f in farms:
                out[f.farm_id] = {b.block_id: 0.0 for b in f.blocks}
            for f, b in blocks:
                give = max(0.0, min(b.demand_m3, remaining, farm_room[f.farm_id]))
                out[f.farm_id][b.block_id] = give
                remaining -= give
                farm_room[f.farm_id] -= give
    return out


# --- LP strategies (S4-S6) ----------------------------------------------------------


def _lp(
    req: AllocationRequest,
    sid: StrategyId,
    s1: dict[str, dict[str, float]] | None,
) -> tuple[dict[str, dict[str, float]] | None, str | None, dict[str, float]]:
    pol = req.policy

    def build(max_min: bool, theta_floor: float | None):
        solver = pywraplp.Solver.CreateSolver("GLOP")
        a, loss_terms = {}, []
        for f in req.farms:
            for b in f.blocks:
                a[f.farm_id, b.block_id] = solver.NumVar(
                    0, b.demand_m3, f"a_{f.farm_id}_{b.block_id}"
                )
        supply = {}
        for aq in req.aquifers:
            supply[aq.aquifer_id] = solver.Add(
                sum(
                    a[f.farm_id, b.block_id]
                    for f in req.farms
                    if f.aquifer_id == aq.aquifer_id
                    for b in f.blocks
                )
                <= aq.available_m3
            )
        for f in req.farms:
            solver.Add(sum(a[f.farm_id, b.block_id] for b in f.blocks) <= f.pump_capacity_m3)
        theta = solver.NumVar(0, 1, "theta") if max_min else None
        for f in req.farms:
            fa = sum(a[f.farm_id, b.block_id] for b in f.blocks)
            if f.demand_m3 > EPS:
                if max_min:
                    solver.Add(fa >= theta * f.demand_m3)
                if theta_floor is not None:
                    solver.Add(fa >= theta_floor * f.demand_m3)
                if sid == "S5" and s1 is not None:
                    solver.Add(fa >= pol.rho_permit_floor * sum(s1[f.farm_id].values()))
                    solver.Add(fa >= pol.phi_min_satisfaction * f.demand_m3)
            for b in f.blocks:
                if b.demand_m3 <= EPS:
                    continue
                r = 1 - a[f.farm_id, b.block_id] * (1.0 / b.demand_m3)  # deficit ratio (linear)
                coef = f.vulnerability_weight * b.area_ha
                loss_terms.append(coef * _ky(b, pol) * r)
                if b.perennial:
                    m = solver.NumVar(0, 1, f"m_{f.farm_id}_{b.block_id}")
                    solver.Add(m >= r - b.survival_threshold)
                    loss_terms.append(coef * pol.kappa_irreversible * m)
        if max_min:
            solver.Maximize(theta)
        else:
            solver.Minimize(sum(loss_terms))
        return solver, a, supply, theta

    theta_floor = None
    if sid == "S6":
        solver, a, supply, theta = build(max_min=True, theta_floor=None)
        if solver.Solve() != pywraplp.Solver.OPTIMAL:
            return None, "max-min stage failed", {}
        theta_floor = max(0.0, theta.solution_value() - 1e-7)

    solver, a, supply, _ = build(max_min=False, theta_floor=theta_floor)
    status = solver.Solve()
    if status != pywraplp.Solver.OPTIMAL:
        note = "infeasible"
        if sid == "S5":
            probe, _, _, th = build(max_min=True, theta_floor=None)
            probe.Solve()
            note = (
                f"infeasible: floors cannot all be met (phi={pol.phi_min_satisfaction}, "
                f"rho={pol.rho_permit_floor}); the highest equal satisfaction any allocation "
                f"can guarantee is {th.solution_value():.3f}"
            )
        return None, note, {}
    alloc = {
        f.farm_id: {b.block_id: a[f.farm_id, b.block_id].solution_value() for b in f.blocks}
        for f in req.farms
    }
    duals = {k: abs(c.dual_value()) for k, c in supply.items()}
    return alloc, None, duals


# --- Evaluation ----------------------------------------------------------------------------------


def _evaluate(
    req: AllocationRequest,
    sid: StrategyId,
    alloc: dict[str, dict[str, float]],
    s1_tot: dict[str, float] | None,
    duals: dict[str, float],
) -> StrategyResult:
    farms_out = []
    sats = []
    tot_loss = tot_irr = tot_alloc = tot_weighted = 0.0
    for f in req.farms:
        blocks = alloc[f.farm_id]
        a_f = sum(blocks.values())
        loss = irr = 0.0
        for b in f.blocks:
            l_b, i_b = _block_loss(b, blocks[b.block_id], req.policy)
            loss += l_b
            irr += i_b
        sat = a_f / f.demand_m3 if f.demand_m3 > EPS else 1.0
        sats.append(sat)
        tot_loss += loss
        tot_weighted += loss * f.vulnerability_weight
        tot_irr += irr
        tot_alloc += a_f
        farms_out.append(
            FarmResult(
                farm_id=f.farm_id,
                allocation_m3=round(a_f, 3),
                demand_m3=round(f.demand_m3, 3),
                satisfaction=round(sat, 4),
                loss_ha_eq=round(loss, 4),
                irreversible_loss_ha_eq=round(irr, 4),
                delta_vs_s1_m3=None if s1_tot is None else round(a_f - s1_tot[f.farm_id], 3),
                blocks={k: round(v, 3) for k, v in blocks.items()},
            )
        )
    return StrategyResult(
        strategy=sid,
        name=STRATEGY_NAMES[sid],
        feasible=True,
        farms=farms_out,
        total_allocated_m3=round(tot_alloc, 3),
        total_loss_ha_eq=round(tot_loss, 4),
        weighted_loss=round(tot_weighted, 4),
        irreversible_loss_ha_eq=round(tot_irr, 4),
        fairness={
            "gini_satisfaction": round(_gini(sats), 4),
            "jain_satisfaction": round(_jain(sats), 4),
            "min_satisfaction": round(min(sats), 4),
        },
        marginal_loss_avoided_per_m3={k: round(v, 8) for k, v in duals.items()},
    )


def compare_allocations(
    req: AllocationRequest,
    *,
    input_confidence: Confidence = Confidence.MEDIUM,
    input_reasons: list[str] | None = None,
    request_id: str | None = None,
) -> EngineEnvelope[AllocationComparison]:
    results: list[StrategyResult] = []
    s1 = _heuristic(req, "S1")
    s1_tot = {fid: sum(v.values()) for fid, v in s1.items()}
    for sid in req.strategies:
        if sid in ("S1", "S2", "S3"):
            alloc = s1 if sid == "S1" else _heuristic(req, sid)
            results.append(_evaluate(req, sid, alloc, s1_tot, {}))
        else:
            alloc, note, duals = _lp(req, sid, s1)
            if alloc is None:
                results.append(
                    StrategyResult(
                        strategy=sid, name=STRATEGY_NAMES[sid], feasible=False, note=note
                    )
                )
            else:
                results.append(_evaluate(req, sid, alloc, s1_tot, duals))

    reasons = list(input_reasons or [])
    conf = input_confidence
    if any(b.ky is None for f in req.farms for b in f.blocks):
        reasons.append("Ky missing for some crop blocks; default weight used")
        if conf == Confidence.HIGH:
            conf = Confidence.MEDIUM
    if any(f.permit_m3 is None for f in req.farms):
        reasons.append("permits unknown for some farms: S1 uses demand-proportional shares")

    payload = AllocationComparison(
        period_label=req.period_label,
        available_by_aquifer_m3={a.aquifer_id: round(a.available_m3, 3) for a in req.aquifers},
        demand_by_aquifer_m3={
            a.aquifer_id: round(
                sum(f.demand_m3 for f in req.farms if f.aquifer_id == a.aquifer_id), 3
            )
            for a in req.aquifers
        },
        strategies=results,
        policy=req.policy,
        assumptions=ASSUMPTIONS + [f"{a.aquifer_id}: {a.source_note}" for a in req.aquifers],
    )
    return EngineEnvelope[AllocationComparison](
        request_id=request_id or str(uuid.uuid4()),
        engine=ENGINE,
        model=MODEL,
        inputs_hash=inputs_hash(req.model_dump(mode="json")),
        confidence=conf,
        confidence_reasons=reasons,
        limitations=ASSUMPTIONS + [DISCLAIMER],
        payload=payload,
    )
