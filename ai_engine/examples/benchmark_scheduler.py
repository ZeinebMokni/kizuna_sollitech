"""Closed-loop benchmark of irrigation policies on REAL weather and soil (Sidi Bouzid area, 2025).

REAL:          NASA POWER daily weather (data_class inferred), SoilGrids soil (inferred).
HYPOTHETICAL:  the farm (zones, crops, dates, flows, pump, PV, battery, well cap).
MODEL CAVEAT:  the "truth" uses the same FAO-56 model as the planner (see closed_loop.py).

Writes a markdown report to docs/evaluation/. Runtime: several minutes (daily MILP re-planning).
Usage: uv run python examples/benchmark_scheduler.py
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from qatra_ai.agronomy.crops import get_crop
from qatra_ai.agronomy.daily_et0 import compute_daily_et0
from qatra_ai.agronomy.water_balance import ZoneSetup
from qatra_ai.data.sources.nasa_power import fetch_power_daily
from qatra_ai.data.sources.soilgrids import fetch_soilgrids
from qatra_ai.evaluation.closed_loop import (
    BenchZone,
    FarmConfig,
    fixed_calendar,
    optimizer_policy,
    run_policy,
    size_calendar_hours,
    summarise,
    threshold_rule,
)
from qatra_ai.optimization.schedule_models import BatterySpec, PumpSystem

LAT, LON = 35.10, 9.30
START, END = date(2025, 3, 2), date(2025, 8, 23)
REPORT = (
    Path(__file__).resolve().parents[2] / "docs" / "evaluation" / "scheduler_closed_loop_2025.md"
)


def build_inputs():
    """Real weather + soil for the site, and the hypothetical benchmark farm."""
    power = fetch_power_daily(LAT, LON, START - timedelta(days=1), END + timedelta(days=3))
    w = compute_daily_et0(
        power.daily,
        latitude_deg=power.latitude,
        elevation_m=power.elevation_m or 0.0,
        wind_height_m=2.0,
    )
    soil = fetch_soilgrids(LAT, LON).to_soil_properties()

    def zone(zid, crop, start, area, flow):
        return BenchZone(
            zid,
            ZoneSetup(
                crop=get_crop(crop),
                season_start=start,
                soil=soil,
                area_ha=area,
                application_efficiency=0.9,
                initial_depletion_mm=0.0,
            ),
            flow,
        )

    farm = FarmConfig(
        zones=[
            zone("olive-north", "olive", date(2025, 3, 1), 2.0, 12.0),
            zone("tomato-east", "tomato", date(2025, 4, 1), 1.0, 10.0),
            zone("potato-south", "potato", date(2025, 3, 1), 1.0, 10.0),
        ],
        pump=PumpSystem(
            max_flow_m3h=15, max_simultaneous_zones=1, total_head_m=60, pump_efficiency=0.55
        ),
        pv_rated_kw=12.0,
        battery=BatterySpec(
            capacity_kwh=20,
            soc_initial_kwh=10,
            soc_min_kwh=4,
            soc_max_kwh=20,
            max_charge_kw=5,
            max_discharge_kw=5,
        ),
        max_volume_per_day_m3=120.0,
    )
    return power, w, soil, farm


def main() -> None:
    power, w, soil, farm = build_inputs()
    season_w = w.loc[pd.Timestamp(START) : pd.Timestamp(END)]
    cal_hours = size_calendar_hours(farm, season_w, interval_days=2)

    scenarios = [
        (
            "Fixed calendar (every 2 d, season-average sizing, scaled to well cap, rotating order)",
            fixed_calendar(2, cal_hours),
            {},
        ),
        ("Threshold rule (refill when Dr >= RAW, driest first)", threshold_rule(), {}),
        (
            "Optimiser, perfect forecast",
            optimizer_policy(mip_relative_gap=1e-3, time_limit_s=10),
            {},
        ),
        (
            "Optimiser, persistence forecast",
            optimizer_policy(mip_relative_gap=1e-3, time_limit_s=10),
            {"forecast_mode": "persistence"},
        ),
    ]
    results, runs, timings = [], {}, {}
    for label, pol, kw in scenarios:
        t0 = time.perf_counter()
        run = run_policy(pol, farm, w, START, END, **kw)
        timings[label] = time.perf_counter() - t0
        runs[label] = run
        s = summarise(run, farm)
        s.insert(0, "scenario", label)
        results.append(s)
        print(f"{label}: {timings[label]:.0f}s, water {s['water_m3'].sum():.0f} m3")

    # Robustness: truth ET 10 % higher than planners assume
    robust = []
    for lbl, pol, kw in [scenarios[0], scenarios[1], scenarios[3]]:
        r = run_policy(pol, farm, w, START, END, truth_et_factor=1.10, **kw)
        s = summarise(r, farm)
        s.insert(0, "scenario", lbl + " [truth ET +10 %]")
        robust.append(s)

    table = pd.concat(results, ignore_index=True)
    rtable = pd.concat(robust, ignore_index=True)
    write_report(table, rtable, runs, farm, cal_hours, power, soil)
    print(f"\nReport written to {REPORT}")


def _fmt(df: pd.DataFrame) -> str:
    out = df.copy()
    for c in ("water_m3", "stress_mm_h"):
        out[c] = out[c].round(0).astype(int)
    out["eta_over_etc"] = out["eta_over_etc"].round(3)
    out["relative_yield"] = out["relative_yield"].map(lambda v: "n/a" if pd.isna(v) else f"{v:.3f}")
    cols = [
        "scenario",
        "zone",
        "water_m3",
        "eta_over_etc",
        "stress_mm_h",
        "severe_hours",
        "days_with_stress",
        "relative_yield",
    ]
    return out[cols].to_markdown(index=False)


def write_report(table, rtable, runs, farm, cal_hours, power, soil) -> None:
    totals = (
        table.groupby("scenario", sort=False)
        .agg(
            water_m3=("water_m3", "sum"),
            stress_mm_h=("stress_mm_h", "sum"),
            severe_hours=("severe_hours", "sum"),
        )
        .round(0)
        .astype(int)
    )
    totals["unserved_zone_hours"] = [runs[s].unserved_zone_hours for s in totals.index]
    totals["pump_energy_kwh"] = [round(runs[s].energy_kwh) for s in totals.index]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        f"""# Closed-loop benchmark: irrigation policies (simulation only)

> **Simulation-tested, not field-validated.** The "truth" water balance uses the same FAO‑56
> model as the planner. Results compare decision policies *given that model*. They do not show
> real-world performance.

- **Period:** {START} → {END}. Each policy re-plans daily at 00:00 and executes 24 h.
- **Weather (real):** NASA POWER daily, grid cell containing {LAT} N, {LON} E (~50 km cells; data_class `inferred`).
- **Soil (real):** SoilGrids 0–60 cm → Saxton–Rawls: FC {soil.theta_fc}, WP {soil.theta_wp} (`inferred`).
- **Farm (hypothetical):** olive 2 ha (cycle from Mar 1), tomato 1 ha (planted Apr 1), potato 1 ha (planted Mar 1);
  drip, application efficiency 0.9; well pump max 15 m³/h, one zone at a time, 60 m head;
  off-grid PV 12 kWp + 20 kWh battery; well cap 120 m³/day.
- **Fixed calendar hours per event (every 2 days):** {cal_hours}
- **Shared knowledge:** every policy sees the exact current soil-water state (as with calibrated sensors).
- **Executor:** requests beyond pump, energy or water limits are dropped and counted as "unserved".
- **Baselines are made competent on purpose:** the calendar scales every zone to fit the well cap
  and rotates which zone goes first; the threshold rule serves the driest zone first.
- **Optimiser settings:** 72 h horizon re-solved daily, MIP gap 0.1 %, 10 s time limit per solve,
  PV derated 20 % in planning (actual PV is not derated in the executor).
- **Not included:** an equal-seasonal-water comparison (needs a seasonal water budget, not yet built).

## Farm totals

{totals.to_markdown()}

## Per zone

{_fmt(table)}

## Robustness: real ET 10 % higher than planners assume

{_fmt(rtable)}

## How to read this

- `stress_mm_h`: sum over hours of depletion beyond RAW (mm·h). `severe_hours`: hours beyond
  RAW + 50 % of (TAW − RAW). For perennials, severe hours are the irreversibility proxy.
- `relative_yield`: FAO‑33 stage-wise Ya/Ym, only where every growth stage has a Ky and fell
  inside the period. Olive has no Ky in its profile, so its yield is not estimated.
- Crop parameters are international reference values (`needs_review`). Weights follow the
  default `PriorityPolicy` (perennial severe-stress multiplier 5, annual 1).

## Limitations

- Same model for planner and truth. Robustness is probed only through the ET bias and forecast mode.
- The farm is deliberately water-short (seasonal crop demand far exceeds the 120 m3/day well cap),
  so every policy causes stress. Differences show *how* scarcity is shared, not whether it is avoided.
- No rainfall forecast skill is modelled beyond perfect vs persistence.
- No sensor noise; no pump breakdowns; constant pump head.
- One location, one season, one hypothetical farm: not generalisable.
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
