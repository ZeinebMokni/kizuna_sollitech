"""Closed-loop (rolling-horizon) benchmark of irrigation policies.

Each simulated day:
  1. a POLICY looks at the current soil-water state and a forecast, and requests irrigation
     hours per zone for the next 24 h;
  2. a shared EXECUTOR applies the requests hour by hour under the farm's physical limits
     (pump, well caps, PV/battery/grid). Anything infeasible is dropped and logged as
     unserved, so no policy can use resources the farm does not have;
  3. a TRUTH model advances the hourly root-zone balance WITH stress feedback
     (ETa = Ks * ETc), and stores daily ETc/ETa for FAO-33 yield response.

IMPORTANT LIMITATION: the truth model uses the same FAO-56 structure as the planner. Results
measure the quality of decisions *given this model*, not field performance. Two robustness
knobs reduce (but do not remove) this optimism:
  - truth_et_factor: the truth's ET is scaled relative to what planners assume;
  - forecast_mode: "perfect" (true future weather) or "persistence" (yesterday repeated).
All policies receive the same perfect knowledge of the current soil-water state, which
corresponds to well-calibrated sensors. That is optimistic for every policy alike.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Literal

import pandas as pd

from qatra_ai.agronomy.kc import (
    adjusted_depletion_fraction,
    kc_for_day,
    root_depth_for_day,
    stage_for_day,
)
from qatra_ai.agronomy.water_balance import LIGHT_RAIN_FACTOR, ZoneSetup
from qatra_ai.agronomy.yield_response import relative_yield_stagewise
from qatra_ai.energy import pump_energy_kwh
from qatra_ai.optimization.inputs import DAYTIME, pv_slots_from_daily_radiation
from qatra_ai.optimization.irrigation_scheduler import solve_schedule
from qatra_ai.optimization.schedule_models import (
    BatterySpec,
    EnergySupply,
    PriorityPolicy,
    PumpSystem,
    ScheduleRequest,
    SchedulingZone,
    WaterSource,
)

ForecastMode = Literal["perfect", "persistence"]
# Positive (so the scheduler does not substitute its default Ky) but negligible.
SEASON_OVER_WEIGHT = 1e-6


# --- Configuration --------------------------------------------------------------------------


@dataclass(frozen=True)
class BenchZone:
    zone_id: str
    setup: ZoneSetup
    design_flow_m3h: float


@dataclass(frozen=True)
class FarmConfig:
    zones: list[BenchZone]
    pump: PumpSystem
    pv_rated_kw: float = 0.0
    pv_system_efficiency: float = 0.86
    battery: BatterySpec | None = None
    grid_hours: frozenset[int] = frozenset()  # local hours with grid power
    grid_max_kw: float = 0.0
    max_volume_per_day_m3: float | None = None


# --- Zone physics helpers ---------------------------------------------------------------------


def _season_day(setup: ZoneSetup, d: date) -> int | None:
    sd = (d - setup.season_start).days
    if setup.crop.perennial:
        return sd % 365
    return sd if 0 <= sd < setup.crop.season_length_days else None


@dataclass
class _DayParams:
    stage: str
    etc_day: float
    taw: float
    raw: float
    peff_day: float


def _day_params(setup: ZoneSetup, d: date, et0: float, precip: float) -> _DayParams | None:
    sd = _season_day(setup, d)
    if sd is None:
        return None
    crop = setup.crop
    kc = kc_for_day(crop, sd)
    stage = stage_for_day(crop, sd)
    assert kc is not None and stage is not None
    etc = kc * et0
    taw = setup.soil.taw_mm(root_depth_for_day(crop, sd, setup.soil.soil_depth_m))
    raw = adjusted_depletion_fraction(crop.depletion_fraction_p, etc) * taw
    peff = 0.0 if precip < LIGHT_RAIN_FACTOR * et0 else precip
    return _DayParams(stage, etc, taw, raw, peff)


def _net_depth(z: BenchZone) -> float:
    return z.setup.application_efficiency * z.design_flow_m3h / (10.0 * z.setup.area_ha)


# --- Policies ----------------------------------------------------------------------------------


@dataclass
class PolicyContext:
    day: date
    depletion: dict[str, float]  # mm at 00:00, active zones only
    weather: pd.DataFrame  # full daily table (policies must only look ahead via `forecast`)
    forecast: pd.DataFrame  # next 3 days as the policy believes them
    soc_kwh: float | None
    farm: FarmConfig
    max_volume_today_m3: float | None


Requests = list[list[str]]  # per local hour 0..23: zone ids requested, in priority order
Policy = Callable[[PolicyContext], Requests]


def fixed_calendar(
    interval_days: int, hours_per_zone: float | dict[str, float], start_hour: int = 7
) -> Policy:
    """Each zone in turn, a fixed number of hours every `interval_days` days, from start_hour.
    `hours_per_zone` may be one value for all zones or a per-zone mapping."""

    def hours_for(zid: str) -> float:
        if isinstance(hours_per_zone, dict):
            return hours_per_zone.get(zid, 0.0)
        return hours_per_zone

    def policy(ctx: PolicyContext) -> Requests:
        req: Requests = [[] for _ in range(24)]
        if (ctx.day.toordinal() % interval_days) != 0:
            return req
        flows = {z.zone_id: z.design_flow_m3h for z in ctx.farm.zones}
        zones = list(ctx.depletion)
        hours = {zid: hours_for(zid) for zid in zones}
        # A careful farmer fits the event inside the well's daily cap, scaling all zones alike.
        vol = sum(hours[zid] * flows[zid] for zid in zones)
        cap = ctx.max_volume_today_m3
        if cap is not None and vol > cap:
            hours = {zid: math.floor(h * cap / vol) for zid, h in hours.items()}
        # Rotate the starting zone each event so no zone is always served last.
        event = ctx.day.toordinal() // interval_days
        k = event % len(zones) if zones else 0
        h = start_hour
        for zid in zones[k:] + zones[:k]:
            for _ in range(math.ceil(hours[zid])):
                if h < 24:
                    req[h].append(zid)
                h += 1
        return req

    label = "per-zone" if isinstance(hours_per_zone, dict) else f"{hours_per_zone:g}h"
    policy.__name__ = f"fixed_calendar_{interval_days}d_{label}"
    return policy


def size_calendar_hours(
    farm: FarmConfig, weather: pd.DataFrame, interval_days: int
) -> dict[str, float]:
    """Hours per irrigation event so that each zone's *season-average* gross requirement is met
    (climatology from the supplied weather; what a careful fixed schedule would use)."""
    out = {}
    for z in farm.zones:
        etc = []
        for ts, row in weather.iterrows():
            pr = _day_params(z.setup, ts.date(), float(row["et0"]), float(row["precip"]))
            if pr is not None:
                etc.append(max(0.0, pr.etc_day - pr.peff_day))
        mean_net = sum(etc) / len(etc) if etc else 0.0
        out[z.zone_id] = round(mean_net * interval_days / _net_depth(z), 1)
    return out


def threshold_rule(start_hour: int = 7) -> Policy:
    """'Irrigate when dry': at 00:00, every zone with Dr >= RAW is refilled to field capacity,
    driest zone first (relative to its RAW..TAW band)."""

    def policy(ctx: PolicyContext) -> Requests:
        req: Requests = [[] for _ in range(24)]
        h = start_hour
        by_id = {z.zone_id: z for z in ctx.farm.zones}
        row = ctx.forecast.iloc[0]
        due = []
        for zid, dr in ctx.depletion.items():
            z = by_id[zid]
            p = _day_params(z.setup, ctx.day, float(row["et0"]), float(row["precip"]))
            if p is None or dr < p.raw:
                continue
            due.append(((dr - p.raw) / max(p.taw - p.raw, 1e-9), zid, dr))
        # Driest zone (relative to its own RAW..TAW band) first.
        for _, zid, dr in sorted(due, reverse=True):
            z = by_id[zid]
            hours = math.ceil(dr / _net_depth(z))
            for _ in range(hours):
                if h < 24:
                    req[h].append(zid)
                h += 1
        return req

    policy.__name__ = "threshold_rule"
    return policy


def optimizer_policy(
    horizon_h: int = 72,
    conservative_pv: float = 0.8,
    policy_weights: PriorityPolicy | None = None,
    mip_relative_gap: float = 1e-4,
    time_limit_s: float = 20.0,
) -> Policy:
    def policy(ctx: PolicyContext) -> Requests:
        req: Requests = [[] for _ in range(24)]
        start = datetime.combine(ctx.day, datetime.min.time())
        fc = ctx.forecast
        days = [ctx.day + timedelta(days=i) for i in range(math.ceil(horizon_h / 24))]
        zones: list[SchedulingZone] = []
        for z in ctx.farm.zones:
            if z.zone_id not in ctx.depletion:
                continue
            etc, peff, ky = [], [], []
            taw = raw = None
            ky_assumed = False
            for i in range(horizon_h):
                d = days[i // 24]
                row = fc.loc[pd.Timestamp(d)]
                p = _day_params(z.setup, d, float(row["et0"]), float(row["precip"]))
                if p is None:  # season over within the horizon: no demand, ~no stress weight
                    etc.append(0.0)
                    peff.append(0.0)
                    ky.append(SEASON_OVER_WEIGHT)
                    continue
                if taw is None:
                    taw, raw = p.taw, p.raw
                etc.append(p.etc_day * DAYTIME[i % 24])
                peff.append(p.peff_day / 24.0)
                k = getattr(z.setup.crop.ky_stage, p.stage) or z.setup.crop.ky_total
                if k is None:
                    ky_assumed, k = True, 0.0
                ky.append(k)
            assert taw is not None and raw is not None
            zones.append(
                SchedulingZone(
                    zone_id=z.zone_id,
                    area_ha=z.setup.area_ha,
                    design_flow_m3h=z.design_flow_m3h,
                    application_efficiency=z.setup.application_efficiency,
                    initial_depletion_mm=min(ctx.depletion[z.zone_id], taw),
                    taw_mm=taw,
                    raw_mm=raw,
                    etc_mm=etc,
                    peff_mm=peff,
                    ky=ky,
                    ky_assumed=ky_assumed,
                    perennial=z.setup.crop.perennial,
                )
            )
        if not zones:
            return req
        farm = ctx.farm
        b = farm.battery
        battery = None
        if b is not None and ctx.soc_kwh is not None:
            battery = b.model_copy(update={"soc_initial_kwh": ctx.soc_kwh})
        rs = fc["rs"] if "rs" in fc else pd.Series(0.0, index=fc.index)
        pv = (
            pv_slots_from_daily_radiation(
                rs,
                start=start,
                n_slots=horizon_h,
                p_rated_kw=farm.pv_rated_kw,
                system_efficiency=farm.pv_system_efficiency,
                conservative_factor=conservative_pv,
            )
            if farm.pv_rated_kw > 0
            else [0.0] * horizon_h
        )
        cap_day = ctx.max_volume_today_m3
        sreq = ScheduleRequest(
            start=start,
            n_slots=horizon_h,
            zones=zones,
            pump=farm.pump,
            water=WaterSource(max_volume_per_day_m3=cap_day),
            energy=EnergySupply(
                pv_kwh=pv,
                grid_available=[(t % 24) in farm.grid_hours for t in range(horizon_h)],
                grid_max_kw=farm.grid_max_kw,
                battery=battery,
            ),
            policy=policy_weights or PriorityPolicy(),
            time_limit_s=time_limit_s,
            mip_relative_gap=mip_relative_gap,
        )
        result = solve_schedule(sreq)
        if result is None:
            return req
        x, _ = result
        for zi, z in enumerate(zones):
            for t in range(24):
                if x[zi][t]:
                    req[t].append(z.zone_id)
        return req

    policy.__name__ = "optimizer"
    return policy


# --- Executor + truth ---------------------------------------------------------------------------


@dataclass
class ZoneDayLog:
    date: date
    zone_id: str
    stage: str
    etc_mm: float
    eta_mm: float
    irrigation_m3: float
    stress_mm_h: float
    severe_h: int
    min_ks: float
    dr_end_mm: float


@dataclass
class BenchmarkRun:
    policy: str
    zone_days: list[ZoneDayLog] = field(default_factory=list)
    energy_kwh: float = 0.0
    grid_kwh: float = 0.0
    unserved_zone_hours: int = 0
    unserved_by_cause: dict[str, int] = field(default_factory=dict)


def _forecast(weather: pd.DataFrame, day: date, mode: ForecastMode, n_days: int) -> pd.DataFrame:
    idx = [pd.Timestamp(day + timedelta(days=i)) for i in range(n_days)]
    if mode == "perfect":
        return weather.loc[idx]
    yesterday = weather.loc[pd.Timestamp(day - timedelta(days=1))]
    return pd.DataFrame([yesterday.to_dict()] * n_days, index=idx)


def run_policy(
    policy: Policy,
    farm: FarmConfig,
    weather: pd.DataFrame,
    start: date,
    end: date,
    *,
    forecast_mode: ForecastMode = "perfect",
    truth_et_factor: float = 1.0,
    severe_fraction: float = 0.5,
    max_volume_per_day_m3: float | None = None,
) -> BenchmarkRun:
    """Simulate [start, end] inclusive. `weather` needs et0, precip, rs (daily) and must cover
    one day before start (persistence) and 3 days after end (forecast horizon)."""
    cap_day = (
        max_volume_per_day_m3 if max_volume_per_day_m3 is not None else farm.max_volume_per_day_m3
    )
    run = BenchmarkRun(policy=getattr(policy, "__name__", "policy"))
    dep: dict[str, float] = {}
    soc = farm.battery.soc_initial_kwh if farm.battery else None
    b = farm.battery
    p = farm.pump
    q = {z.zone_id: z.design_flow_m3h for z in farm.zones}  # m3 per 1 h slot
    e = {
        zid: pump_energy_kwh(v, p.total_head_m, p.pump_efficiency, p.motor_efficiency)
        for zid, v in q.items()
    }
    by_id = {z.zone_id: z for z in farm.zones}

    day = start
    while day <= end:
        row = weather.loc[pd.Timestamp(day)]
        et0, precip = float(row["et0"]), float(row["precip"])
        params = {}
        for z in farm.zones:
            pr = _day_params(z.setup, day, et0 * truth_et_factor, precip)
            if pr is None:
                dep.pop(z.zone_id, None)
                continue
            params[z.zone_id] = pr
            dep.setdefault(
                z.zone_id,
                0.0 if z.setup.initial_depletion_mm is None else z.setup.initial_depletion_mm,
            )
            dep[z.zone_id] = min(dep[z.zone_id], pr.taw)

        ctx = PolicyContext(
            day=day,
            depletion=dict(dep),
            weather=weather,
            forecast=_forecast(weather, day, forecast_mode, 3),
            soc_kwh=soc,
            farm=farm,
            max_volume_today_m3=cap_day,
        )
        requests = policy(ctx)

        pv_day = (
            pv_slots_from_daily_radiation(
                pd.Series([float(row.get("rs", 0.0))], index=[pd.Timestamp(day)]),
                start=datetime.combine(day, datetime.min.time()),
                n_slots=24,
                p_rated_kw=farm.pv_rated_kw,
                system_efficiency=farm.pv_system_efficiency,
                conservative_factor=1.0,
            )
            if farm.pv_rated_kw > 0
            else [0.0] * 24
        )

        logs = {
            zid: ZoneDayLog(day, zid, pr.stage, 0, 0, 0, 0, 0, 1.0, 0) for zid, pr in params.items()
        }
        vol_today = 0.0
        for h in range(24):
            # --- Executor: serve requests in priority order under physical limits -----------
            served: list[str] = []
            flow = 0.0
            grid_room = farm.grid_max_kw if h in farm.grid_hours else 0.0
            batt_room = 0.0
            if b is not None and soc is not None:
                batt_room = min(
                    b.max_discharge_kw, max(0.0, soc - b.soc_min_kwh) * b.discharge_efficiency
                )
            energy_avail = pv_day[h] + grid_room + batt_room
            load = 0.0
            for zid in dict.fromkeys(requests[h]):  # dedupe, keep order
                if zid not in params:
                    continue
                cause = None
                if flow + q[zid] > p.max_flow_m3h + 1e-9 or len(served) >= p.max_simultaneous_zones:
                    cause = "pump"
                elif cap_day is not None and vol_today + q[zid] > cap_day + 1e-9:
                    cause = "water_cap"
                elif load + e[zid] > energy_avail + 1e-9:
                    cause = "energy"
                if cause:
                    run.unserved_zone_hours += 1
                    run.unserved_by_cause[cause] = run.unserved_by_cause.get(cause, 0) + 1
                    continue
                served.append(zid)
                flow += q[zid]
                vol_today += q[zid]
                load += e[zid]
            # Energy dispatch: PV, then grid, then battery; surplus PV charges the battery.
            deficit = max(0.0, load - pv_day[h])
            g = min(deficit, grid_room)
            deficit -= g
            if b is not None and soc is not None:
                if deficit > 0:
                    soc -= deficit / b.discharge_efficiency
                else:
                    surplus = pv_day[h] - load
                    soc = min(
                        b.soc_max_kwh, soc + min(surplus, b.max_charge_kw) * b.charge_efficiency
                    )
            run.energy_kwh += load
            run.grid_kwh += g

            # --- Truth: hourly balance with stress feedback ----------------------------------
            for zid, pr in params.items():
                z = by_id[zid]
                d0 = dep[zid]
                ks = 1.0 if d0 <= pr.raw else max(0.0, (pr.taw - d0) / (pr.taw - pr.raw))
                etc_h = pr.etc_day * DAYTIME[h]
                eta_h = ks * etc_h
                irr = _net_depth(z) if zid in served else 0.0
                d1 = min(pr.taw, max(0.0, d0 + eta_h - pr.peff_day / 24.0 - irr))
                dep[zid] = d1
                lg = logs[zid]
                lg.etc_mm += etc_h
                lg.eta_mm += eta_h
                lg.irrigation_m3 += q[zid] if zid in served else 0.0
                lg.stress_mm_h += max(0.0, d1 - pr.raw)
                lg.severe_h += int(d1 > pr.raw + severe_fraction * (pr.taw - pr.raw))
                lg.min_ks = min(lg.min_ks, ks)
        for zid, lg in logs.items():
            lg.dr_end_mm = dep[zid]
            run.zone_days.append(lg)
        day += timedelta(days=1)
    return run


# --- Metrics -------------------------------------------------------------------------------------


def summarise(run: BenchmarkRun, farm: FarmConfig) -> pd.DataFrame:
    df = pd.DataFrame([vars(r) for r in run.zone_days])
    rows = []
    by_id = {z.zone_id: z for z in farm.zones}
    for zid, g in df.groupby("zone_id", sort=False):
        crop = by_id[zid].setup.crop
        ry, reasons = relative_yield_stagewise(crop, g)
        rows.append(
            {
                "policy": run.policy,
                "zone": zid,
                "crop": crop.code,
                "water_m3": g["irrigation_m3"].sum(),
                "eta_over_etc": g["eta_mm"].sum() / g["etc_mm"].sum()
                if g["etc_mm"].sum()
                else None,
                "stress_mm_h": g["stress_mm_h"].sum(),
                "severe_hours": int(g["severe_h"].sum()),
                "days_with_stress": int((g["min_ks"] < 1.0).sum()),
                "relative_yield": ry,
                "yield_note": "; ".join(reasons) if reasons else "",
            }
        )
    return pd.DataFrame(rows)
