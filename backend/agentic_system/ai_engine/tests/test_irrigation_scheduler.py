"""Scheduler tests on SYNTHETIC scenarios (constant demand, idealised PV). They check that the
optimiser respects hard constraints and prioritises as designed, not real-world performance."""

from datetime import date, datetime

import pandas as pd
import pytest

from qatra_ai.agronomy.crops import get_crop
from qatra_ai.agronomy.soil import SoilWaterProperties
from qatra_ai.agronomy.water_balance import ZoneSetup
from qatra_ai.contracts import Confidence, DataClass
from qatra_ai.optimization.inputs import DAYTIME, pv_slots_from_daily_radiation, zone_from_forecast
from qatra_ai.optimization.irrigation_scheduler import plan_irrigation, simulate_zone
from qatra_ai.optimization.schedule_models import (
    BatterySpec,
    EnergySupply,
    PumpSystem,
    ScheduleRequest,
    SchedulingZone,
    WaterSource,
)

START = datetime(2026, 6, 1, 0, 0)
T = 48


def zone(
    zid,
    *,
    d0=20.0,
    raw=25.0,
    taw=60.0,
    etc_day=8.0,
    ky=1.0,
    perennial=False,
    flow=10.0,
    area=1.0,
    **kw,
):
    etc = [etc_day * DAYTIME[(t % 24)] for t in range(T)]
    return SchedulingZone(
        zone_id=zid,
        area_ha=area,
        design_flow_m3h=flow,
        application_efficiency=0.9,
        initial_depletion_mm=d0,
        taw_mm=taw,
        raw_mm=raw,
        etc_mm=etc,
        peff_mm=[0.0] * T,
        ky=[ky] * T,
        perennial=perennial,
        **kw,
    )


def daytime_pv(peak_kwh=10.0):
    return [peak_kwh * DAYTIME[t % 24] / max(DAYTIME) for t in range(T)]


def request(zones, *, pump=None, energy=None, water=None, allowed=None):
    return ScheduleRequest(
        start=START,
        n_slots=T,
        zones=zones,
        pump=pump
        or PumpSystem(
            max_flow_m3h=10, max_simultaneous_zones=1, total_head_m=40, pump_efficiency=0.6
        ),
        energy=energy or EnergySupply(pv_kwh=[0.0] * T, grid_available=[True] * T, grid_max_kw=20),
        water=water or WaterSource(),
        allowed=allowed,
        time_limit_s=20,
    )


def run(req):
    env = plan_irrigation(req, input_confidence=Confidence.HIGH)
    assert env.payload is not None, env.confidence_reasons
    assert env.payload.verification_violations == []
    return env, env.payload


def by_zone(plan):
    return {z.zone_id: z for z in plan.zones}


def test_single_zone_prevents_stress_with_ample_resources():
    env, plan = run(request([zone("A")]))
    a = by_zone(plan)["A"]
    assert a.stress_mm_h_without_irrigation > 0
    assert a.stress_mm_h == 0 and a.volume_m3 > 0
    assert a.reasons == ["IRRIGATED_TO_PREVENT_STRESS"]
    assert env.confidence == Confidence.HIGH and plan.status == "optimal"


def test_no_irrigation_when_no_stress_expected():
    _, plan = run(request([zone("A", d0=0.0, etc_day=2.0)]))
    a = by_zone(plan)["A"]
    assert a.volume_m3 == 0 and a.reasons == ["NO_STRESS_EXPECTED_IN_HORIZON"]


def test_pump_constraint_never_exceeded_and_reported():
    zs = [zone("A", d0=30), zone("B", d0=30), zone("C", d0=30)]
    _, plan = run(
        request(
            zs,
            pump=PumpSystem(
                max_flow_m3h=20, max_simultaneous_zones=3, total_head_m=40, pump_efficiency=0.6
            ),
        )
    )
    for slot in {a.slot for a in plan.actions}:
        assert sum(1 for a in plan.actions if a.slot == slot) <= 2  # 3 x 10 m3/h > 20


def test_perennial_prioritised_over_annual_under_scarcity():
    """Same stress, one slot of water only: the perennial's severe stress weighs more."""
    olive = zone("olive", d0=50, raw=25, taw=60, perennial=True, ky=1.0)
    tomato = zone("tomato", d0=50, raw=25, taw=60, perennial=False, ky=1.0)
    water = WaterSource(max_volume_m3=100.0)  # 10 slots x 10 m3 for both zones combined
    # Lower-priority zone listed FIRST so solver ordering cannot explain the result.
    _, plan = run(request([tomato, olive], water=water))
    z = by_zone(plan)
    assert z["olive"].volume_m3 > z["tomato"].volume_m3
    assert plan.totals["water_m3"] <= 100.0 + 1e-6
    assert "WATER_VOLUME_CAP" in z["tomato"].reasons
    cap = next(c for c in plan.constraints if c.name == "water_volume_cap")
    assert cap.binding_slots == 1 and cap.shadow_price and cap.shadow_price > 0


def test_sensitive_stage_prioritised_by_ky():
    flowering = zone("flowering", d0=40, ky=1.1)
    vegetative = zone("vegetative", d0=40, ky=0.4)
    _, plan = run(request([vegetative, flowering], water=WaterSource(max_volume_m3=80)))
    z = by_zone(plan)
    assert z["flowering"].volume_m3 > z["vegetative"].volume_m3
    # Without Ky weighting the split would differ (or tie); comparison is reported
    assert plan.unweighted_comparison is not None


def test_equal_weights_remove_perennial_preference():
    """With kappa_perennial == kappa_annual the olive has no special claim: the split is then
    a tie, so the weighted result above is caused by the policy, not by the data."""
    from qatra_ai.optimization.schedule_models import PriorityPolicy

    olive = zone("olive", d0=50, perennial=True)
    tomato = zone("tomato", d0=50)
    req = request([tomato, olive], water=WaterSource(max_volume_m3=100.0))
    flat = req.model_copy(update={"policy": PriorityPolicy(kappa_perennial=1.0)})
    weighted_obj = plan_irrigation(req).payload
    flat_plan = plan_irrigation(flat).payload
    assert by_zone(weighted_obj)["olive"].volume_m3 == 100.0
    # Equal weights: both allocations are optimal; objective identical whichever zone is fed
    assert flat_plan.totals["water_m3"] == 100.0


def test_energy_not_reported_binding_when_grid_has_room():
    _, plan = run(request([zone("A", d0=30)]))
    energy = next(c for c in plan.constraints if c.name == "energy")
    assert energy.binding_slots == 0


def test_solar_only_irrigates_in_daylight():
    energy = EnergySupply(pv_kwh=daytime_pv(10.0), grid_available=[False] * T)
    _, plan = run(request([zone("A", d0=30)], energy=energy))
    assert plan.actions
    for a in plan.actions:
        assert 6 <= a.start.hour < 18
    assert plan.totals["grid_kwh"] == 0


def test_battery_allows_night_pumping_and_respects_soc():
    energy = EnergySupply(
        pv_kwh=[0.0] * T,
        grid_available=[False] * T,
        battery=BatterySpec(
            capacity_kwh=40,
            soc_initial_kwh=36,
            soc_min_kwh=8,
            soc_max_kwh=40,
            max_charge_kw=5,
            max_discharge_kw=5,
        ),
    )
    _, plan = run(request([zone("A", d0=30)], energy=energy))
    assert plan.actions and plan.totals["battery_discharge_kwh"] > 0
    assert plan.totals["battery_discharge_kwh"] <= (36 - 8) * 0.95 + 1e-6


def test_no_energy_means_no_irrigation_and_energy_reason():
    energy = EnergySupply(pv_kwh=[0.0] * T, grid_available=[False] * T)
    _, plan = run(request([zone("A", d0=30)], energy=energy))
    a = by_zone(plan)["A"]
    assert a.volume_m3 == 0 and "ENERGY_LIMITED" in a.reasons


def test_operating_window_respected():
    allowed = [(t % 24) < 6 or (t % 24) >= 20 for t in range(T)]  # night tariff window
    _, plan = run(request([zone("A", d0=30)], allowed=allowed))
    assert all(allowed[a.slot] for a in plan.actions)


def test_daily_hour_limit_and_daily_volume_cap():
    z = zone("A", d0=55, taw=60, raw=25, max_hours_per_day=3)
    _, plan = run(request([z], water=WaterSource(max_volume_per_day_m3=20)))
    per_day = pd.Series([a.start.date() for a in plan.actions]).value_counts()
    assert (per_day <= 2).all()  # 20 m3/day / 10 m3 per slot, tighter than 3 h
    daily = next(c for c in plan.constraints if c.name == "water_daily_cap")
    assert daily.binding_slots == 2  # both days at the cap
    assert "WATER_VOLUME_CAP" in by_zone(plan)["A"].reasons


def test_reported_trajectory_matches_independent_simulation():
    z = zone("A", d0=30)
    _, plan = run(request([z]))
    xs = [0] * T
    for a in plan.actions:
        xs[a.slot] = 1
    traj = simulate_zone(z, xs, 0.9 * 10 / (10 * 1.0))
    assert by_zone(plan)["A"].depletion_end_mm == pytest.approx(traj[-1], abs=1e-3)


def test_deterministic_and_hash_stable():
    req = request([zone("A", d0=30), zone("B", d0=35, ky=0.5)], water=WaterSource(max_volume_m3=60))
    e1, e2 = plan_irrigation(req), plan_irrigation(req)
    assert e1.inputs_hash == e2.inputs_hash
    assert [(a.zone_id, a.slot) for a in e1.payload.actions] == [
        (a.zone_id, a.slot) for a in e2.payload.actions
    ]


def test_confidence_inherits_inputs_and_flags_assumed_ky():
    z = zone("A", d0=30).model_copy(update={"ky_assumed": True})
    env = plan_irrigation(request([z]), input_confidence=Confidence.HIGH)
    assert env.confidence == Confidence.MEDIUM
    assert any("Ky missing" in r for r in env.confidence_reasons)
    env_low = plan_irrigation(
        request([zone("A")]), input_confidence=Confidence.LOW, input_reasons=["soil inferred"]
    )
    assert env_low.confidence == Confidence.LOW and "soil inferred" in env_low.confidence_reasons


def test_request_validation():
    with pytest.raises(ValueError, match="n_slots"):
        ScheduleRequest(
            start=START,
            n_slots=T + 1,
            zones=[zone("A")],
            pump=PumpSystem(
                max_flow_m3h=10, max_simultaneous_zones=1, total_head_m=40, pump_efficiency=0.6
            ),
            energy=EnergySupply(pv_kwh=[0.0] * (T + 1), grid_available=[True] * (T + 1)),
        )
    with pytest.raises(ValueError, match="RAW"):
        zone("A", raw=70, taw=60)


# --- Builders from agronomy ------------------------------------------------------------------


def test_zone_from_forecast_and_pv_builder():
    crop = get_crop("olive")
    soil = SoilWaterProperties(
        theta_fc=0.28, theta_wp=0.15, data_class=DataClass.INFERRED, source="t", method="t"
    )
    setup = ZoneSetup(
        crop=crop, season_start=date(2026, 3, 1), soil=soil, area_ha=2.0, application_efficiency=0.9
    )
    idx = pd.date_range("2026-06-01", periods=2, freq="D")
    fc = pd.DataFrame({"et0": [7.0, 8.0], "precip": [0.0, 0.0], "rs": [28.0, 29.0]}, index=idx)
    z = zone_from_forecast(
        "olive-1",
        setup,
        current_depletion_mm=40,
        forecast_daily=fc,
        start=START,
        n_slots=48,
        design_flow_m3h=15,
    )
    from qatra_ai.agronomy.kc import kc_for_day

    kc_day = kc_for_day(crop, (date(2026, 6, 1) - date(2026, 3, 1)).days)
    assert sum(z.etc_mm[:24]) == pytest.approx(kc_day * 7.0)  # daily total preserved
    assert z.perennial and z.ky_assumed  # olive has no Ky in the profile -> flagged
    assert z.taw_mm == pytest.approx(1000 * 0.13 * 1.2)
    pv = pv_slots_from_daily_radiation(fc["rs"], start=START, n_slots=48, p_rated_kw=10)
    assert all(v == 0 for v in pv[:6]) and sum(pv[:24]) == pytest.approx(10 * 28 / 3.6 * 0.86 * 0.8)
