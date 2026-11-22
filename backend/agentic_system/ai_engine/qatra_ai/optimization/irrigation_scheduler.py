"""Multi-zone irrigation scheduling as a mixed-integer linear program (OR-Tools / SCIP).

Formulation (AI_ENGINE_BLUEPRINT section 6.1), slots t = 0..T-1 of length dt hours:

  x[z,t] in {0,1}                       zone z irrigates during slot t
  D[z,t+1] >= D[z,t] + ETc - Peff - d_z x[z,t],  D >= 0      depletion dynamics [mm]
  s[z,t]   >= D[z,t] - RAW_z,  s >= 0                         stress beyond RAW
  s2[z,t]  >= D[z,t] - Dsev_z, s2 >= 0                        severe stress tier
  sum_z Q_z x[z,t] <= Q_max ;  sum_z x[z,t] <= N_max ;  x[z,t] <= allowed[t]
  sum_z e_z x[z,t] + ch_t <= PV_t + dis_t + g_t              energy balance [kWh]
  soc_{t+1} = soc_t + eta_c ch_t - dis_t / eta_d ;  bounds   battery
  g_t <= grid_available_t * g_max * dt
  sum q_z x <= V_max (horizon), per local day <= V_day ;  hours per zone per day <= H_max

  min  sum_{z,t} A_z dt [ Ky_{z,t} s[z,t] + Ky_{z,t} kappa_z s2[z,t] ]
       + lambda_W sum q_z x + lambda_E sum cost_t g_t

where d_z = Ea Q_z dt / (10 A_z) is the net depth applied per slot and kappa_z is the
irreversibility weight (higher for perennials, whose loss lasts for years).

Documented simplifications (returned as `assumptions`):
- ET is not reduced by water stress inside the optimiser (Ks = 1). This over-estimates depletion,
  so it errs toward irrigating.
- TAW/RAW are constant over the horizon (root growth over 1-3 days is negligible).
- Pump energy is proportional to volume at a fixed total head.
- Reported depletion is re-simulated exactly from the chosen plan (with D clipped at 0).

Shadow prices come from the LP relaxation (x continuous). They are approximate marginal values
and are labelled as such.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import timedelta

from ortools.linear_solver import pywraplp

from qatra_ai.contracts import (
    Confidence,
    DataClass,
    EngineEnvelope,
    ModelInfo,
    ValidationStatus,
    inputs_hash,
)
from qatra_ai.energy import pump_energy_kwh
from qatra_ai.optimization.schedule_models import (
    ConstraintReport,
    SchedulePlan,
    ScheduleRequest,
    SchedulingZone,
    SlotAction,
    ZonePlan,
)

ENGINE = "optimization.irrigation_scheduler"
MODEL = ModelInfo(
    model_id="milp_multizone_irrigation",
    version="0.1.0",
    validation_status=ValidationStatus.SIMULATION_TESTED,
    references=["AI_ENGINE_BLUEPRINT.md section 6.1", "FAO-56 water balance", "FAO-33 Ky"],
    evaluation_ref="docs/evaluation/scheduler_closed_loop_2025.md",
)
EPS = 1e-6
_ORDER = [Confidence.INSUFFICIENT_EVIDENCE, Confidence.LOW, Confidence.MEDIUM, Confidence.HIGH]

ASSUMPTIONS = [
    "ET is not reduced by water stress inside the optimiser (Ks = 1): errs toward irrigating.",
    "TAW and RAW are held constant over the planning horizon.",
    "Pump energy is proportional to pumped volume at a fixed total head.",
    "Depletion trajectories are re-simulated from the chosen plan; water above field "
    "capacity is lost to drainage.",
    "Shadow prices come from the LP relaxation and are approximate.",
]


# --- Internal helpers ---------------------------------------------------------------------


@dataclass
class _Consts:
    q: list[float]  # m3 per slot, per zone
    d: list[float]  # net mm per slot, per zone
    e: list[float]  # kWh per slot, per zone
    dsev: list[float]
    w1: list[list[float]]
    w2: list[list[float]]
    day_of_slot: list[int]
    allowed: list[bool]


def _consts(req: ScheduleRequest, weighted: bool) -> _Consts:
    dt, p, pol = req.slot_hours, req.pump, req.policy
    q, d, e, dsev, w1, w2 = [], [], [], [], [], []
    for z in req.zones:
        qz = z.design_flow_m3h * dt
        q.append(qz)
        d.append(z.application_efficiency * qz / (10.0 * z.area_ha))
        e.append(pump_energy_kwh(qz, p.total_head_m, p.pump_efficiency, p.motor_efficiency))
        dsev.append(z.raw_mm + pol.severe_fraction * (z.taw_mm - z.raw_mm))
        kappa = pol.kappa_perennial if z.perennial else pol.kappa_annual
        if weighted:
            w1.append([k if k > 0 else pol.default_ky for k in z.ky])
            w2.append([kappa * (k if k > 0 else pol.default_ky) for k in z.ky])
        else:
            w1.append([1.0] * req.n_slots)
            w2.append([0.0] * req.n_slots)
    start_day = req.start.date()
    days = [
        ((req.start + timedelta(hours=t * dt)).date() - start_day).days for t in range(req.n_slots)
    ]
    allowed = list(req.allowed) if req.allowed is not None else [True] * req.n_slots
    return _Consts(q, d, e, dsev, w1, w2, days, allowed)


@dataclass
class _Solved:
    x: list[list[float]]
    g: list[float]
    ch: list[float]
    dis: list[float]
    soc: list[float]
    objective: float
    status: str
    gap: float | None
    solver_name: str
    duals: dict[str, float]


def _solve(req: ScheduleRequest, *, weighted: bool, relax: bool) -> _Solved | None:
    c = _consts(req, weighted)
    T, Z, dt = req.n_slots, len(req.zones), req.slot_hours
    names = ("GLOP",) if relax else ("SCIP", "CBC")
    solver = None
    for name in names:
        solver = pywraplp.Solver.CreateSolver(name)
        if solver is not None:
            break
    if solver is None:
        raise RuntimeError("no suitable OR-Tools solver available")
    solver_name = name
    inf = solver.infinity()

    x = [
        [
            (solver.NumVar if relax else solver.IntVar)(0, 1 if c.allowed[t] else 0, f"x_{zi}_{t}")
            for t in range(T)
        ]
        for zi in range(Z)
    ]
    D = [[solver.NumVar(0, inf, f"D_{zi}_{t}") for t in range(T + 1)] for zi in range(Z)]
    s = [[solver.NumVar(0, inf, f"s_{zi}_{t}") for t in range(T + 1)] for zi in range(Z)]
    s2 = [[solver.NumVar(0, inf, f"s2_{zi}_{t}") for t in range(T + 1)] for zi in range(Z)]

    for zi, z in enumerate(req.zones):
        D[zi][0].SetBounds(z.initial_depletion_mm, z.initial_depletion_mm)
        for t in range(T):
            solver.Add(D[zi][t + 1] - D[zi][t] + c.d[zi] * x[zi][t] >= z.etc_mm[t] - z.peff_mm[t])
            solver.Add(s[zi][t + 1] - D[zi][t + 1] >= -z.raw_mm)
            solver.Add(s2[zi][t + 1] - D[zi][t + 1] >= -c.dsev[zi])

    pump_flow, energy_bal = [], []
    for t in range(T):
        pump_flow.append(
            solver.Add(
                sum(z.design_flow_m3h * x[zi][t] for zi, z in enumerate(req.zones))
                <= req.pump.max_flow_m3h
            )
        )
        solver.Add(sum(x[zi][t] for zi in range(Z)) <= req.pump.max_simultaneous_zones)

    en = req.energy
    g = [
        solver.NumVar(0, en.grid_max_kw * dt if en.grid_available[t] else 0.0, f"g_{t}")
        for t in range(T)
    ]
    b = en.battery
    if b is not None:
        ch = [solver.NumVar(0, b.max_charge_kw * dt, f"ch_{t}") for t in range(T)]
        dis = [solver.NumVar(0, b.max_discharge_kw * dt, f"dis_{t}") for t in range(T)]
        soc = [solver.NumVar(b.soc_min_kwh, b.soc_max_kwh, f"soc_{t}") for t in range(T + 1)]
        soc[0].SetBounds(b.soc_initial_kwh, b.soc_initial_kwh)
        for t in range(T):
            solver.Add(
                soc[t + 1]
                == soc[t] + b.charge_efficiency * ch[t] - dis[t] * (1.0 / b.discharge_efficiency)
            )
    else:
        ch = [solver.NumVar(0, 0, f"ch_{t}") for t in range(T)]
        dis = [solver.NumVar(0, 0, f"dis_{t}") for t in range(T)]
        soc = [solver.NumVar(0, 0, f"soc_{t}") for t in range(T + 1)]
    for t in range(T):
        load = sum(c.e[zi] * x[zi][t] for zi in range(Z))
        energy_bal.append(solver.Add(load + ch[t] - dis[t] - g[t] <= en.pv_kwh[t]))

    water_total = None
    if req.water.max_volume_m3 is not None:
        water_total = solver.Add(
            sum(c.q[zi] * x[zi][t] for zi in range(Z) for t in range(T)) <= req.water.max_volume_m3
        )
    water_day = []
    if req.water.max_volume_per_day_m3 is not None:
        for day in sorted(set(c.day_of_slot)):
            slots = [t for t in range(T) if c.day_of_slot[t] == day]
            water_day.append(
                solver.Add(
                    sum(c.q[zi] * x[zi][t] for zi in range(Z) for t in slots)
                    <= req.water.max_volume_per_day_m3
                )
            )
    for zi, z in enumerate(req.zones):
        if z.max_hours_per_day is not None:
            for day in sorted(set(c.day_of_slot)):
                slots = [t for t in range(T) if c.day_of_slot[t] == day]
                solver.Add(sum(x[zi][t] * dt for t in slots) <= z.max_hours_per_day)

    pol = req.policy
    cost = en.grid_cost_per_kwh or [1.0] * T
    obj = solver.Objective()
    for zi, z in enumerate(req.zones):
        for t in range(1, T + 1):
            obj.SetCoefficient(s[zi][t], z.area_ha * dt * c.w1[zi][t - 1])
            obj.SetCoefficient(s2[zi][t], z.area_ha * dt * c.w2[zi][t - 1])
        for t in range(T):
            obj.SetCoefficient(x[zi][t], pol.lambda_water_per_m3 * c.q[zi])
    for t in range(T):
        obj.SetCoefficient(g[t], pol.lambda_energy * cost[t])
    obj.SetMinimization()

    if relax:
        status = solver.Solve()
    else:
        solver.SetTimeLimit(int(req.time_limit_s * 1000))
        params = pywraplp.MPSolverParameters()
        params.SetDoubleParam(params.RELATIVE_MIP_GAP, req.mip_relative_gap)
        status = solver.Solve(params)

    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        return None

    objective = solver.Objective().Value()
    gap = None
    if not relax:
        bound = solver.Objective().BestBound()
        gap = abs(objective - bound) / max(abs(objective), 1e-9)

    duals: dict[str, float] = {}
    if relax:
        # OR-Tools returns d(objective)/d(rhs). For <= constraints in a minimisation it is <= 0;
        # we report the *reduction* in weighted stress per unit of extra capacity.
        if water_total is not None:
            duals["water_volume_cap"] = -water_total.dual_value()
        duals["pump_flow"] = -sum(cn.dual_value() for cn in pump_flow)
        duals["energy"] = -sum(cn.dual_value() for cn in energy_bal)
        if water_day:
            duals["water_daily_cap"] = -sum(cn.dual_value() for cn in water_day)
        duals = {k: (0.0 if abs(v) < 1e-9 else v) for k, v in duals.items()}

    return _Solved(
        x=[[x[zi][t].solution_value() for t in range(T)] for zi in range(Z)],
        g=[v.solution_value() for v in g],
        ch=[v.solution_value() for v in ch],
        dis=[v.solution_value() for v in dis],
        soc=[v.solution_value() for v in soc],
        objective=objective,
        status="optimal" if status == pywraplp.Solver.OPTIMAL else "feasible",
        gap=gap,
        solver_name=solver_name,
        duals=duals,
    )


def simulate_zone(zone: SchedulingZone, x: list[float], net_depth_per_slot: float) -> list[float]:
    """Exact depletion trajectory (length T+1) for a given on/off plan, D clipped at 0."""
    d = zone.initial_depletion_mm
    traj = [d]
    for t, on in enumerate(x):
        d = max(0.0, d + zone.etc_mm[t] - zone.peff_mm[t] - net_depth_per_slot * on)
        traj.append(d)
    return traj


def verify_plan(req: ScheduleRequest, sol: _Solved) -> list[str]:
    """Independent check of every hard constraint on the returned plan (safety veto input)."""
    c = _consts(req, True)
    T, dt, tol = req.n_slots, req.slot_hours, 1e-5
    v: list[str] = []
    for zi, z in enumerate(req.zones):
        for t in range(T):
            raw = sol.x[zi][t]
            xv = round(raw)
            if abs(raw - xv) > 1e-6 or xv not in (0, 1):
                v.append(f"{z.zone_id} slot {t}: non-binary decision {raw}")
            if xv and not c.allowed[t]:
                v.append(f"{z.zone_id} slot {t}: irrigates outside the operating window")
    for t in range(T):
        flow = sum(z.design_flow_m3h * sol.x[zi][t] for zi, z in enumerate(req.zones))
        if flow > req.pump.max_flow_m3h + tol:
            v.append(f"slot {t}: flow {flow:.2f} > pump max {req.pump.max_flow_m3h}")
        if sum(sol.x[zi][t] for zi in range(len(req.zones))) > req.pump.max_simultaneous_zones:
            v.append(f"slot {t}: too many simultaneous zones")
        load = sum(c.e[zi] * sol.x[zi][t] for zi in range(len(req.zones)))
        supply = req.energy.pv_kwh[t] + sol.dis[t] + sol.g[t] - sol.ch[t]
        if load > supply + tol:
            v.append(f"slot {t}: energy demand {load:.3f} kWh > supply {supply:.3f} kWh")
        if sol.g[t] > tol and not req.energy.grid_available[t]:
            v.append(f"slot {t}: grid used while unavailable")
    vol = sum(c.q[zi] * sol.x[zi][t] for zi in range(len(req.zones)) for t in range(T))
    if req.water.max_volume_m3 is not None and vol > req.water.max_volume_m3 + tol:
        v.append(f"total volume {vol:.1f} m3 > cap {req.water.max_volume_m3}")
    b = req.energy.battery
    if b is not None:
        for t, sv in enumerate(sol.soc):
            if sv < b.soc_min_kwh - tol or sv > b.soc_max_kwh + tol:
                v.append(f"battery SOC out of bounds at step {t}: {sv:.3f}")
    for day in sorted(set(c.day_of_slot)):
        slots = [t for t in range(T) if c.day_of_slot[t] == day]
        if req.water.max_volume_per_day_m3 is not None:
            dv = sum(c.q[zi] * sol.x[zi][t] for zi in range(len(req.zones)) for t in slots)
            if dv > req.water.max_volume_per_day_m3 + tol:
                v.append(f"day {day}: volume {dv:.1f} > daily cap")
        for zi, z in enumerate(req.zones):
            if z.max_hours_per_day is not None:
                hrs = sum(sol.x[zi][t] * dt for t in slots)
                if hrs > z.max_hours_per_day + tol:
                    v.append(f"{z.zone_id} day {day}: {hrs} h > {z.max_hours_per_day} h")
    return v


def _energy_headroom(req: ScheduleRequest, sol: _Solved, c: _Consts, t: int) -> float:
    """Extra kWh that could be supplied in slot t without changing other slots (approximate:
    battery headroom ignores effects on later state of charge)."""
    dt, b = req.slot_hours, req.energy.battery
    load = sum(c.e[j] * round(sol.x[j][t]) for j in range(len(req.zones)))
    # Curtailed PV plus energy currently sent to the battery (charging could be stopped)
    headroom = req.energy.pv_kwh[t] + sol.dis[t] + sol.g[t] - load
    if req.energy.grid_available[t]:
        headroom += req.energy.grid_max_kw * dt - sol.g[t]
    if b is not None:
        headroom += min(
            b.max_discharge_kw * dt - sol.dis[t],
            max(0.0, sol.soc[t] - b.soc_min_kwh) * b.discharge_efficiency,
        )
    return headroom


def _zone_reasons(
    req: ScheduleRequest, sol: _Solved, c: _Consts, zi: int, traj: list[float], base: list[float]
) -> tuple[list[str], list[str]]:
    z = req.zones[zi]
    T, dt = req.n_slots, req.slot_hours
    stressed = [t for t in range(1, T + 1) if traj[t] > z.raw_mm + EPS]
    stressed_base = [t for t in range(1, T + 1) if base[t] > z.raw_mm + EPS]
    vol = sum(c.q[zi] * sol.x[zi][t] for t in range(T))
    if not stressed_base and vol < EPS:
        return ["NO_STRESS_EXPECTED_IN_HORIZON"], []
    if not stressed:
        return ["IRRIGATED_TO_PREVENT_STRESS"], []

    reasons: list[str] = ["IRRIGATED_STRESS_REDUCED"] if vol > EPS else []
    details: list[str] = []
    last = stressed[-1]
    candidates = [t for t in range(last) if c.allowed[t] and sol.x[zi][t] < 0.5]
    if not candidates:
        reasons.append("OPERATING_WINDOW_OR_FLOW_LIMIT")
        details.append("zone already irrigated in every allowed slot before its last stress slot")
        return reasons, details

    counts = {"pump": 0, "energy": 0, "water": 0, "water_day": 0, "hours": 0, "free": 0}
    total_vol = sum(c.q[j] * sol.x[j][t] for j in range(len(req.zones)) for t in range(T))
    for t in candidates:
        blocked = False
        flow = sum(req.zones[j].design_flow_m3h * sol.x[j][t] for j in range(len(req.zones)))
        n_on = sum(sol.x[j][t] for j in range(len(req.zones)))
        if (
            flow + z.design_flow_m3h > req.pump.max_flow_m3h + EPS
            or n_on + 1 > req.pump.max_simultaneous_zones
        ):
            counts["pump"] += 1
            blocked = True
        if c.e[zi] > _energy_headroom(req, sol, c, t) + EPS:
            counts["energy"] += 1
            blocked = True
        if (
            req.water.max_volume_m3 is not None
            and total_vol + c.q[zi] > req.water.max_volume_m3 + EPS
        ):
            counts["water"] += 1
            blocked = True
        if req.water.max_volume_per_day_m3 is not None:
            day_slots = [u for u in range(T) if c.day_of_slot[u] == c.day_of_slot[t]]
            day_vol = sum(c.q[j] * sol.x[j][u] for j in range(len(req.zones)) for u in day_slots)
            if day_vol + c.q[zi] > req.water.max_volume_per_day_m3 + EPS:
                counts["water_day"] += 1
                blocked = True
        if z.max_hours_per_day is not None:
            day_slots = [u for u in range(T) if c.day_of_slot[u] == c.day_of_slot[t]]
            if sum(sol.x[zi][u] * dt for u in day_slots) + dt > z.max_hours_per_day + EPS:
                counts["hours"] += 1
                blocked = True
        if not blocked:
            counts["free"] += 1

    mapping = [
        ("pump", "PUMP_CAPACITY_SHARED"),
        ("energy", "ENERGY_LIMITED"),
        ("water", "WATER_VOLUME_CAP"),
        ("water_day", "WATER_VOLUME_CAP"),
        ("hours", "DAILY_HOURS_LIMIT"),
        ("free", "PRIORITY_TRADE_OFF"),
    ]
    for key, code in mapping:
        if counts[key]:
            if code not in reasons:
                reasons.append(code)
            label = (
                f"{code} ({'daily cap' if key == 'water_day' else 'horizon cap'})"
                if (key in ("water", "water_day"))
                else code
            )
            details.append(f"{label}: {counts[key]} of {len(candidates)} unused allowed slots")
    return reasons, details


def _build_plan(req: ScheduleRequest, sol: _Solved, solve_time: float) -> SchedulePlan:
    c = _consts(req, True)
    T, dt = req.n_slots, req.slot_hours
    actions: list[SlotAction] = []
    zones: list[ZonePlan] = []
    pol = req.policy
    for zi, z in enumerate(req.zones):
        xs = [round(v) for v in sol.x[zi]]
        for t in range(T):
            if xs[t]:
                start = req.start + timedelta(hours=t * dt)
                actions.append(
                    SlotAction(
                        zone_id=z.zone_id,
                        slot=t,
                        start=start,
                        end=start + timedelta(hours=dt),
                        volume_m3=round(c.q[zi], 3),
                        net_depth_mm=round(c.d[zi], 3),
                    )
                )
        traj = simulate_zone(z, xs, c.d[zi])
        base = simulate_zone(z, [0] * T, c.d[zi])

        def stress(tr: list[float], zz: SchedulingZone = z) -> float:
            return sum(max(0.0, d - zz.raw_mm) for d in tr[1:]) * dt

        reasons, details = _zone_reasons(req, sol, c, zi, traj, base)
        kappa = pol.kappa_perennial if z.perennial else pol.kappa_annual
        ky_txt = f"Ky {min(z.ky):.2f}-{max(z.ky):.2f}" + (" (assumed)" if z.ky_assumed else "")
        zones.append(
            ZonePlan(
                zone_id=z.zone_id,
                volume_m3=round(sum(xs) * c.q[zi], 3),
                irrigation_hours=sum(xs) * dt,
                net_depth_mm=round(sum(xs) * c.d[zi], 3),
                depletion_start_mm=round(traj[0], 3),
                depletion_end_mm=round(traj[-1], 3),
                max_depletion_mm=round(max(traj), 3),
                raw_mm=z.raw_mm,
                taw_mm=z.taw_mm,
                stress_mm_h=round(stress(traj), 3),
                stress_mm_h_without_irrigation=round(stress(base), 3),
                severe_stress_slots=sum(d > c.dsev[zi] + EPS for d in traj[1:]),
                severe_stress_slots_without_irrigation=sum(d > c.dsev[zi] + EPS for d in base[1:]),
                perennial=z.perennial,
                weight_summary=f"{ky_txt}; severe-stress multiplier {kappa:g}; area {z.area_ha} ha",
                reasons=reasons,  # type: ignore[arg-type]
                reason_details=details,
            )
        )

    load = [sum(c.e[zi] * round(sol.x[zi][t]) for zi in range(len(req.zones))) for t in range(T)]
    pv_used = [
        max(0.0, min(req.energy.pv_kwh[t], load[t] + sol.ch[t] - sol.dis[t] - sol.g[t]))
        for t in range(T)
    ]
    cost = req.energy.grid_cost_per_kwh or [0.0] * T
    totals = {
        "water_m3": round(sum(zp.volume_m3 for zp in zones), 3),
        "pump_energy_kwh": round(sum(load), 3),
        "pv_available_kwh": round(sum(req.energy.pv_kwh), 3),
        "pv_used_kwh": round(sum(pv_used), 3),
        "grid_kwh": round(sum(sol.g), 3),
        "grid_cost": round(sum(gc * g for gc, g in zip(cost, sol.g, strict=True)), 3),
        "battery_charge_kwh": round(sum(sol.ch), 3),
        "battery_discharge_kwh": round(sum(sol.dis), 3),
    }

    # Constraint usage and approximate shadow prices (LP relaxation)
    relaxed = _solve(req, weighted=True, relax=True)
    duals = relaxed.duals if relaxed else {}
    pump_binding = sum(
        1
        for t in range(T)
        if sum(z.design_flow_m3h * round(sol.x[zi][t]) for zi, z in enumerate(req.zones))
        > req.pump.max_flow_m3h - min(z.design_flow_m3h for z in req.zones) + EPS
    )
    unit = "weighted stress (mm·h·ha·Ky) avoided"
    constraints = [
        ConstraintReport(
            name="pump_flow",
            binding_slots=pump_binding,
            shadow_price=duals.get("pump_flow"),
            shadow_price_meaning=f"{unit} per +1 m3/h pump capacity in every slot (LP approx.)",
        ),
        ConstraintReport(
            name="energy",
            binding_slots=sum(
                1 for t in range(T) if _energy_headroom(req, sol, c, t) < min(c.e) - EPS
            ),
            shadow_price=duals.get("energy"),
            shadow_price_meaning=(
                f"{unit} per +1 kWh available in every slot (LP approx.; includes the small "
                "grid-cost tie-breaker lambda_energy)"
            ),
        ),
    ]
    if req.water.max_volume_m3 is not None:
        constraints.append(
            ConstraintReport(
                name="water_volume_cap",
                binding_slots=int(totals["water_m3"] >= req.water.max_volume_m3 - min(c.q) + EPS),
                shadow_price=duals.get("water_volume_cap"),
                shadow_price_meaning=f"{unit} per +1 m3 of allowed volume (LP approx.)",
            )
        )

    if req.water.max_volume_per_day_m3 is not None:
        cap_day = req.water.max_volume_per_day_m3
        binding_days = 0
        for day in sorted(set(c.day_of_slot)):
            slots = [t for t in range(T) if c.day_of_slot[t] == day]
            vol = sum(c.q[zi] * round(sol.x[zi][t]) for zi in range(len(req.zones)) for t in slots)
            binding_days += int(vol > cap_day - min(c.q) + EPS)
        constraints.append(
            ConstraintReport(
                name="water_daily_cap",
                binding_slots=binding_days,
                shadow_price=duals.get("water_daily_cap"),
                shadow_price_meaning=(
                    f"{unit} per +1 m3 on every day's cap (LP approx.); "
                    "binding_slots counts DAYS for this constraint"
                ),
            )
        )

    unweighted = _solve(req, weighted=False, relax=False)
    comparison = None
    if unweighted is not None:
        comparison = {
            z.zone_id: round(sum(round(v) for v in unweighted.x[zi]) * c.q[zi], 3)
            for zi, z in enumerate(req.zones)
        }

    return SchedulePlan(
        status=sol.status,  # type: ignore[arg-type]
        objective=round(sol.objective, 6),
        mip_gap=sol.gap,
        solve_time_s=round(solve_time, 3),
        solver=sol.solver_name,
        actions=sorted(actions, key=lambda a: (a.slot, a.zone_id)),
        zones=zones,
        totals=totals,
        constraints=constraints,
        unweighted_comparison=comparison,
        policy=req.policy,
        assumptions=list(ASSUMPTIONS),
        verification_violations=verify_plan(req, sol),
    )


# --- Public API -----------------------------------------------------------------------------


def plan_irrigation(
    req: ScheduleRequest,
    *,
    input_confidence: Confidence = Confidence.MEDIUM,
    input_reasons: list[str] | None = None,
    request_id: str | None = None,
) -> EngineEnvelope[SchedulePlan]:
    """Optimise the schedule and return it in an EngineEnvelope.

    `input_confidence` comes from the upstream agronomic assessment (the optimiser cannot
    be more certain than its inputs).
    """
    request_id = request_id or str(uuid.uuid4())
    common = dict(
        request_id=request_id,
        engine=ENGINE,
        model=MODEL,
        inputs_hash=inputs_hash(req.model_dump(mode="json")),
    )
    t0 = time.perf_counter()
    sol = _solve(req, weighted=True, relax=False)
    elapsed = time.perf_counter() - t0
    if sol is None:
        return EngineEnvelope[SchedulePlan](
            **common,
            confidence=Confidence.INSUFFICIENT_EVIDENCE,
            confidence_reasons=["solver found no feasible schedule within the time limit"],
            limitations=list(ASSUMPTIONS),
        )

    plan = _build_plan(req, sol, elapsed)
    conf = input_confidence
    reasons = list(input_reasons or [])

    def cap(level: Confidence, why: str) -> None:
        nonlocal conf
        conf = min(conf, level, key=_ORDER.index)
        reasons.append(why)

    if plan.verification_violations:
        return EngineEnvelope[SchedulePlan](
            **common,
            confidence=Confidence.INSUFFICIENT_EVIDENCE,
            confidence_reasons=["plan failed independent constraint verification; not released"],
            limitations=plan.verification_violations,
        )
    if sol.status != "optimal":
        cap(Confidence.MEDIUM, f"time limit reached; optimality gap {sol.gap:.2%}")
    if any(z.ky_assumed for z in req.zones):
        cap(Confidence.MEDIUM, "Ky missing for at least one crop; default weight used")
    if req.energy.pv_data_class in (DataClass.PROJECTED, DataClass.SIMULATED):
        reasons.append(f"plan relies on {req.energy.pv_data_class.value} PV energy")

    provenance = {req.energy.pv_data_class: req.n_slots}
    return EngineEnvelope[SchedulePlan](
        **common,
        confidence=conf,
        confidence_reasons=reasons,
        limitations=list(ASSUMPTIONS),
        provenance_summary=provenance,
        payload=plan,
    )


def solve_schedule(req: ScheduleRequest) -> tuple[list[list[int]], str] | None:
    """Fast path for simulation loops: optimal on/off matrix [zone][slot] without the
    explanation/comparison solves. The plan is still verified; violations raise."""
    sol = _solve(req, weighted=True, relax=False)
    if sol is None:
        return None
    violations = verify_plan(req, sol)
    if violations:
        raise RuntimeError(f"scheduler produced an invalid plan: {violations[:3]}")
    return [[round(v) for v in row] for row in sol.x], sol.status
