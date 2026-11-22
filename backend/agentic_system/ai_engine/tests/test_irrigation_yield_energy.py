import pandas as pd
import pytest

from qatra_ai.agronomy.crops import Salinity, get_crop
from qatra_ai.agronomy.irrigation import irrigation_requirement, leaching_requirement
from qatra_ai.agronomy.yield_response import (
    relative_yield_salinity,
    relative_yield_seasonal,
    relative_yield_stagewise,
)
from qatra_ai.energy import Battery, cell_temperature, pump_energy_kwh, pv_power_kw


def test_irrigation_volume_and_runtime():
    r = irrigation_requirement(
        depletion_mm=30, area_ha=2.0, application_efficiency=0.9, design_flow_m3h=50
    )
    assert r.net_mm == 30
    assert r.gross_mm == pytest.approx(33.333, rel=1e-4)
    assert r.volume_m3 == pytest.approx(666.67, rel=1e-4)  # 1 mm on 1 ha = 10 m3
    assert r.runtime_h == pytest.approx(13.333, rel=1e-4)


def test_deficit_target_and_leaching():
    r = irrigation_requirement(
        depletion_mm=30,
        area_ha=1,
        application_efficiency=1.0,
        target_depletion_mm=10,
        leaching_fraction=0.2,
    )
    assert r.net_mm == 20 and r.gross_mm == pytest.approx(25.0)


def test_irrigation_validation():
    with pytest.raises(ValueError):
        irrigation_requirement(depletion_mm=10, area_ha=1, application_efficiency=0)


def test_leaching_requirement_surface_and_drip():
    tomato = get_crop("tomato").salinity  # threshold 2.5, slope 9.9
    assert leaching_requirement(1.0, tomato, "surface") == pytest.approx(1.0 / (12.5 - 1.0))
    max_ece = 2.5 + 100 / 9.9
    assert leaching_requirement(1.0, tomato, "drip") == pytest.approx(1.0 / (2 * max_ece))
    with pytest.raises(ValueError):
        leaching_requirement(13.0, tomato, "surface")


def test_seasonal_yield_response():
    assert relative_yield_seasonal(1.05, 100, 100) == 1.0
    assert relative_yield_seasonal(1.05, 80, 100) == pytest.approx(1 - 1.05 * 0.2)
    assert relative_yield_seasonal(2.0, 0, 100) == 0.0


def test_stagewise_yield_requires_all_stages():
    crop = get_crop("tomato")
    daily = pd.DataFrame(
        {
            "stage": ["initial", "development", "mid", "late"],
            "etc_mm": [10.0, 10.0, 10.0, 10.0],
            "eta_mm": [10.0, 10.0, 8.0, 10.0],
        }
    )
    ratio, reasons = relative_yield_stagewise(crop, daily)
    assert reasons == [] and ratio == pytest.approx(1 - 1.10 * 0.2)
    olive_ratio, olive_reasons = relative_yield_stagewise(get_crop("olive"), daily)
    assert olive_ratio is None and any("no Ky" in r for r in olive_reasons)


def test_salinity_yield():
    s = Salinity(threshold_ece_ds_m=2.5, slope_pct_per_ds_m=9.9)
    assert relative_yield_salinity(2.0, s) == 1.0
    assert relative_yield_salinity(4.5, s) == pytest.approx(1 - 0.099 * 2)


def test_pump_energy_rule_of_thumb():
    # 2.725 Wh per m3 per metre of head at 100 % efficiency
    assert pump_energy_kwh(1000, 1, 1.0, 1.0) == pytest.approx(2.724, abs=0.002)
    assert pump_energy_kwh(100, 50, 0.6, 0.9) == pytest.approx(
        100 * 50 * 2.7241e-3 / 0.54, rel=1e-3
    )


def test_pv_power():
    assert pv_power_kw(10, 0, 25) == 0.0
    stc = pv_power_kw(10, 1000, 25, system_efficiency=1.0)
    assert stc == pytest.approx(10.0)
    hot = pv_power_kw(10, 1000, cell_temperature(40, 1000), system_efficiency=1.0)
    assert hot < stc


def test_battery_limits_enforced():
    b = Battery(capacity_kwh=10, soc_min_fraction=0.2)
    assert b.step(5.0, 0.0, 0.95) == pytest.approx(4.0)
    with pytest.raises(ValueError):
        b.step(2.5, 0.0, 1.0)  # would fall below 2 kWh
