"""Water-balance tests. Weather here is SYNTHETIC test input (constant, labelled), used to
check physics invariants, not to represent any real place."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from qatra_ai.agronomy.assessment import assess_zone_water
from qatra_ai.agronomy.crops import get_crop
from qatra_ai.agronomy.soil import SoilWaterProperties
from qatra_ai.agronomy.water_balance import ZoneSetup, days_to_stress, simulate_water_balance
from qatra_ai.contracts import Confidence, DataClass

START = date(2026, 4, 1)


def soil(data_class=DataClass.MEASURED):
    return SoilWaterProperties(
        theta_fc=0.30, theta_wp=0.15, data_class=data_class, source="test", method="test"
    )


def setup(**kw):
    base = dict(
        crop=get_crop("tomato"),
        season_start=START,
        soil=soil(),
        area_ha=1.0,
        application_efficiency=0.9,
        initial_depletion_mm=0.0,
        climate_adjust_kc=False,
    )
    base.update(kw)
    return ZoneSetup(**base)


def weather(days=60, et0=5.0, precip=0.0, start=START):
    idx = pd.date_range(start, periods=days, freq="D")
    return pd.DataFrame({"et0": et0, "precip": precip, "et0_method": "penman_monteith"}, index=idx)


def test_mass_balance_closes_every_day():
    w = weather(120, et0=6.0)
    w.loc[w.index[10], "precip"] = 40.0
    w.loc[w.index[50], "precip"] = 3.0  # below 0.2*ET0 threshold? 3 >= 1.2 -> effective
    irr = pd.Series(25.0, index=w.index[::7])
    t, _ = simulate_water_balance(setup(), w, irr)
    lhs = t["dr_end_mm"] - t["dr_start_mm"]
    rhs = (
        t["eta_mm"]
        - t["peff_mm"]
        - t["irrigation_net_mm"]
        + t["deep_percolation_mm"]
        + t["assimilation_adjustment_mm"]
    )
    np.testing.assert_allclose(lhs, rhs, atol=1e-9)
    # Continuity: today's start equals yesterday's end (TAW only grows for annual crops)
    np.testing.assert_allclose(t["dr_start_mm"].iloc[1:], t["dr_end_mm"].iloc[:-1], atol=1e-9)


def test_depletion_bounded_and_stress_develops_without_water():
    t, _ = simulate_water_balance(setup(), weather(100, et0=7.0))
    assert (t["dr_end_mm"] >= 0).all() and (t["dr_end_mm"] <= t["taw_mm"] + 1e-9).all()
    assert (t.loc[t["dr_start_mm"] <= t["raw_mm"], "ks"] == 1.0).all()
    assert t["stressed"].any()
    assert t["ks"].iloc[-1] < 1.0
    assert (t["eta_mm"] <= t["etc_mm"] + 1e-12).all()


def test_light_rain_is_not_effective():
    w = weather(5, et0=5.0)
    w["precip"] = 0.5  # < 0.2 * 5 mm
    t, _ = simulate_water_balance(setup(), w)
    assert (t["peff_mm"] == 0).all()


def test_excess_water_becomes_deep_percolation():
    w = weather(3, et0=5.0)
    w.loc[w.index[1], "precip"] = 100.0
    t, _ = simulate_water_balance(setup(), w)
    assert t["deep_percolation_mm"].iloc[1] > 0
    assert t["dr_end_mm"].iloc[1] == 0


def test_days_outside_annual_season_are_skipped():
    w = weather(10, start=date(2026, 3, 25))
    t, _ = simulate_water_balance(setup(), w)
    assert t.index[0].date() == START and len(t) == 3


def test_perennial_wraps_cycle():
    t, _ = simulate_water_balance(setup(crop=get_crop("olive")), weather(400, et0=3.0))
    assert len(t) == 400 and t["season_day"].iloc[365] == 0


def test_rejects_gaps_and_missing_precip():
    w = weather(10).drop(index=pd.Timestamp("2026-04-05"))
    with pytest.raises(ValueError, match="continuous"):
        simulate_water_balance(setup(), w)
    w2 = weather(5)
    w2.loc[w2.index[2], "precip"] = np.nan
    with pytest.raises(ValueError, match="precipitation"):
        simulate_water_balance(setup(), w2)


def test_et0_gap_is_filled_and_flagged():
    w = weather(10)
    w.loc[w.index[6], "et0"] = np.nan
    t, _ = simulate_water_balance(setup(), w)
    assert "et0_gap_filled" in t["flags"].iloc[6]
    assert t["et0_mm"].iloc[6] == pytest.approx(5.0)


def test_calibrated_sensor_pulls_estimate_uncalibrated_is_ignored():
    w = weather(30, et0=5.0)
    day = w.index[20]
    obs = pd.DataFrame({"theta": [0.29], "std": [0.01], "calibrated": [True]}, index=[day])
    t_ref, _ = simulate_water_balance(setup(), w)
    t_cal, _ = simulate_water_balance(setup(), w, soil_moisture_obs=obs)
    # Sensor says the soil is nearly at FC -> estimate moves down towards it
    assert t_cal.loc[day, "dr_end_mm"] < t_ref.loc[day, "dr_end_mm"]
    assert "assimilated" in t_cal.loc[day, "flags"].split(",")
    assert t_cal.loc[day, "depletion_std_mm"] < t_ref.loc[day, "depletion_std_mm"]

    obs_uncal = obs.assign(calibrated=False)
    t_unc, _ = simulate_water_balance(setup(), w, soil_moisture_obs=obs_uncal)
    assert t_unc.loc[day, "dr_end_mm"] == pytest.approx(t_ref.loc[day, "dr_end_mm"])
    assert "obs_uncalibrated_not_assimilated" in t_unc.loc[day, "flags"]


def test_days_to_stress_projection():
    s = setup()
    n, _ = days_to_stress(s, current_depletion_mm=0.0, forecast=weather(30, et0=6.0))
    assert n is not None and n > 0
    n0, _ = days_to_stress(s, current_depletion_mm=60.0, forecast=weather(5, et0=6.0))
    assert n0 == 0  # already beyond RAW (TAW = 30 mm at day 0)
    wet = weather(10, et0=1.0)
    wet["precip"] = 10.0
    n_none, _ = days_to_stress(s, 0.0, wet)
    assert n_none is None


class TestAssessmentEnvelope:
    def test_confidence_capped_by_unreviewed_crop_and_inferred_soil(self):
        env = assess_zone_water(
            setup(soil=soil(DataClass.INFERRED)),
            weather(40),
            weather_source="test",
            weather_data_class=DataClass.MEASURED,
        )
        assert env.confidence == Confidence.MEDIUM
        assert any("not locally reviewed" in r for r in env.confidence_reasons)
        assert any("inferred" in r for r in env.confidence_reasons)
        assert env.model.validation_status.value == "literature_parameterised"
        assert env.payload is not None and env.payload.depletion.unit == "mm"
        assert len(env.inputs_hash) == 64

    def test_unknown_initial_state_lowers_confidence(self):
        env = assess_zone_water(
            setup(initial_depletion_mm=None),
            weather(40),
            weather_source="test",
            weather_data_class=DataClass.MEASURED,
        )
        assert env.confidence == Confidence.LOW

    def test_simulated_weather_is_low_confidence(self):
        env = assess_zone_water(
            setup(), weather(40), weather_source="sim", weather_data_class=DataClass.SIMULATED
        )
        assert env.confidence == Confidence.LOW
        assert DataClass.SIMULATED in env.provenance_summary

    def test_insufficient_evidence_when_et0_mostly_missing(self):
        w = weather(10)
        w["et0_method"] = "missing"
        env = assess_zone_water(
            setup(), w, weather_source="t", weather_data_class=DataClass.MEASURED
        )
        assert env.confidence == Confidence.INSUFFICIENT_EVIDENCE
        assert env.payload is None and env.missing_inputs

    def test_stagewise_yield_unavailable_for_partial_season_and_no_ky(self):
        env = assess_zone_water(
            setup(), weather(40), weather_source="t", weather_data_class=DataClass.MEASURED
        )
        assert env.payload.relative_yield_estimate is None
        assert any("not simulated" in r for r in env.payload.relative_yield_unavailable_reasons)

    def test_full_season_yield_and_inputs_hash_deterministic(self):
        w = weather(145, et0=5.0)
        irr = pd.Series(20.0, index=w.index[::3])
        a = assess_zone_water(
            setup(),
            w,
            irrigation_gross_mm=irr,
            weather_source="t",
            weather_data_class=DataClass.MEASURED,
            request_id="r1",
        )
        b = assess_zone_water(
            setup(),
            w,
            irrigation_gross_mm=irr,
            weather_source="t",
            weather_data_class=DataClass.MEASURED,
            request_id="r2",
        )
        assert a.inputs_hash == b.inputs_hash
        assert a.payload.relative_yield_estimate is not None
        assert 0 <= a.payload.relative_yield_estimate <= 1
