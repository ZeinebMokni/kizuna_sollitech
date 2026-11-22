"""Suitability tests on SYNTHETIC multi-year weather (labelled test input)."""

import numpy as np
import pandas as pd
import pytest

from qatra_ai.agronomy.soil import SoilWaterProperties
from qatra_ai.contracts import DataClass
from qatra_ai.suitability.engine import SiteConditions, assess_crop, assess_crops, mark_pareto


def weather(et0=5.0, precip=0.0, tmax=28.0, tmin=12.0, years=(2020, 2021, 2022, 2023)):
    idx = pd.date_range(f"{years[0]}-01-01", f"{years[-1] + 1}-12-31", freq="D")
    return pd.DataFrame({"et0": et0, "precip": precip, "tmax": tmax, "tmin": tmin}, index=idx)


def site(**kw):
    base = dict(
        latitude=35.0,
        soil=SoilWaterProperties(
            theta_fc=0.28,
            theta_wp=0.15,
            data_class=DataClass.INFERRED,
            source="t",
            method="t",
            soil_depth_m=2.0,
        ),
        available_water_m3_per_ha=20000,
        available_energy_kwh_per_ha=50000,
        irrigation_water_ec_ds_m=0.5,
        weather_source="synthetic",
        weather_data_class=DataClass.SIMULATED,
    )
    base.update(kw)
    return SiteConditions(**base)


def factor(res, name):
    return next(f for f in res.factors if f.factor == name)


def test_ample_resources_highly_suitable_except_market_undetermined():
    r = assess_crop("tomato", (4, 1), site(), weather())
    assert r.overall == "S1"
    assert factor(r, "market").suitability == "U"  # never silently assumed
    assert r.seasons_evaluated >= 4
    assert "temperature limits" in r.placeholder_parameters


def test_requirement_matches_water_budget():
    # No rain, constant ET0: net irrigation ~ season ETc (minus final unrefilled depletion)
    r = assess_crop("tomato", (4, 1), site(), weather(et0=6.0))
    etc = r.indicators["etc_median_mm"]
    gross = r.indicators["gross_irrigation_median_m3_per_ha"]
    assert gross == pytest.approx(etc / 0.9 * 10, rel=0.08)


def test_water_shortage_limits_with_ky():
    r = assess_crop("tomato", (4, 1), site(available_water_m3_per_ha=3000), weather(et0=6.0))
    w = factor(r, "water")
    assert w.suitability in ("S3", "N") and w.unit == "relative yield"
    assert "water" in r.limiting_factors or r.overall == "N"


def test_crop_without_ky_water_is_undetermined_not_unsuitable():
    r = assess_crop("olive", (3, 1), site(available_water_m3_per_ha=4000), weather(et0=6.0))
    w = factor(r, "water")
    assert w.suitability == "U" and "no Ky" in w.rule and w.value is not None
    assert r.overall == "U"  # water is critical: cannot judge, so say so


def test_unverified_temperature_thresholds_only_warn():
    cold = weather(tmin=-3.0)
    r = assess_crop("tomato", (4, 1), site(), cold)
    frost = factor(r, "frost")
    assert frost.suitability == "N" and frost.provisional
    assert r.overall != "N"  # placeholder thresholds cannot decide the overall class
    assert any("frost=N" in w for w in r.provisional_warnings)
    hot = weather(tmax=38.0)
    r2 = assess_crop("tomato", (4, 1), site(), hot)
    assert factor(r2, "heat").suitability == "N" and r2.provisional_warnings


def test_salinity_from_irrigation_water():
    r = assess_crop("potato", (3, 1), site(irrigation_water_ec_ds_m=3.0), weather())
    s = factor(r, "salinity")
    # ECe = 4.5 dS/m -> 1 - 0.12 * (4.5 - 1.7) = 0.664 -> S3
    assert s.value == pytest.approx(0.664, abs=1e-3) and s.suitability == "S3"


def test_missing_critical_data_gives_undetermined():
    r = assess_crop("tomato", (4, 1), site(available_water_m3_per_ha=None), weather())
    assert r.overall == "U" and "water" in r.undetermined_factors


def test_insufficient_weather_coverage():
    short = weather(years=(2020,)).loc[:"2020-05-01"]
    r = assess_crop("tomato", (4, 1), site(), short)
    assert r.seasons_evaluated == 0 and r.overall == "U"


def test_shallow_soil_limits_deep_rooted_crop():
    shallow = site(
        soil=SoilWaterProperties(
            theta_fc=0.28,
            theta_wp=0.15,
            soil_depth_m=0.6,
            data_class=DataClass.INFERRED,
            source="t",
            method="t",
        )
    )
    r = assess_crop("durum_wheat", (11, 1), shallow, weather())
    assert factor(r, "soil_depth").suitability == "N"  # 0.6 / 1.5 = 0.4


def test_pareto_and_no_single_score():
    res = assess_crops(
        {"tomato": (4, 1), "potato": (3, 1), "durum_wheat": (11, 1)}, site(), weather(et0=5.0)
    )
    assert all(hasattr(r, "factors") and not hasattr(r, "score") for r in res)
    flags = [r.pareto_optimal for r in res if r.overall in ("S1", "S2", "S3")]
    assert any(flags)  # at least one non-dominated crop


def test_pareto_dominance_logic():
    r = assess_crop("tomato", (4, 1), site(), weather())
    better = r.model_copy(
        update={
            "indicators": {
                **r.indicators,
                "gross_irrigation_p80_m3_per_ha": r.indicators["gross_irrigation_p80_m3_per_ha"]
                - 100,
            },
            "crop": "better",
        }
    )
    out = {x.crop: x.pareto_optimal for x in mark_pareto([r, better])}
    assert out == {"tomato": False, "better": True}
    assert np.isfinite(r.indicators["pump_energy_p80_kwh_per_ha"])


def test_pareto_ignores_placeholder_indicators():
    a = assess_crop("tomato", (4, 1), site(), weather(tmax=38.0))  # many (provisional) hot days
    b = a.model_copy(
        update={
            "crop": "b",
            "indicators": {
                **a.indicators,
                "mean_heat_days": 0.0,
                "gross_irrigation_p80_m3_per_ha": a.indicators["gross_irrigation_p80_m3_per_ha"]
                + 1,
            },
        }
    )
    out = {x.crop: x.pareto_optimal for x in mark_pareto([a, b])}
    # b is better only on a placeholder-based indicator and worse on water -> a dominates
    assert out == {"tomato": True, "b": False}
