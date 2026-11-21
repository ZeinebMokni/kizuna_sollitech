"""Crop suitability on REAL multi-year weather and soil (west of Sidi Bouzid, 2015-2024).

REAL:          NASA POWER daily weather 2015-2024 (inferred), SoilGrids soil (inferred).
HYPOTHETICAL:  water quota per ha, energy per ha, irrigation-water salinity, soil depth,
               planting dates. Temperature thresholds are unverified placeholders.
Usage: uv run python examples/suitability_demo.py
"""

from __future__ import annotations

from datetime import date

from qatra_ai.agronomy.daily_et0 import compute_daily_et0
from qatra_ai.data.sources.nasa_power import fetch_power_daily
from qatra_ai.data.sources.soilgrids import fetch_soilgrids
from qatra_ai.suitability.engine import SiteConditions, assess_crops

LAT, LON = 35.10, 9.30
CROPS = {
    "tomato": (4, 1),
    "potato": (2, 1),
    "durum_wheat": (11, 15),
    "olive": (3, 1),
    "citrus": (3, 1),
    "date_palm": (3, 1),
}


def main() -> None:
    power = fetch_power_daily(LAT, LON, date(2015, 1, 1), date(2024, 12, 31))
    w = compute_daily_et0(
        power.daily,
        latitude_deg=power.latitude,
        elevation_m=power.elevation_m or 0.0,
        wind_height_m=2.0,
    )
    soil = fetch_soilgrids(LAT, LON).to_soil_properties().model_copy(update={"soil_depth_m": 1.5})
    site = SiteConditions(
        latitude=LAT,
        soil=soil,
        irrigation_water_ec_ds_m=1.5,
        available_water_m3_per_ha=6000,
        available_energy_kwh_per_ha=3000,
        pumping_head_m=60,
        weather_source=power.source,
        weather_data_class=power.data_class,
    )
    print(
        f"Weather {power.source} 2015-2024 ({power.data_class.value}); soil FC {soil.theta_fc} "
        f"WP {soil.theta_wp}; HYPOTHETICAL: 6000 m3/ha water, 3000 kWh/ha, ECw 1.5 dS/m, "
        "depth 1.5 m\n"
    )
    for r in assess_crops(CROPS, site, w):
        ind = r.indicators
        print(
            f"{r.crop:12s} planted {r.planting}  OVERALL {r.overall}  "
            f"limiting {r.limiting_factors or '-'}  Pareto {r.pareto_optimal}"
        )
        print(
            f"   need P80 {ind.get('gross_irrigation_p80_m3_per_ha')} m3/ha "
            f"(median {ind.get('gross_irrigation_median_m3_per_ha')}), "
            f"exp. yield {ind.get('expected_relative_yield')}, "
            f"energy {ind.get('pump_energy_p80_kwh_per_ha')} kWh/ha, "
            f"heat days {ind.get('mean_heat_days')}, frost share {ind.get('frost_season_share')}"
        )
        print(
            "   "
            + "; ".join(
                f"{f.factor}={f.suitability}" + (f"({f.value})" if f.value is not None else "")
                for f in r.factors
            )
        )
        if r.provisional_warnings:
            print(f"   provisional warnings: {r.provisional_warnings}")
        if r.undetermined_factors:
            print(f"   undetermined: {r.undetermined_factors}")


if __name__ == "__main__":
    main()
