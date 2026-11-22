# Engine weather input vs a Tunisian ground station (NASA POWER vs DGACTA CRRA)

> **First real-data check of QATRA's inputs.** It measures how far the gridded weather the
> engine uses differs from one local station. It is **not** a validation of the engine's
> decisions, and 13 days in one autumn are far too few to generalise.

- **Station:** DGACTA CRRA Sidi Bouzid (35.684 N, 9.479 E); readings
  flagged `valid` only. Humidity, pressure and station ET0 are excluded (failed QC).
- **Grid:** NASA POWER daily point for the same coordinates (about 0.5 degree cells),
  elevation 529.51 m, data class `inferred`. Retrieved 2026-11-22.
- **Period:** 2026-10-24 to 2026-11-09. **Complete station days:** 13 of 19 days with data
  (needs >= 10 readings spanning 02:00-22:00 local, gaps <= 3 h).
- Station Tmax/Tmin come from 2-hourly samples (true extremes slightly missed); station Rs is a
  trapezoid integral of the samples; station wind assumed at 2 m; day boundaries are local
  time (POWER daily may differ by about 1 h).

## Results (bias = POWER minus station)

| variable (POWER minus station)   |   days |   station_mean |   power_mean |   bias |   mae |   rmse |    r |
|:---------------------------------|-------:|---------------:|-------------:|-------:|------:|-------:|-----:|
| Tmax (degC)                      |     13 |          22.32 |        21.93 |  -0.4  |  0.67 |   0.9  | 0.9  |
| Tmin (degC)                      |     13 |          13.33 |        11.76 |  -1.57 |  1.75 |   1.92 | 0.81 |
| Solar radiation Rs (MJ/m2/day)   |     13 |          10.68 |        11.7  |   1.02 |  2.15 |   2.57 | 0.64 |
| Wind at 2 m (m/s)                |     13 |           1.72 |         1.92 |   0.2  |  0.52 |   0.65 | 0.74 |
| ET0 Penman-Monteith (mm/day)     |     13 |           2.52 |         2.54 |   0.01 |  0.37 |   0.45 | 0.62 |

**Seasonal-scale effect on ET0:** over these days, ET0 from POWER inputs totals
33.0 mm vs 32.8 mm with the station's temperature, radiation
and wind (+0.5 %). The hybrid still uses POWER dew point, so humidity error is not included.

## Daily values

| date                |   n_station_readings |   tmax_station |   tmax_power |   tmin_station |   tmin_power |   rs_station |   rs_power |   wind_station |   wind_power |   et0_hybrid |   et0_power |
|:--------------------|---------------------:|---------------:|-------------:|---------------:|-------------:|-------------:|-----------:|---------------:|-------------:|-------------:|------------:|
| 2026-10-24 00:00:00 |                   12 |           24   |         23.2 |           16.6 |         14.5 |          7.6 |       13.3 |           1.34 |         2.84 |         2.35 |        3.34 |
| 2026-10-26 00:00:00 |                   13 |           24.9 |         22.9 |           14.2 |         11.7 |         15.6 |       14.2 |           2.22 |         2.62 |         3.3  |        2.93 |
| 2026-10-30 00:00:00 |                   18 |           23.7 |         21.9 |           14.1 |         11.8 |          9.3 |       12.9 |           0.88 |         1.01 |         1.93 |        2.02 |
| 2026-10-31 00:00:00 |                   12 |           21.3 |         20.7 |           13.2 |         10.4 |         14.8 |       11.2 |           0.99 |         0.9  |         2.18 |        1.81 |
| 2026-11-01 00:00:00 |                   13 |           20.9 |         20.6 |           11.5 |          9.4 |         12.1 |       12.9 |           1.3  |         2.06 |         2.19 |        2.5  |
| 2026-11-02 00:00:00 |                   15 |           19.1 |         18   |           13.1 |         10.9 |          9.1 |       11.5 |           3.31 |         3.92 |         3.22 |        3.13 |
| 2026-11-03 00:00:00 |                   13 |           20.1 |         19.8 |           10.7 |          7.9 |         13.8 |       14.4 |           2.06 |         1.86 |         2.89 |        2.62 |
| 2026-11-04 00:00:00 |                   13 |           20.6 |         21.4 |           11.3 |         10.4 |          5.3 |        6.7 |           1.54 |         2.18 |         2.25 |        2.8  |
| 2026-11-05 00:00:00 |                   12 |           21.8 |         22   |           14.8 |         13.1 |          6.4 |        8.1 |           1.48 |         1.73 |         2.19 |        2.35 |
| 2026-11-06 00:00:00 |                   14 |           23.5 |         23.4 |           12.3 |         12.1 |          9.9 |       11.4 |           1.08 |         0.9  |         2.03 |        1.95 |
| 2026-11-07 00:00:00 |                   13 |           23   |         23.4 |           14   |         12.9 |         11.6 |        9.3 |           1.95 |         0.97 |         2.71 |        1.92 |
| 2026-11-08 00:00:00 |                   15 |           22.4 |         22.5 |           15.4 |         14.5 |         10.3 |       13   |           1.69 |         1.08 |         2.39 |        2.09 |
| 2026-11-09 00:00:00 |                   13 |           24.9 |         25.3 |           12.1 |         13.2 |         13   |       13.2 |           2.47 |         2.86 |         3.17 |        3.55 |

## Limitations

- One station, one short autumn window, sampling every 2 hours: indicative only.
- Humidity cannot be checked (the station sensor reads 100 % throughout), and humidity is a
  major ET0 input in this climate.
- A single station is itself a point measurement with unknown maintenance and calibration.
- Re-run this script as the daily archive grows; summer data matter most for irrigation.
