"""Demo: run a full tomato season on REAL reanalysis weather (Open-Meteo archive).

What is real:      the weather inputs (ERA5-family reanalysis via Open-Meteo; data_class=inferred).
What is assumed:   the zone (crop, planting date, soil texture, area, efficiency, irrigation
                   schedule) is a HYPOTHETICAL example. Results are illustrations of the
                   engine, not advice for any real farm.

Usage:  uv run python examples/season_demo.py [--lat 35.04 --lon 9.48 --year 2025]
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

import numpy as np
import pandas as pd

from qatra_ai.agronomy.assessment import assess_zone_water
from qatra_ai.agronomy.crops import get_crop
from qatra_ai.agronomy.daily_et0 import compute_daily_et0
from qatra_ai.agronomy.soil import soil_from_texture
from qatra_ai.agronomy.water_balance import ZoneSetup
from qatra_ai.data.sources.nasa_power import fetch_power_daily
from qatra_ai.data.sources.open_meteo import fetch_daily_weather
from qatra_ai.data.sources.soilgrids import SoilGridsError, fetch_soilgrids


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, default=35.10)  # farmland west of Sidi Bouzid
    ap.add_argument("--lon", type=float, default=9.30)
    ap.add_argument("--weather", choices=["open_meteo", "nasa_power"], default="open_meteo")
    ap.add_argument("--year", type=int, default=2025)
    args = ap.parse_args()

    planting = date(args.year, 4, 1)
    crop = get_crop("tomato")
    end = planting + timedelta(days=crop.season_length_days - 1)

    if args.weather == "nasa_power":
        pw = fetch_power_daily(args.lat, args.lon, planting, end)
        print(
            f"Weather: {pw.source} ({pw.data_class.value}), {len(pw.daily)} days, "
            f"elevation {pw.elevation_m} m (grid cell ~50 km)"
        )
        w = compute_daily_et0(
            pw.daily, latitude_deg=pw.latitude, elevation_m=pw.elevation_m or 0.0, wind_height_m=2.0
        )
        source, data_class = pw.source, pw.data_class
    else:
        res = fetch_daily_weather(args.lat, args.lon, kind="archive", start=planting, end=end)
        print(
            f"Weather: {res.source} ({res.data_class.value}), {len(res.daily)} days, "
            f"elevation {res.elevation_m:.0f} m; dropped {res.dropped_incomplete_days}"
        )
        w = compute_daily_et0(res.daily, latitude_deg=res.latitude, elevation_m=res.elevation_m)
        source, data_class = res.source, res.data_class
        # Cross-check: QATRA daily FAO-56 PM vs Open-Meteo hourly FAO-56 (same input source)
        both = w[["et0", "et0_provider"]].dropna()
        diff = both["et0"] - both["et0_provider"]
        print(
            f"ET0 cross-check: bias {diff.mean():+.2f} mm/d | MAE {diff.abs().mean():.2f} | "
            f"r {np.corrcoef(both['et0'], both['et0_provider'])[0, 1]:.3f} | "
            f"totals {both['et0'].sum():.0f} vs {both['et0_provider'].sum():.0f} mm"
        )

    # --- Hypothetical zone ------------------------------------------------------------------
    try:
        soil = fetch_soilgrids(args.lat, args.lon).to_soil_properties()
    except SoilGridsError as exc:
        print(f"SoilGrids unavailable ({exc}); using a hypothetical sandy loam")
        soil = soil_from_texture(0.55, 0.15, 1.0, source="hypothetical sandy loam (demo)")
    print(f"Soil: FC {soil.theta_fc} WP {soil.theta_wp} ({soil.data_class.value}, {soil.source})")
    setup = ZoneSetup(
        crop=crop,
        season_start=planting,
        soil=soil,
        area_ha=1.0,
        application_efficiency=0.90,
        initial_depletion_mm=0.0,
    )
    # Hypothetical schedule: 15 mm gross every 3 days
    irrigation = pd.Series(15.0, index=w.index[::3])

    env = assess_zone_water(
        setup,
        w,
        weather_source=source,
        weather_data_class=data_class,
        irrigation_gross_mm=irrigation,
        design_flow_m3h=25.0,
    )
    p = env.payload
    assert p is not None
    print(
        f"\nZone assessment (confidence: {env.confidence.value}; model status: "
        f"{env.model.validation_status.value})"
    )
    for r in env.confidence_reasons:
        print(f"  - {r}")
    tot = p.season_totals
    print(
        f"  ET0 {tot['et0'].value:.0f} | ETc {tot['etc'].value:.0f} | ETa {tot['eta'].value:.0f} | "
        f"Peff {tot['effective_rain'].value:.0f} | Inet {tot['irrigation_net'].value:.0f} | "
        f"DP {tot['deep_percolation'].value:.0f} mm"
    )
    print(
        f"  ETa/ETc {p.relative_transpiration} | relative yield (FAO-33, stage-wise) "
        f"{p.relative_yield_estimate}"
    )
    days = pd.DataFrame(p.daily)
    print(
        f"  stressed days: {int(days['stressed'].sum())} of {len(days)}; "
        f"by stage: {days[days['stressed']].groupby('stage').size().to_dict()}"
    )
    print("  limitations:")
    for lim in env.limitations:
        print(f"    * {lim}")


if __name__ == "__main__":
    main()
