"""Evaluate the engine's weather input (NASA POWER, gridded) against the DGACTA CRRA station.

First comparison of QATRA's inputs with a Tunisian ground station. Uses only station readings
flagged `valid` by the archiver (air temperature, solar radiation, wind; the station's humidity,
pressure and ET0 failed QC). Output: docs/evaluation/weather_nasa_power_vs_crra.md

Method
- Station days: local calendar days (UTC+1); a day counts only if it has >= 10 temperature
  readings, the first <= 02:00 and the last >= 22:00 local, and no gap > 3 h.
- Station Tmax/Tmin = max/min of the samples (2-hourly sampling misses the true extremes:
  Tmax is biased low and Tmin high by a fraction of a degree).
- Station Rs = time integral of W/m2 (trapezoid, zero at the day's ends) -> MJ/m2/day.
- Station wind is assumed to be measured at 2 m (DGACTA agro-met standard; not confirmed).
- ET0: FAO-56 Penman-Monteith with all-POWER inputs (what the engine uses) vs a hybrid with
  station Tmax/Tmin/Rs/wind and POWER dew point (the station humidity sensor failed).

    uv run python examples/eval_weather_vs_station.py
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from qatra_ai.agronomy.daily_et0 import compute_daily_et0
from qatra_ai.data.sources.nasa_power import fetch_power_daily
from qatra_ai.data.station_selection import STATIONS

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "processed" / "dgacta_sidi_bouzid" / "sb_crra.csv"
OUT = ROOT / "docs" / "evaluation" / "weather_nasa_power_vs_crra.md"
STATION = next(s for s in STATIONS if s.station_id == "sb_crra")


def station_daily() -> tuple[pd.DataFrame, int]:
    d = pd.read_csv(SRC)
    d = d[
        (d.qc_flag == "valid")
        & d.variable.isin(["air_temperature", "solar_radiation", "wind_speed"])
    ]
    d["t"] = pd.to_datetime(d.timestamp_utc).dt.tz_convert("Etc/GMT-1")  # UTC+1 (Tunisia)
    w = d.pivot_table(index="t", columns="variable", values="value")
    rows, candidate_days = [], 0
    for day, g in w.groupby(w.index.date):
        candidate_days += 1
        g = g.dropna(subset=["air_temperature"])
        hrs = g.index.hour + g.index.minute / 60
        gaps = np.diff(np.r_[hrs.to_numpy()])
        if len(g) < 10 or hrs.min() > 2 or hrs.max() < 22 or (gaps > 3.01).any():
            continue
        r = g["solar_radiation"].dropna()
        x = np.r_[0.0, r.index.hour + r.index.minute / 60, 24.0]
        y = np.r_[0.0, r.to_numpy(), 0.0]
        rows.append(
            {
                "date": pd.Timestamp(day),
                "n": len(g),
                "tmax": g.air_temperature.max(),
                "tmin": g.air_temperature.min(),
                "rs": float(np.trapezoid(y, x)) * 3600 / 1e6,
                "wind": g.wind_speed.mean(),
            }
        )
    return pd.DataFrame(rows).set_index("date"), candidate_days


def metrics(a: pd.Series, b: pd.Series) -> dict:
    ok = a.notna() & b.notna()
    e = (a - b)[ok]
    return {
        "days": int(ok.sum()),
        "station_mean": round(float(b[ok].mean()), 2),
        "power_mean": round(float(a[ok].mean()), 2),
        "bias": round(float(e.mean()), 2),
        "mae": round(float(e.abs().mean()), 2),
        "rmse": round(float(np.sqrt((e**2).mean())), 2),
        "r": round(float(np.corrcoef(a[ok], b[ok])[0, 1]), 2) if ok.sum() > 2 else None,
    }


def main() -> None:
    st, candidates = station_daily()
    if st.empty:
        raise SystemExit("no complete station days")
    power = fetch_power_daily(
        STATION.latitude, STATION.longitude, st.index.min().date(), st.index.max().date()
    )
    pw = power.daily.reindex(st.index)
    rows = {
        "Tmax (degC)": metrics(pw.tmax, st.tmax),
        "Tmin (degC)": metrics(pw.tmin, st.tmin),
        "Solar radiation Rs (MJ/m2/day)": metrics(pw.rs, st.rs),
        "Wind at 2 m (m/s)": metrics(pw.wind, st.wind),
    }
    elev = power.elevation_m or 350.0
    et_power = compute_daily_et0(
        pw[["tmin", "tmax", "tdew", "rs", "wind"]],
        latitude_deg=STATION.latitude,
        elevation_m=elev,
        wind_height_m=power.wind_height_m,
    )["et0"]
    hybrid = pd.DataFrame(
        {"tmin": st.tmin, "tmax": st.tmax, "tdew": pw.tdew, "rs": st.rs, "wind": st.wind}
    )
    hybrid["tdew"] = np.minimum(hybrid.tdew, hybrid.tmin)  # keep ea physically consistent
    et_hybrid = compute_daily_et0(
        hybrid, latitude_deg=STATION.latitude, elevation_m=elev, wind_height_m=2.0
    )["et0"]
    rows["ET0 Penman-Monteith (mm/day)"] = metrics(et_power, et_hybrid)
    rel = (et_power.sum() - et_hybrid.sum()) / et_hybrid.sum() * 100

    table = pd.DataFrame(rows).T
    table.index.name = "variable (POWER minus station)"
    period = f"{st.index.min().date()} to {st.index.max().date()}"
    md = f"""# Engine weather input vs a Tunisian ground station (NASA POWER vs DGACTA CRRA)

> **First real-data check of QATRA's inputs.** It measures how far the gridded weather the
> engine uses differs from one local station. It is **not** a validation of the engine's
> decisions, and {len(st)} days in one autumn are far too few to generalise.

- **Station:** DGACTA CRRA Sidi Bouzid ({STATION.latitude} N, {STATION.longitude} E); readings
  flagged `valid` only. Humidity, pressure and station ET0 are excluded (failed QC).
- **Grid:** NASA POWER daily point for the same coordinates (about 0.5 degree cells),
  elevation {elev:g} m, data class `inferred`. Retrieved {date.today()}.
- **Period:** {period}. **Complete station days:** {len(st)} of {candidates} days with data
  (needs >= 10 readings spanning 02:00-22:00 local, gaps <= 3 h).
- Station Tmax/Tmin come from 2-hourly samples (true extremes slightly missed); station Rs is a
  trapezoid integral of the samples; station wind assumed at 2 m; day boundaries are local
  time (POWER daily may differ by about 1 h).

## Results (bias = POWER minus station)

{table.to_markdown()}

**Seasonal-scale effect on ET0:** over these days, ET0 from POWER inputs totals
{et_power.sum():.1f} mm vs {et_hybrid.sum():.1f} mm with the station's temperature, radiation
and wind ({rel:+.1f} %). The hybrid still uses POWER dew point, so humidity error is not included.

## Daily values

{
        pd.DataFrame(
            {
                "n_station_readings": st.n,
                "tmax_station": st.tmax.round(1),
                "tmax_power": pw.tmax.round(1),
                "tmin_station": st.tmin.round(1),
                "tmin_power": pw.tmin.round(1),
                "rs_station": st.rs.round(1),
                "rs_power": pw.rs.round(1),
                "wind_station": st.wind.round(2),
                "wind_power": pw.wind.round(2),
                "et0_hybrid": et_hybrid.round(2),
                "et0_power": et_power.round(2),
            }
        ).to_markdown()
    }

## Limitations

- One station, one short autumn window, sampling every 2 hours: indicative only.
- Humidity cannot be checked (the station sensor reads 100 % throughout), and humidity is a
  major ET0 input in this climate.
- A single station is itself a point measurement with unknown maintenance and calibration.
- Re-run this script as the daily archive grows; summer data matter most for irrigation.
"""
    OUT.write_text(md, encoding="utf-8")
    print(table.to_string())
    print(
        f"ET0 total: power {et_power.sum():.1f} mm, hybrid {et_hybrid.sum():.1f} mm ({rel:+.1f} %)"
    )
    print(f"complete days {len(st)} of {candidates}; wrote {OUT}")


if __name__ == "__main__":
    main()
