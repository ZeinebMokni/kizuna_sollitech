"""Climate 2050 scenarios for the farmland west of Sidi Bouzid -> docs/scenarios/.

REAL:          NASA POWER baseline 1995-2014; NASA NEX-GDDP-CMIP6 model output (projected).
HYPOTHETICAL:  water quota, energy, salinity, soil depth, planting dates (as suitability_demo),
               and the two stress-test scenarios.
Usage: uv run python examples/climate_2050.py   (first run downloads ~600 small files; cached)
       uv run python examples/climate_2050.py --farm <farm_id>
           any farm profile: its location, crops, soil and limits; the report goes to
           .cache/results/ (not docs/, since a real farm's results are private)
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
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


RESULTS_DIR = Path(__file__).resolve().parents[1] / ".cache" / "results"


@dataclass
class Target:
    """Where and what to assess. Default: the hypothetical demo setting (unchanged)."""

    lat: float = LAT
    lon: float = LON
    crops: dict = field(default_factory=lambda: dict(CROPS))
    ec: float | None = 1.5
    water_m3_ha: float | None = 6000
    energy_kwh_ha: float | None = 3000
    head_m: float = 60
    soil_depth_m: float | None = 1.5
    soil: object = None  # SoilWaterProperties; None -> SoilGrids
    title: str = "farmland west of Sidi Bouzid (35.10 N, 9.30 E)"
    report: Path = REPORT
    results_name: str = "climate_2050.json"
    farm_note: str = "hypothetical quota 6000 m3/ha, 3000 kWh/ha, ECw 1.5 dS/m, soil 1.5 m"
    params_note: str = (
        "Farm parameters (6000 m³/ha quota, 3000 kWh/ha, ECw 1.5 dS/m, 1.5 m soil, planting "
        "dates) are hypothetical."
    )


def target_for_farm(farm_id: str) -> Target:
    from qatra_ai.farms.registry import load_registry
    from qatra_ai.service.data import PublicDataProvider
    from qatra_ai.service.runtime import FarmRuntime

    p = load_registry().get(farm_id)
    crops = {c.crop: (c.planting_month, c.planting_day) for c in p.suitability_candidates} or {
        z.crop: (z.season_start.month, z.season_start.day) for z in p.zones
    }
    w, e = p.water, p.energy
    lat, lon = p.location.latitude, p.location.longitude
    note = (
        f"from farm profile {farm_id} ({p.kind}): quota {w.seasonal_m3_per_ha} m3/ha, "
        f"{e.seasonal_kwh_per_ha} kWh/ha, ECw {w.irrigation_ec_ds_m} dS/m, soil {p.soil_depth_m} m "
        "(None = not known)"
    )
    return Target(
        lat=lat,
        lon=lon,
        crops=crops,
        ec=w.irrigation_ec_ds_m,
        water_m3_ha=w.seasonal_m3_per_ha,
        energy_kwh_ha=e.seasonal_kwh_per_ha,
        head_m=p.pump.total_head_m,
        soil_depth_m=p.soil_depth_m,
        soil=FarmRuntime(p, PublicDataProvider()).soil,
        title=f"{p.name} ({lat:.2f} N, {lon:.2f} E)",
        report=RESULTS_DIR / f"climate_2050_{farm_id}.md",
        results_name=f"climate_2050_{farm_id}.json",
        farm_note=note,
        params_note=f"Farm parameters come from the farm profile `{farm_id}` ({p.kind}).",
    )


def model_data(
    client: NexGddpClient, model: str, scenario: str, years, lat: float, lon: float
) -> pd.DataFrame:
    cols = []
    for var in ("tasmax", "tasmin", "pr", "rsds"):
        try:
            cols.append(client.fetch(model, scenario, years, lat, lon, variables=[var]))
        except NexGddpError as exc:
            if var == "rsds":
                print(f"  {model} {scenario}: no rsds ({exc}); radiation held constant")
                continue
            raise
    return pd.concat(cols, axis=1)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Climate 2050 scenarios for a farm location")
    ap.add_argument("--farm", help="farm_id of a farm profile (default: the demo setting)")
    args = ap.parse_args(argv)
    tg = target_for_farm(args.farm) if args.farm else Target()

    power = fetch_power_daily(tg.lat, tg.lon, date(1995, 1, 1), date(2014, 12, 31))
    baseline = power.daily
    soil = tg.soil or fetch_soilgrids(tg.lat, tg.lon).to_soil_properties()
    if tg.soil_depth_m is not None:
        soil = soil.model_copy(update={"soil_depth_m": tg.soil_depth_m})
    site = SiteConditions(
        latitude=tg.lat,
        soil=soil,
        irrigation_water_ec_ds_m=tg.ec,
        available_water_m3_per_ha=tg.water_m3_ha,
        available_energy_kwh_per_ha=tg.energy_kwh_ha,
        pumping_head_m=tg.head_m,
        weather_source=power.source,
        weather_data_class=power.data_class,
    )

    scenarios = [
        Scenario("baseline 1995-2014", "historical", source=power.source),
        Scenario(
            "stress test: +2 C, -20 % rain",
            "hypothetical",
            MonthlyDeltas.uniform(dt=2.0, precip_pct=-20),
        ),
        Scenario(
            "stress test: +3 C, -30 % rain",
            "hypothetical",
            MonthlyDeltas.uniform(dt=3.0, precip_pct=-30),
        ),
    ]
    client = NexGddpClient(CACHE)
    failed = []
    try:
        for model in MODELS:
            try:
                hist = model_data(client, model, "historical", HIST_YEARS, tg.lat, tg.lon)
            except NexGddpError as exc:
                failed.append(f"{model}: {exc}")
                continue
            for ssp in SSPS:
                try:
                    fut = model_data(client, model, ssp, FUT_YEARS, tg.lat, tg.lon)
                except NexGddpError as exc:
                    failed.append(f"{model} {ssp}: {exc}")
                    continue
                d = monthly_deltas(hist, fut)
                scenarios.append(
                    Scenario(
                        f"{model} {ssp} 2041-2060",
                        "projected",
                        d,
                        ssp=ssp,
                        model=model,
                        window="2041-2060 vs 1995-2014",
                        source="NASA NEX-GDDP-CMIP6",
                    )
                )
                print(f"{model} {ssp}: {d.annual_summary()}", flush=True)
    finally:
        client.close()

    imp = run_impacts(
        baseline,
        scenarios,
        tg.crops,
        site,
        latitude=power.latitude,
        elevation_m=power.elevation_m or 0.0,
    )
    t = imp.table
    deltas = t.drop_duplicates("scenario")[
        [
            "scenario",
            "kind",
            "et0_annual_mm",
            "dtmax_mean_c",
            "dtmin_mean_c",
            "precip_ratio_mean",
            "rs_ratio_mean",
        ]
    ]
    cols = [
        "scenario",
        "kind",
        "crop",
        "overall",
        "irrigation_p50_m3_ha",
        "irrigation_p50_m3_ha_change_pct",
        "irrigation_p80_m3_ha",
        "irrigation_p80_m3_ha_change_pct",
        "expected_relative_yield",
        "heat_days",
    ]
    report = tg.report
    soil_line = f"{soil.source} → {soil.method} (`{soil.data_class.value}`)"
    report.parent.mkdir(parents=True, exist_ok=True)
    # Keep a hand-written "## Findings" section across regenerations.
    findings = ""
    if report.exists():
        old_text = report.read_text(encoding="utf-8")
        marker = "\n## Findings"
        if marker in old_text:
            findings = old_text[old_text.index(marker) :]
    report.write_text(
        f"""# Climate 2050 scenarios: {tg.title}

> **Scenarios, not forecasts.** *Projected* rows apply one climate model's change signal to the
> observed baseline (delta-change); the spread across models is the message, not any single
> row. *Hypothetical* rows are stress tests chosen by hand. {tg.params_note}

- Baseline: NASA POWER daily 1995–2014 (`inferred`). Soil: {soil_line}.
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
"""
        + findings,
        encoding="utf-8",
    )
    # Machine-readable results for the dashboard API (qatra_ai.service).
    results_dir = RESULTS_DIR
    results_dir.mkdir(parents=True, exist_ok=True)
    ens = imp.ensemble.copy()
    ens.columns = ["_".join(c).strip("_") if isinstance(c, tuple) else c for c in ens.columns]
    (results_dir / tg.results_name).write_text(
        json.dumps(
            {
                "location": {"latitude": tg.lat, "longitude": tg.lon},
                "models": MODELS,
                "ssps": SSPS,
                "not_retrieved": failed,
                "scenarios": json.loads(t.to_json(orient="records")),
                "ensemble": json.loads(ens.reset_index().to_json(orient="records")),
                "limitations": LIMITATIONS,
                "farm_note": tg.farm_note,
            }
        ),
        encoding="utf-8",
    )
    print(imp.ensemble.to_string())
    print(f"\nReport written to {report}")


if __name__ == "__main__":
    main()
