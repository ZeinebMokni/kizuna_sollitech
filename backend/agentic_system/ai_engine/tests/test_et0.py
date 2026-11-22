"""ET0 tests against the worked examples published in FAO-56 (Allen et al., 1998).

Expected values are those printed in the FAO-56 examples (rounded as published),
so tolerances reflect the publication's rounding.
"""

import numpy as np
import pandas as pd
import pytest

from qatra_ai.agronomy import et0 as fao
from qatra_ai.agronomy.daily_et0 import METHOD_HS, METHOD_MISSING, METHOD_PM, compute_daily_et0


def test_example_2_3_pressure_and_psychrometric_constant():
    # FAO-56 Examples 2-3: elevation 1800 m -> P = 81.8 kPa, gamma = 0.054 kPa/degC
    p = fao.atmospheric_pressure(1800)
    assert p == pytest.approx(81.8, abs=0.05)
    assert fao.psychrometric_constant(p) == pytest.approx(0.054, abs=0.0005)


def test_example_3_mean_saturation_vapour_pressure():
    # FAO-56 Example 3: Tmax 24.5, Tmin 15 -> e°(Tmax) 3.075, e°(Tmin) 1.705, es 2.39 kPa
    assert fao.saturation_vapour_pressure(24.5) == pytest.approx(3.075, abs=0.001)
    assert fao.saturation_vapour_pressure(15.0) == pytest.approx(1.705, abs=0.001)
    assert fao.mean_saturation_vapour_pressure(15.0, 24.5) == pytest.approx(2.39, abs=0.005)


def test_example_8_extraterrestrial_radiation():
    # FAO-56 Example 8: 20°S, 3 September (J = 246) -> Ra = 32.2 MJ m-2 day-1
    assert fao.extraterrestrial_radiation(-20.0, 246) == pytest.approx(32.2, abs=0.05)


def test_wind_conversion_worked_example():
    # FAO-56 worked example (chapter 3, wind): 3.2 m/s at 10 m -> 2.4 m/s at 2 m
    assert fao.wind_speed_at_2m(3.2, 10.0) == pytest.approx(2.4, abs=0.01)


class TestExample18Brussels:
    """FAO-56 Example 18: Uccle (Brussels), 6 July, 50°48'N, 100 m.
    Tmax 21.5, Tmin 12.3, RHmax 84, RHmin 63, wind 10 km/h at 10 m, sunshine 9.25 h.
    Published: ea 1.409, Ra 41.09, N 16.1, Rs 22.07, Rso 30.90, Rnl 3.71, Rn 13.28, ET0 3.9."""

    lat, doy, z = 50.80, 187, 100.0
    tmax, tmin, rhmax, rhmin = 21.5, 12.3, 84.0, 63.0

    def test_intermediate_values(self):
        ea = fao.actual_vapour_pressure_from_rh(self.tmin, self.tmax, self.rhmin, self.rhmax)
        assert ea == pytest.approx(1.409, abs=0.002)
        ra = fao.extraterrestrial_radiation(self.lat, self.doy)
        assert ra == pytest.approx(41.09, abs=0.05)
        n_max = fao.daylight_hours(self.lat, self.doy)
        assert n_max == pytest.approx(16.1, abs=0.05)
        rs = fao.solar_radiation_from_sunshine(9.25, n_max, ra)
        assert rs == pytest.approx(22.07, abs=0.05)
        rso = fao.clear_sky_radiation(ra, self.z)
        assert rso == pytest.approx(30.90, abs=0.05)
        rnl = fao.net_longwave_radiation(self.tmin, self.tmax, ea, rs, rso)
        assert rnl == pytest.approx(3.71, abs=0.02)
        assert fao.net_shortwave_radiation(rs) - rnl == pytest.approx(13.28, abs=0.05)

    def test_et0(self):
        ra = fao.extraterrestrial_radiation(self.lat, self.doy)
        rs = fao.solar_radiation_from_sunshine(9.25, fao.daylight_hours(self.lat, self.doy), ra)
        ea = fao.actual_vapour_pressure_from_rh(self.tmin, self.tmax, self.rhmin, self.rhmax)
        u2 = fao.wind_speed_at_2m(10.0 / 3.6, 10.0)
        et0 = fao.et0_penman_monteith(
            tmin=self.tmin,
            tmax=self.tmax,
            ea=ea,
            rs=rs,
            u2=u2,
            latitude_deg=self.lat,
            elevation_m=self.z,
            day_of_year=self.doy,
        )
        assert et0 == pytest.approx(3.9, abs=0.05)


def test_vectorised_matches_scalar():
    tmin = np.array([12.3, 20.0])
    tmax = np.array([21.5, 35.0])
    out = fao.et0_hargreaves(
        tmin=tmin, tmax=tmax, latitude_deg=35.0, day_of_year=np.array([187, 200])
    )
    single = fao.et0_hargreaves(tmin=20.0, tmax=35.0, latitude_deg=35.0, day_of_year=200)
    assert out[1] == pytest.approx(single)


def test_hargreaves_increases_with_temperature():
    lo = fao.et0_hargreaves(tmin=10, tmax=20, latitude_deg=35, day_of_year=180)
    hi = fao.et0_hargreaves(tmin=20, tmax=30, latitude_deg=35, day_of_year=180)
    assert 0 < lo < hi


def test_daily_table_method_selection():
    idx = pd.date_range("2026-07-01", periods=3, freq="D")
    df = pd.DataFrame(
        {
            "tmin": [20.0, 20.0, np.nan],
            "tmax": [34.0, 34.0, np.nan],
            "tdew": [12.0, np.nan, np.nan],
            "rs": [28.0, 28.0, 28.0],
            "wind": [3.0, 3.0, 3.0],
        },
        index=idx,
    )
    out = compute_daily_et0(df, latitude_deg=35.0, elevation_m=300.0)
    assert list(out["et0_method"]) == [METHOD_PM, METHOD_HS, METHOD_MISSING]
    assert out["et0"].iloc[0] > 0 and np.isnan(out["et0"].iloc[2])


def test_daily_table_rejects_inverted_temperatures():
    idx = pd.date_range("2026-07-01", periods=1, freq="D")
    with pytest.raises(ValueError):
        compute_daily_et0(
            pd.DataFrame({"tmin": [30.0], "tmax": [20.0]}, index=idx),
            latitude_deg=35,
            elevation_m=0,
        )
