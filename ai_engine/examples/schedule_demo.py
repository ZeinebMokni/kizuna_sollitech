"""Demo: agronomy engine -> 72 h multi-zone irrigation schedule, on REAL weather and soil.

REAL inputs:   NASA POWER daily weather and SoilGrids soil texture for the chosen point.
HYPOTHETICAL:  the farm (zones, crops, dates, areas, flows, pump, solar array, battery,
               aquifer cap, past irrigation). The "forecast" is historical weather replayed
               as if it were a forecast (no archived forecasts are used).
This illustrates the engine; it is not advice for any real farm.

Usage: uv run python examples/schedule_demo.py [--lat 35.10 --lon 9.30 --day 2025-06-15]
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta

import pandas as pd

from qatra_ai.agronomy.crops import get_crop
from qatra_ai.agronomy.daily_et0 import compute_daily_et0
from qatra_ai.agronomy.water_balance import ZoneSetup, simulate_water_balance
from qatra_ai.contracts import Confidence
from qatra_ai.data.sources.nasa_power import fetch_power_daily
from qatra_ai.data.sources.soilgrids import fetch_soilgrids
from qatra_ai.optimization.inputs import (
    DISAGGREGATION_ASSUMPTIONS,
    pv_slots_from_daily_radiation,
    zone_from_forecast,
)
from qatra_ai.optimization.irrigation_scheduler import plan_irrigation
from qatra_ai.optimization.schedule_models import (
    BatterySpec,
    EnergySupply,
    PumpSystem,
    ScheduleRequest,
    WaterSource,
)

HORIZON_H = 72

# Hypothetical farm: (zone id, crop, season start, area ha, design flow m3/h)
ZONES = [
    ("olive-north", "olive", date(2025, 3, 1), 2.0, 12.0),
    ("tomato-east", "tomato", date(2025, 4, 1), 1.0, 10.0),
    ("potato-south", "potato", date(2025, 3, 1), 1.0, 10.0),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, default=35.10)
    ap.add_argument("--lon", type=float, default=9.30)
    ap.add_argument("--day", type=date.fromisoformat, default=date(2025, 6, 15))
    args = ap.parse_args()

    first = min(z[2] for z in ZONES)
    last = args.day + timedelta(days=HORIZON_H // 24)
    power = fetch_power_daily(args.lat, args.lon, first, last)
    weather = compute_daily_et0(
        power.daily,
        latitude_deg=power.latitude,
        elevation_m=power.elevation_m or 0.0,
        wind_height_m=2.0,
    )
    soil = fetch_soilgrids(args.lat, args.lon).to_soil_properties()
    print(
        f"Real inputs: NASA POWER {first}..{last}; soil {soil.source} "
        f"FC {soil.theta_fc} WP {soil.theta_wp} ({soil.data_class.value})"
    )

    history = weather.loc[: pd.Timestamp(args.day - timedelta(days=1))]
    forecast = weather.loc[pd.Timestamp(args.day) :]
    start = datetime.combine(args.day, datetime.min.time())

    sched_zones = []
    for zid, crop_code, season_start, area, flow in ZONES:
        setup = ZoneSetup(
            crop=get_crop(crop_code),
            season_start=season_start,
            soil=soil,
            area_ha=area,
            application_efficiency=0.9,
            initial_depletion_mm=0.0,
        )
        hist = history.loc[pd.Timestamp(season_start) :]
        # Hypothetical past practice: 12 mm gross every 4 days
        past_irrigation = pd.Series(12.0, index=hist.index[::4])
        table, _ = simulate_water_balance(setup, hist, past_irrigation)
        dr = float(table["dr_end_mm"].iloc[-1])
        z = zone_from_forecast(
            zid,
            setup,
            current_depletion_mm=dr,
            forecast_daily=forecast,
            start=start,
            n_slots=HORIZON_H,
            design_flow_m3h=flow,
        )
        stage = table["stage"].iloc[-1]
        print(
            f"  {zid:13s} {crop_code:7s} stage {stage:11s} Dr {dr:5.1f} mm  RAW {z.raw_mm:5.1f}"
            f"  TAW {z.taw_mm:5.1f}  "
            + ("Ky missing -> default weight" if z.ky_assumed else f"Ky {max(z.ky):.2f}")
        )
        sched_zones.append(z)

    req = ScheduleRequest(
        start=start,
        n_slots=HORIZON_H,
        zones=sched_zones,
        pump=PumpSystem(
            max_flow_m3h=15, max_simultaneous_zones=1, total_head_m=60, pump_efficiency=0.55
        ),
        water=WaterSource(max_volume_per_day_m3=120, note="hypothetical aquifer permit"),
        energy=EnergySupply(
            pv_kwh=pv_slots_from_daily_radiation(
                forecast["rs"], start=start, n_slots=HORIZON_H, p_rated_kw=12
            ),
            grid_available=[False] * HORIZON_H,  # off-grid well
            battery=BatterySpec(
                capacity_kwh=20,
                soc_initial_kwh=10,
                soc_min_kwh=4,
                soc_max_kwh=20,
                max_charge_kw=5,
                max_discharge_kw=5,
            ),
        ),
    )
    env = plan_irrigation(
        req,
        input_confidence=Confidence.MEDIUM,
        input_reasons=[
            "crop parameters not locally reviewed",
            "soil FC/WP inferred from SoilGrids",
        ],
    )
    plan = env.payload
    if plan is None:
        print("No plan:", env.confidence_reasons, env.limitations)
        return
    print(
        f"\nPlan: {plan.status} by {plan.solver} in {plan.solve_time_s}s | "
        f"confidence {env.confidence.value} | verification violations: "
        f"{len(plan.verification_violations)}"
    )
    for z in plan.zones:
        print(
            f"  {z.zone_id:13s} {z.volume_m3:6.1f} m3 {z.irrigation_hours:4.0f} h | stress "
            f"{z.stress_mm_h:7.1f} (no irrigation {z.stress_mm_h_without_irrigation:7.1f}) mm h | "
            f"{', '.join(z.reasons)}"
        )
    print("  totals:", {k: v for k, v in plan.totals.items() if v})
    print("  if all zones weighted equally (m3):", plan.unweighted_comparison)
    for cst in plan.constraints:
        sp = "" if cst.shadow_price is None else f", shadow price {cst.shadow_price:.3f}"
        unit = "day(s)" if cst.name == "water_daily_cap" else "slot(s)"
        print(f"  constraint {cst.name}: binding in {cst.binding_slots} {unit}{sp}")
    hours = pd.DataFrame([(a.start, a.zone_id) for a in plan.actions], columns=["start", "zone"])
    print("\nSchedule (hours on):")
    for zid, g in hours.groupby("zone"):
        print(f"  {zid:13s} " + ", ".join(t.strftime("%d %Hh") for t in g["start"]))
    print("\nAssumptions:", *plan.assumptions, *DISAGGREGATION_ASSUMPTIONS, sep="\n  - ")


if __name__ == "__main__":
    main()
