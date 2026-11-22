"""QC and Open-Meteo parsing tests. The Open-Meteo payload below is a SYNTHETIC fixture with
the API's response shape, built to test parsing and aggregation; its numbers are not
real observations."""

import numpy as np
import pandas as pd
import pytest

from qatra_ai.data.qc import GAP_FILLED, INVALID, SUSPECT, VALID, QCRules, apply_qc
from qatra_ai.data.sources.open_meteo import OpenMeteoError, hourly_to_daily, parse_hourly


def synthetic_payload(days=2, start="2026-07-01T00:00"):
    times = pd.date_range(start, periods=24 * days + 1, freq="h")  # includes next 00:00
    n = len(times)
    hours = times.hour.to_numpy()
    return {
        "latitude": 35.0,
        "longitude": 9.5,
        "elevation": 350.0,
        "timezone": "Africa/Tunis",
        "hourly_units": {"wind_speed_10m": "m/s"},
        "hourly": {
            "time": [t.strftime("%Y-%m-%dT%H:%M") for t in times],
            "temperature_2m": list(20 + 10 * np.sin((hours - 9) / 24 * 2 * np.pi)),
            "relative_humidity_2m": list(np.full(n, 50.0)),
            "dew_point_2m": list(np.full(n, 10.0)),
            "wind_speed_10m": list(np.full(n, 3.0)),
            "shortwave_radiation": list(np.where((hours >= 7) & (hours <= 19), 500.0, 0.0)),
            "precipitation": list(np.where(hours == 15, 2.0, 0.0)),
            "et0_fao_evapotranspiration": list(np.full(n, 0.25)),
        },
    }


def test_hourly_to_daily_aggregates_correctly():
    daily, dropped = hourly_to_daily(parse_hourly(synthetic_payload(days=2)))
    # After shifting accumulations back 1 h, both calendar days are complete; the
    # trailing 00:00 sample belongs to day 2. Day 3 has 1 instantaneous hour -> dropped.
    assert len(daily) == 2 and dropped
    d0 = daily.iloc[0]
    assert d0["tmax"] == pytest.approx(30.0, abs=0.1) and d0["tmin"] == pytest.approx(10.0, abs=0.1)
    assert d0["wind"] == pytest.approx(3.0)
    assert d0["precip"] == pytest.approx(2.0)
    # 13 hours x 500 W/m2 x 3600 s = 23.4 MJ/m2 (the 07:00 value covers 06-07 h)
    assert d0["rs"] == pytest.approx(23.4)
    assert d0["et0_provider"] == pytest.approx(6.0)


def test_parse_rejects_wrong_wind_unit_and_empty():
    p = synthetic_payload()
    p["hourly_units"]["wind_speed_10m"] = "km/h"
    with pytest.raises(OpenMeteoError):
        parse_hourly(p)
    with pytest.raises(OpenMeteoError):
        parse_hourly({"hourly": {}})


def test_qc_flags_range_spike_and_fills_short_gap_only():
    idx = pd.date_range("2026-07-01", periods=12, freq="30min")
    s = pd.Series(
        [0.20, 0.20, 0.21, 0.95, 0.21, np.nan, 0.21, 0.20, np.nan, np.nan, np.nan, 0.19], index=idx
    )
    s.iloc[2] = 0.21
    out = apply_qc(s, QCRules(min_value=0, max_value=0.6, max_rate_per_hour=0.1, max_gap_fill="1h"))
    assert out["flag"].iloc[3] in (INVALID, GAP_FILLED)  # out of range -> removed
    assert out["raw_value"].iloc[3] == 0.95  # original kept
    assert out["flag"].iloc[5] == GAP_FILLED  # 1 h gap -> filled
    assert out["flag"].iloc[9] != GAP_FILLED  # 2 h gap -> not filled
    assert np.isnan(out["value"].iloc[9])


def test_qc_spike_marked_suspect():
    idx = pd.date_range("2026-07-01", periods=5, freq="1h")
    s = pd.Series([0.20, 0.20, 0.40, 0.20, 0.20], index=idx)
    out = apply_qc(s, QCRules(max_rate_per_hour=0.1))
    assert out["flag"].iloc[2] == SUSPECT and out["flag"].iloc[0] == VALID


def test_qc_flatline():
    idx = pd.date_range("2026-07-01", periods=10, freq="1h")
    out = apply_qc(pd.Series(0.25, index=idx), QCRules(flatline_window="6h"))
    assert (out["flag"].iloc[3:] == SUSPECT).all()


# --- SoilGrids / NASA POWER parsing (SYNTHETIC fixtures with the real response shapes) ---

from qatra_ai.data.sources.nasa_power import parse_power  # noqa: E402
from qatra_ai.data.sources.soilgrids import SoilGridsError, parse_soilgrids  # noqa: E402


def _sg_layer(name, d_factor, values):
    return {
        "name": name,
        "unit_measure": {"d_factor": d_factor},
        "depths": [{"label": lbl, "values": {"mean": v}} for lbl, v in values.items()],
    }


def test_soilgrids_units_and_depth_weighting():
    depths = {"0-5cm": 1, "5-15cm": 1, "15-30cm": 1, "30-60cm": 1}
    payload = {
        "properties": {
            "layers": [
                _sg_layer("sand", 10, {k: 400 for k in depths}),  # 400 g/kg mapped -> 40 %
                _sg_layer(
                    "clay", 10, {"0-5cm": 100, "5-15cm": 100, "15-30cm": 300, "30-60cm": 300}
                ),
                _sg_layer("soc", 10, {k: 100 for k in depths}),  # 100 dg/kg -> 10 g/kg
            ]
        }
    }
    p = parse_soilgrids(payload, max_depth_cm=60)
    assert p.sand_pct == pytest.approx(40.0)
    # clay: (10*5 + 10*10 + 30*15 + 30*30) / 60 = 25 %
    assert p.clay_pct == pytest.approx(25.0)
    assert p.soc_g_kg == pytest.approx(10.0)
    assert p.organic_matter_pct == pytest.approx(1.724)


def test_soilgrids_null_prediction_is_an_error():
    payload = {"properties": {"layers": [_sg_layer("sand", 10, {"0-5cm": None})]}}
    with pytest.raises(SoilGridsError):
        parse_soilgrids(payload)


def test_nasa_power_fill_values_become_nan():
    payload = {
        "properties": {
            "parameter": {
                "T2M_MAX": {"20250401": 25.0, "20250402": -999.0},
                "ALLSKY_SFC_SW_DWN": {"20250401": 20.0, "20250402": 21.0},
            }
        },
        "parameters": {"ALLSKY_SFC_SW_DWN": {"units": "MJ/m^2/day"}},
    }
    df = parse_power(payload)
    assert df["tmax"].iloc[0] == 25.0 and np.isnan(df["tmax"].iloc[1])
    assert df["rs"].iloc[1] == 21.0
