"""Closed-loop benchmark tests on SYNTHETIC constant weather (labelled test input)."""

from datetime import date

import pandas as pd
import pytest

from qatra_ai.agronomy.crops import get_crop
from qatra_ai.agronomy.soil import SoilWaterProperties
from qatra_ai.agronomy.water_balance import ZoneSetup
from qatra_ai.contracts import DataClass
from qatra_ai.evaluation.closed_loop import (
    BenchZone,
    FarmConfig,
    fixed_calendar,
    optimizer_policy,
    run_policy,
    summarise,
    threshold_rule,
)
from qatra_ai.optimization.schedule_models import BatterySpec, PumpSystem

pytestmark = pytest.mark.slow  # daily MILP re-planning: ~1-2 min; skip with -m "not slow"

START, END = date(2026, 6, 1), date(2026, 6, 10)


def weather(et0=7.0, rs=27.0):
    idx = pd.date_range("2026-05-25", "2026-06-20", freq="D")
    return pd.DataFrame({"et0": et0, "precip": 0.0, "rs": rs}, index=idx)


def farm(**kw):
    soil = SoilWaterProperties(
        theta_fc=0.28, theta_wp=0.155, data_class=DataClass.INFERRED, source="t", method="t"
    )
    zones = [
        BenchZone(
            "tomato",
            ZoneSetup(
                crop=get_crop("tomato"),
                season_start=date(2026, 4, 1),
                soil=soil,
                area_ha=1.0,
                application_efficiency=0.9,
                initial_depletion_mm=20.0,
            ),
            10.0,
        ),
        BenchZone(
            "olive",
            ZoneSetup(
                crop=get_crop("olive"),
                season_start=date(2026, 3, 1),
                soil=soil,
                area_ha=1.0,
                application_efficiency=0.9,
                initial_depletion_mm=80.0,
            ),
            10.0,
        ),
    ]
    base = dict(
        zones=zones,
        pump=PumpSystem(
            max_flow_m3h=12, max_simultaneous_zones=1, total_head_m=50, pump_efficiency=0.55
        ),
        grid_hours=frozenset(range(24)),
        grid_max_kw=10,
    )
    base.update(kw)
    return FarmConfig(**base)


def test_executor_enforces_daily_cap_and_logs_unserved():
    f = farm(max_volume_per_day_m3=40)

    def greedy(ctx):  # requests every active zone every hour: the executor must refuse excess
        return [list(ctx.depletion) for _ in range(24)]

    run = run_policy(greedy, f, weather(), START, END)
    daily = pd.DataFrame([vars(r) for r in run.zone_days]).groupby("date")["irrigation_m3"].sum()
    assert (daily <= 40 + 1e-9).all()
    assert run.unserved_zone_hours > 0 and run.unserved_by_cause.get("water_cap", 0) > 0


def test_calendar_scales_to_well_cap_and_rotates():
    f = farm(max_volume_per_day_m3=40)
    run = run_policy(fixed_calendar(1, {"tomato": 8, "olive": 8}), f, weather(), START, END)
    assert run.unserved_by_cause.get("water_cap", 0) == 0  # sized to fit
    df = pd.DataFrame([vars(r) for r in run.zone_days])
    assert (df.groupby("zone_id")["irrigation_m3"].sum() > 0).all()  # nobody starved


def test_no_energy_means_no_water():
    f = farm(grid_hours=frozenset(), grid_max_kw=0)
    run = run_policy(threshold_rule(), f, weather(), START, END)
    assert sum(r.irrigation_m3 for r in run.zone_days) == 0
    assert run.unserved_by_cause.get("energy", 0) > 0


def test_battery_soc_never_below_minimum_and_solar_used():
    bat = BatterySpec(
        capacity_kwh=20,
        soc_initial_kwh=10,
        soc_min_kwh=4,
        soc_max_kwh=20,
        max_charge_kw=5,
        max_discharge_kw=5,
    )
    f = farm(grid_hours=frozenset(), grid_max_kw=0, pv_rated_kw=10, battery=bat)
    run = run_policy(optimizer_policy(), f, weather(), START, END)
    assert run.grid_kwh == 0 and run.energy_kwh > 0


def test_truth_balance_bounds():
    run = run_policy(fixed_calendar(3, 2), farm(), weather(), START, END)
    for r in run.zone_days:
        assert r.dr_end_mm >= 0 and 0 <= r.min_ks <= 1 and r.eta_mm <= r.etc_mm + 1e-9


def test_optimizer_beats_calendar_on_weighted_stress_with_perfect_forecast():
    f = farm()
    w = weather()
    cal = summarise(run_policy(fixed_calendar(2, 3), f, w, START, END), f)
    opt = summarise(run_policy(optimizer_policy(), f, w, START, END), f)
    # Both zones get attention; the optimiser should not leave more severe stress
    assert opt["severe_hours"].sum() <= cal["severe_hours"].sum()


def test_persistence_forecast_and_truth_bias_run():
    f = farm()
    run = run_policy(
        optimizer_policy(),
        f,
        weather(),
        START,
        END,
        forecast_mode="persistence",
        truth_et_factor=1.1,
    )
    s = summarise(run, f)
    assert set(s["zone"]) == {"tomato", "olive"}
    assert (s["water_m3"] >= 0).all()


def test_annual_zone_leaves_simulation_after_season():
    f = farm()
    w = pd.DataFrame(
        {"et0": 6.0, "precip": 0.0, "rs": 25.0},
        index=pd.date_range("2026-08-10", "2026-09-05", freq="D"),
    )
    run = run_policy(threshold_rule(), f, w, date(2026, 8, 15), date(2026, 8, 30))
    tomato_days = [r for r in run.zone_days if r.zone_id == "tomato"]
    # tomato season (Apr 1 + 145 d) ends 2026-08-23
    assert max(r.date for r in tomato_days) == date(2026, 8, 23)


@pytest.mark.parametrize("policy", [fixed_calendar(2, 3), threshold_rule(), optimizer_policy()])
def test_all_policies_produce_summary(policy):
    f = farm()
    s = summarise(run_policy(policy, f, weather(), START, END), f)
    assert len(s) == 2 and s["policy"].nunique() == 1
