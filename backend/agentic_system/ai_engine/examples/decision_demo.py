"""Demo: ranked decision packages ("where to intervene first") on REAL weather and soil.

REAL: NASA POWER weather and SoilGrids soil (both data_class inferred).
HYPOTHETICAL: the farm, its past irrigation, pump, PV, battery and well cap. The "forecast" is
historical weather replayed. Not advice for any real farm.
Usage: uv run python examples/decision_demo.py [--day 2025-06-15]
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta

import pandas as pd

from qatra_ai.agronomy.crops import get_crop
from qatra_ai.agronomy.daily_et0 import compute_daily_et0
from qatra_ai.agronomy.water_balance import ZoneSetup, simulate_water_balance
from qatra_ai.contracts import Provenance
from qatra_ai.data.sources.nasa_power import fetch_power_daily
from qatra_ai.data.sources.soilgrids import fetch_soilgrids
from qatra_ai.optimization.schedule_models import BatterySpec, PumpSystem
from qatra_ai.orchestrator.decision import FarmContext, ZoneContext, decide

LAT, LON = 35.10, 9.30
ZONES = [
    ("olive-north", "olive", date(2025, 3, 1), 2.0, 12.0),
    ("tomato-east", "tomato", date(2025, 4, 1), 1.0, 10.0),
    ("potato-south", "potato", date(2025, 3, 1), 1.0, 10.0),
]


def build_decision(day: date = date(2025, 6, 15)):
    power = fetch_power_daily(LAT, LON, date(2025, 3, 1), day + timedelta(days=4))
    w = compute_daily_et0(
        power.daily,
        latitude_deg=power.latitude,
        elevation_m=power.elevation_m or 0.0,
        wind_height_m=2.0,
    )
    soil = fetch_soilgrids(LAT, LON).to_soil_properties()
    hist = w.loc[: pd.Timestamp(day - timedelta(days=1))]

    zones = []
    for zid, crop, start, area, flow in ZONES:
        setup = ZoneSetup(
            crop=get_crop(crop),
            season_start=start,
            soil=soil,
            area_ha=area,
            application_efficiency=0.9,
            initial_depletion_mm=0.0,
        )
        h = hist.loc[pd.Timestamp(start) :]
        table, _ = simulate_water_balance(setup, h, pd.Series(12.0, index=h.index[::4]))
        prov = Provenance(
            data_class=power.data_class,
            source="fao56_water_balance+nasa_power",
            quality_grade="C",
            method="modelled; no soil-moisture sensor",
        )
        zones.append(ZoneContext(zid, setup, flow, float(table["dr_end_mm"].iloc[-1]), prov))

    ctx = FarmContext(
        farm_id="demo-farm",
        as_of=datetime.combine(day, datetime.min.time()),
        zones=zones,
        forecast_daily=w.loc[pd.Timestamp(day) :],
        forecast_source=power.source,
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
    return decide(ctx)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", type=date.fromisoformat, default=date(2025, 6, 15))
    day = ap.parse_args().day
    env = build_decision(day)
    print(
        f"Decision for {day} | overall confidence {env.confidence.value} | "
        f"schedule {env.payload.schedule_status}\n"
    )
    for p in env.payload.packages:
        amt = f" {p.amount.value} {p.amount.unit}" if p.amount else ""
        print(
            f"#{p.rank} [tier {p.tier}: {p.tier_label}] {p.action.upper()}{amt} -> {p.target}"
            f"  (approval: {p.requires_human_approval}, confidence {p.confidence.value})"
        )
        for r in p.reasons:
            print(f"    reason  {r.code}: {r.text}")
        print(f"    why here: {'; '.join(p.priority_trace)}")
        if p.windows:
            print(f"    windows (next 24 h): {', '.join(x[11:] for x in p.windows)}")
        if p.expected_impact:
            print(
                "    impact: "
                + ", ".join(f"{k} {v.value} {v.unit}" for k, v in p.expected_impact.items())
            )
        for a in p.alternatives:
            print(f"    alternative: {a}")
        if p.constraints:
            print(f"    limits: {p.constraints}")
        print()


if __name__ == "__main__":
    main()
