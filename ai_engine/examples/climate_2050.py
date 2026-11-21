"""Climate 2050 scenarios for the farmland west of Sidi Bouzid -> docs/scenarios/.

REAL:          NASA POWER baseline 1995-2014; NASA NEX-GDDP-CMIP6 model output (projected).
HYPOTHETICAL:  water quota, energy, salinity, soil depth, planting dates (as suitability_demo),
               and the two stress-test scenarios.
Usage: uv run python examples/climate_2050.py   (first run downloads ~600 small files; cached)
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from qatra_ai.climate.scenarios import (
    LIMITATIONS,
    MonthlyDeltas,
    Scenario,
    monthly_deltas,
    run_impacts,
)
from qatra_ai.data.sources.nasa_power import fetch_power_daily
from qatra_ai.data.sources.nex_gddp import NexGddpClient, NexGddpError
from qatra_ai.data.sources.soilgrids import fetch_soilgrids
from qatra_ai.suitability.engine import SiteConditions

LAT, LON = 35.10, 9.30
MODELS = ["INM-CM5-0", "MRI-ESM2-0", "MPI-ESM1-2-HR", "EC-Earth3", "CanESM5"]
SSPS = ["ssp245", "ssp585"]
HIST_YEARS = list(range(1995, 2015, 2))
FUT_YEARS = list(range(2041, 2061, 2))
CROPS = {"tomato": (4, 1), "potato": (2, 1), "durum_wheat": (11, 15), "citrus": (3, 1)}
ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs" / "scenarios" / "climate_2050_sidi_bouzid.md"
CACHE = Path(__file__).resolve().parents[1] / ".cache" / "nex_gddp"


def model_data(client: NexGddpClient, model: str, scenario: str, years) -> pd.DataFrame:
    cols = []
    for var in ("tasmax", "tasmin", "pr", "rsds"):
        try:
            cols.append(client.fetch(model, scenario, years, LAT, LON, variables=[var]))
        except NexGddpError as exc:
            if var == "rsds":
                print(f"  {model} {scenario}: no rsds ({exc}); radiation held constant")
                continue
            raise
    return pd.concat(cols, axis=1)


def main() -> None:
    power = fetch_power_daily(LAT, LON, date(1995, 1, 1), date(2014, 12, 31))
    baseline = power.daily
    soil = fetch_soilgrids(LAT, LON).to_soil_properties().model_copy(update={"soil_depth_m": 1.5})
    site = SiteConditions(
        latitude=LAT, soil=soil, irrigation_water_ec_ds_m=1.5, available_water_m3_per_ha=6000,
        available_energy_kwh_per_ha=3000, pumping_head_m=60, weather_source=power.source,
        weather_data_class=power.data_class)

    scenarios = [
        Scenario("baseline 1995-2014", "historical", source=power.source),
        Scenario("stress test: +2 C, -20 % rain", "hypothetical",
                 MonthlyDeltas.uniform(dt=2.0, precip_pct=-20)),
        Scenario("stress test: +3 C, -30 % rain", "hypothetical",
                 MonthlyDeltas.uniform(dt=3.0, precip_pct=-30)),
    ]
    client = NexGddpClient(CACHE)
    failed = []
    try:
        for model in MODELS:
            try:
                hist = model_data(client, model, "historical", HIST_YEARS)
            except NexGddpError as exc:
                failed.append(f"{model}: {exc}")
                continue
            for ssp in SSPS:
                try:
                    fut = model_data(client, model, ssp, FUT_YEARS)
                except NexGddpError as exc:
                    failed.append(f"{model} {ssp}: {exc}")
                    continue
                d = monthly_deltas(hist, fut)
                scenarios.append(Scenario(f"{model} {ssp} 2041-2060", "projected", d, ssp=ssp,
                                          model=model, window="2041-2060 vs 1995-2014",
                                          source="NASA NEX-GDDP-CMIP6"))
                print(f"{model} {ssp}: {d.annual_summary()}", flush=True)
    finally:
        client.close()

    imp = run_impacts(baseline, scenarios, CROPS, site, latitude=power.latitude,
                      elevation_m=power.elevation_m or 0.0)
    t = imp.table
    deltas = t.drop_duplicates("scenario")[["scenario", "kind", "et0_annual_mm", "dtmax_mean_c",
                                            "dtmin_mean_c", "precip_ratio_mean", "rs_ratio_mean"]]
    cols = ["scenario", "kind", "crop", "overall", "irrigation_p50_m3_ha",
            "irrigation_p50_m3_ha_change_pct", "irrigation_p80_m3_ha",
            "irrigation_p80_m3_ha_change_pct", "expected_relative_yield", "heat_days"]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(f"""# Climate 2050 scenarios: farmland west of Sidi Bouzid (35.10 N, 9.30 E)

> **Scenarios, not forecasts.** *Projected* rows apply one climate model's change signal to the
> observed baseline (delta-change); the spread across models is the message, not any single
> row. *Hypothetical* rows are stress tests chosen by hand. Farm parameters (6000 m³/ha quota,
> 3000 kWh/ha, ECw 1.5 dS/m, 1.5 m soil, planting dates) are hypothetical.

- Baseline: NASA POWER daily 1995–2014 (`inferred`). Soil: SoilGrids → Saxton–Rawls (`inferred`).
- Projections: NASA NEX-GDDP-CMIP6 (0.25°, bias-corrected), models {", ".join(MODELS)};
  SSP2-4.5 and SSP5-8.5; change = 2041–2060 vs 1995–2014, every second year sampled per window.
- Not retrieved: {"; ".join(failed) if failed else "none"}.

## Climate change signal per scenario

{deltas.to_markdown(index=False)}

## Ensemble spread (projected scenarios): change in dry-year (P80) irrigation need, %

{imp.ensemble.to_markdown()}

## All scenarios by crop

{t[cols].to_markdown(index=False)}

## Limitations

{chr(10).join("- " + x for x in LIMITATIONS)}
- Every second year sampled per 20-year window to limit download volume.
- Groundwater response is not simulated (aquifer parameters are not available).
""", encoding="utf-8")
    print(imp.ensemble.to_string())
    print(f"\nReport written to {REPORT}")


if __name__ == "__main__":
    main()
