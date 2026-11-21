"""Climate scenario tests on SYNTHETIC data (labelled test input)."""

import numpy as np
import pandas as pd
import pytest

from qatra_ai.agronomy import et0 as fao
from qatra_ai.agronomy.soil import SoilWaterProperties
from qatra_ai.climate.scenarios import (
    MonthlyDeltas,
    Scenario,
    apply_deltas,
    monthly_deltas,
    run_impacts,
)
from qatra_ai.contracts import DataClass
from qatra_ai.data.sources.nex_gddp import NexGddpError, parse_ncss_csv
from qatra_ai.suitability.engine import SiteConditions


def daily(years=(2000, 2001, 2002), tmax=30.0, tmin=15.0, precip=1.0, rs=25.0, tdew=10.0):
    idx = pd.date_range(f"{years[0]}-01-01", f"{years[-1]}-12-31", freq="D")
    return pd.DataFrame(
        {"tmax": tmax, "tmin": tmin, "precip": precip, "rs": rs, "tdew": tdew, "wind": 2.0},
        index=idx,
    )


def test_monthly_deltas_recover_known_signal():
    hist = daily()
    fut = daily(years=(2050, 2051, 2052), tmax=32.0, tmin=16.5, precip=0.8, rs=26.0)
    d = monthly_deltas(hist, fut)
    assert np.allclose(d.dtmax, 2.0) and np.allclose(d.dtmin, 1.5)
    assert np.allclose(d.precip_ratio, 0.8) and np.allclose(d.rs_ratio, 1.04)


def test_precip_ratio_is_capped():
    d = monthly_deltas(daily(precip=0.1), daily(years=(2050, 2051, 2052), precip=5.0))
    assert d.precip_ratio.max() == 3.0


def test_apply_deltas_and_constant_relative_humidity():
    base = daily()
    out = apply_deltas(base, MonthlyDeltas.uniform(dt=2.0, precip_pct=-20, rs_pct=5))
    assert np.allclose(out["tmax"], 32.0) and np.allclose(out["precip"], 0.8)
    assert np.allclose(out["rs"], 26.25)
    rh_before = fao.saturation_vapour_pressure(10.0) / fao.saturation_vapour_pressure(22.5)
    rh_after = fao.saturation_vapour_pressure(out["tdew"].iloc[0]) / fao.saturation_vapour_pressure(
        24.5
    )
    assert rh_after == pytest.approx(rh_before, rel=1e-6)
    assert out["tdew"].iloc[0] > 10.0  # dew point rises with warming


def test_warming_raises_et0_and_irrigation_need():
    base = daily(years=(2000, 2001, 2002, 2003), precip=0.0)
    site = SiteConditions(
        latitude=35.0,
        soil=SoilWaterProperties(
            theta_fc=0.28,
            theta_wp=0.15,
            data_class=DataClass.INFERRED,
            source="t",
            method="t",
            soil_depth_m=2.0,
        ),
        available_water_m3_per_ha=8000,
        available_energy_kwh_per_ha=50000,
        irrigation_water_ec_ds_m=0.5,
        weather_source="synthetic",
        weather_data_class=DataClass.SIMULATED,
    )
    scenarios = [
        Scenario("baseline", "historical"),
        Scenario("+2C", "hypothetical", MonthlyDeltas.uniform(dt=2.0)),
        Scenario("m1", "projected", MonthlyDeltas.uniform(dt=1.5), ssp="ssp245", model="m1"),
        Scenario("m2", "projected", MonthlyDeltas.uniform(dt=2.5), ssp="ssp245", model="m2"),
    ]
    imp = run_impacts(base, scenarios, {"tomato": (4, 1)}, site, latitude=35.0, elevation_m=300)
    t = imp.table.set_index("scenario")
    assert t.loc["+2C", "et0_annual_mm"] > t.loc["baseline", "et0_annual_mm"]
    assert t.loc["+2C", "irrigation_p80_m3_ha_change_pct"] > 0
    assert t.loc["baseline", "irrigation_p80_m3_ha_change_pct"] == 0
    assert set(t["kind"]) == {"historical", "hypothetical", "projected"}
    ens = imp.ensemble.loc[("ssp245", "tomato")]
    lo, hi = (
        ens[("irrigation_p80_m3_ha_change_pct", "min")],
        ens[("irrigation_p80_m3_ha_change_pct", "max")],
    )
    assert lo < hi and ens["models"].item() == 2  # spread across models, not one number
    assert imp.limitations


def test_ncss_csv_parser_and_errors():
    csv = (
        'time,station,latitude[unit="degrees_north"],longitude[unit="degrees_east"],'
        'tasmax[unit="K"]\n2050-07-01T12:00:00Z,p,35.125,9.375,309.6751\n'
        "2050-07-02T12:00:00Z,p,35.125,9.375,310.0\n"
    )
    s = parse_ncss_csv(csv, "tasmax")
    assert len(s) == 2 and s.iloc[0] == pytest.approx(309.6751)
    with pytest.raises(NexGddpError):
        parse_ncss_csv("a,b\n1,2\n", "tasmax")
