# Climate 2050 scenarios: farmland west of Sidi Bouzid (35.10 N, 9.30 E)

> **Scenarios, not forecasts.** *Projected* rows apply one climate model's change signal to the
> observed baseline (delta-change); the spread across models is the message, not any single
> row. *Hypothetical* rows are stress tests chosen by hand. Farm parameters (6000 m³/ha quota,
> 3000 kWh/ha, ECw 1.5 dS/m, 1.5 m soil, planting dates) are hypothetical.

- Baseline: NASA POWER daily 1995–2014 (`inferred`). Soil: SoilGrids → Saxton–Rawls (`inferred`).
- Projections: NASA NEX-GDDP-CMIP6 (0.25°, bias-corrected), models INM-CM5-0, MRI-ESM2-0, MPI-ESM1-2-HR, EC-Earth3, CanESM5;
  SSP2-4.5 and SSP5-8.5; change = 2041–2060 vs 1995–2014, every second year sampled per window.
- Not retrieved: INM-CM5-0: INM-CM5-0/historical/tasmax/1995: not found (HTTP 404); EC-Earth3: EC-Earth3/historical/tasmax/1995: not found (HTTP 404).

## Climate change signal per scenario

| scenario                       | kind         |   et0_annual_mm |   dtmax_mean_c |   dtmin_mean_c |   precip_ratio_mean |   rs_ratio_mean |
|:-------------------------------|:-------------|----------------:|---------------:|---------------:|--------------------:|----------------:|
| baseline 1995-2014             | historical   |            1712 |         nan    |         nan    |             nan     |         nan     |
| stress test: +2 C, -20 % rain  | hypothetical |            1805 |           2    |           2    |               0.8   |           1     |
| stress test: +3 C, -30 % rain  | hypothetical |            1852 |           3    |           3    |               0.7   |           1     |
| MRI-ESM2-0 ssp245 2041-2060    | projected    |            1801 |           1.68 |           1.41 |               0.953 |           1.007 |
| MRI-ESM2-0 ssp585 2041-2060    | projected    |            1833 |           2.57 |           2.1  |               1.027 |           1.006 |
| MPI-ESM1-2-HR ssp245 2041-2060 | projected    |            1788 |           1.38 |           1.31 |               0.808 |           1.012 |
| MPI-ESM1-2-HR ssp585 2041-2060 | projected    |            1806 |           1.76 |           1.58 |               0.847 |           1.007 |
| CanESM5 ssp245 2041-2060       | projected    |            1822 |           2.32 |           2.07 |               0.92  |           1.011 |
| CanESM5 ssp585 2041-2060       | projected    |            1842 |           2.91 |           2.87 |               0.923 |           1.004 |

## Ensemble spread (projected scenarios): change in dry-year (P80) irrigation need, %

|                           |   ('irrigation_p80_m3_ha_change_pct', 'min') |   ('irrigation_p80_m3_ha_change_pct', 'median') |   ('irrigation_p80_m3_ha_change_pct', 'max') |   ('irrigation_p50_m3_ha_change_pct', 'min') |   ('irrigation_p50_m3_ha_change_pct', 'median') |   ('irrigation_p50_m3_ha_change_pct', 'max') |   ('heat_days', 'min') |   ('heat_days', 'median') |   ('heat_days', 'max') |   ('expected_relative_yield', 'min') |   ('expected_relative_yield', 'median') |   ('expected_relative_yield', 'max') |   ('models', '') |
|:--------------------------|---------------------------------------------:|------------------------------------------------:|---------------------------------------------:|---------------------------------------------:|------------------------------------------------:|---------------------------------------------:|-----------------------:|--------------------------:|-----------------------:|-------------------------------------:|----------------------------------------:|-------------------------------------:|-----------------:|
| ('ssp245', 'citrus')      |                                         13.4 |                                            13.5 |                                         15.1 |                                         10.4 |                                            11.8 |                                         16   |                   13.3 |                      17.9 |                   18.6 |                                  0.7 |                                     0.7 |                                  0.7 |                3 |
| ('ssp245', 'durum_wheat') |                                          8.6 |                                            13.6 |                                         18.7 |                                          1.6 |                                             4.1 |                                          7.3 |                    1.3 |                       1.4 |                    1.6 |                                  1   |                                     1   |                                  1   |                3 |
| ('ssp245', 'potato')      |                                          2   |                                             5.3 |                                          7   |                                          4.7 |                                             5.7 |                                          8.7 |                    8.5 |                       8.7 |                    9.1 |                                  0.9 |                                     0.9 |                                  1   |                3 |
| ('ssp245', 'tomato')      |                                          7.1 |                                             8.1 |                                          8.8 |                                          6.9 |                                             7.2 |                                          7.8 |                   33   |                      37.5 |                   38   |                                  0.5 |                                     0.5 |                                  0.5 |                3 |
| ('ssp585', 'citrus')      |                                         12.5 |                                            14.8 |                                         15.2 |                                         11.7 |                                            12.9 |                                         13.3 |                   17.3 |                      17.6 |                   18.4 |                                  0.7 |                                     0.7 |                                  0.7 |                3 |
| ('ssp585', 'durum_wheat') |                                          9.5 |                                            11.6 |                                         29.5 |                                          1   |                                             6.9 |                                         11.2 |                    1.6 |                       1.6 |                    2.2 |                                  0.9 |                                     1   |                                  1   |                3 |
| ('ssp585', 'potato')      |                                          3   |                                             5.1 |                                          9.4 |                                          5.4 |                                             7.4 |                                         13.7 |                    8.7 |                       9.6 |                    9.6 |                                  0.9 |                                     1   |                                  1   |                3 |
| ('ssp585', 'tomato')      |                                          4   |                                             7.3 |                                          8.9 |                                          5.6 |                                             6.1 |                                          9.5 |                   37.4 |                      37.5 |                   38.9 |                                  0.5 |                                     0.5 |                                  0.6 |                3 |

## All scenarios by crop

| scenario                       | kind         | crop        | overall   |   irrigation_p50_m3_ha |   irrigation_p50_m3_ha_change_pct |   irrigation_p80_m3_ha |   irrigation_p80_m3_ha_change_pct |   expected_relative_yield |   heat_days |
|:-------------------------------|:-------------|:------------|:----------|-----------------------:|----------------------------------:|-----------------------:|----------------------------------:|--------------------------:|------------:|
| baseline 1995-2014             | historical   | tomato      | S3        |                   9564 |                               0   |                  10153 |                               0   |                     0.589 |        26.8 |
| baseline 1995-2014             | historical   | potato      | S1        |                   5386 |                               0   |                   5998 |                               0   |                     1     |         5.5 |
| baseline 1995-2014             | historical   | durum_wheat | U         |                   4305 |                               0   |                   4874 |                               0   |                     1     |         0.7 |
| baseline 1995-2014             | historical   | citrus      | S2        |                   7997 |                               0   |                   8548 |                               0   |                     0.806 |         9.3 |
| stress test: +2 C, -20 % rain  | hypothetical | tomato      | S3        |                  10178 |                               6.4 |                  10866 |                               7   |                     0.54  |        36.1 |
| stress test: +2 C, -20 % rain  | hypothetical | potato      | S1        |                   5908 |                               9.7 |                   6564 |                               9.4 |                     0.909 |         9.8 |
| stress test: +2 C, -20 % rain  | hypothetical | durum_wheat | U         |                   4879 |                              13.3 |                   5880 |                              20.6 |                     1     |         2.1 |
| stress test: +2 C, -20 % rain  | hypothetical | citrus      | S3        |                   9837 |                              23   |                   9920 |                              16.1 |                     0.716 |        16.4 |
| stress test: +3 C, -30 % rain  | hypothetical | tomato      | S3        |                  10522 |                              10   |                  11092 |                               9.2 |                     0.529 |        38.7 |
| stress test: +3 C, -30 % rain  | hypothetical | potato      | S2        |                   6210 |                              15.3 |                   6762 |                              12.7 |                     0.881 |        13.9 |
| stress test: +3 C, -30 % rain  | hypothetical | durum_wheat | U         |                   5328 |                              23.8 |                   5983 |                              22.8 |                     1     |         2.8 |
| stress test: +3 C, -30 % rain  | hypothetical | citrus      | S3        |                   9845 |                              23.1 |                  10710 |                              25.3 |                     0.668 |        21.4 |
| MRI-ESM2-0 ssp245 2041-2060    | projected    | tomato      | S3        |                  10222 |                               6.9 |                  10978 |                               8.1 |                     0.534 |        38   |
| MRI-ESM2-0 ssp245 2041-2060    | projected    | potato      | S1        |                   5694 |                               5.7 |                   6318 |                               5.3 |                     0.948 |         9.1 |
| MRI-ESM2-0 ssp245 2041-2060    | projected    | durum_wheat | U         |                   4621 |                               7.3 |                   5535 |                              13.6 |                     1     |         1.3 |
| MRI-ESM2-0 ssp245 2041-2060    | projected    | citrus      | S3        |                   8827 |                              10.4 |                   9699 |                              13.5 |                     0.732 |        18.6 |
| MRI-ESM2-0 ssp585 2041-2060    | projected    | tomato      | S3        |                  10102 |                               5.6 |                  10556 |                               4   |                     0.575 |        38.9 |
| MRI-ESM2-0 ssp585 2041-2060    | projected    | potato      | S1        |                   5782 |                               7.4 |                   6301 |                               5.1 |                     0.951 |         8.7 |
| MRI-ESM2-0 ssp585 2041-2060    | projected    | durum_wheat | U         |                   4604 |                               6.9 |                   5336 |                               9.5 |                     1     |         1.6 |
| MRI-ESM2-0 ssp585 2041-2060    | projected    | citrus      | S3        |                   8930 |                              11.7 |                   9613 |                              12.5 |                     0.742 |        18.4 |
| MPI-ESM1-2-HR ssp245 2041-2060 | projected    | tomato      | S3        |                  10252 |                               7.2 |                  11044 |                               8.8 |                     0.52  |        33   |
| MPI-ESM1-2-HR ssp245 2041-2060 | projected    | potato      | S1        |                   5856 |                               8.7 |                   6416 |                               7   |                     0.932 |         8.7 |
| MPI-ESM1-2-HR ssp245 2041-2060 | projected    | durum_wheat | U         |                   4482 |                               4.1 |                   5787 |                              18.7 |                     1     |         1.4 |
| MPI-ESM1-2-HR ssp245 2041-2060 | projected    | citrus      | S3        |                   9273 |                              16   |                   9838 |                              15.1 |                     0.72  |        13.3 |
| MPI-ESM1-2-HR ssp585 2041-2060 | projected    | tomato      | S3        |                  10472 |                               9.5 |                  11059 |                               8.9 |                     0.526 |        37.4 |
| MPI-ESM1-2-HR ssp585 2041-2060 | projected    | potato      | S1        |                   6125 |                              13.7 |                   6559 |                               9.4 |                     0.91  |         9.6 |
| MPI-ESM1-2-HR ssp585 2041-2060 | projected    | durum_wheat | U         |                   4788 |                              11.2 |                   6312 |                              29.5 |                     0.948 |         1.6 |
| MPI-ESM1-2-HR ssp585 2041-2060 | projected    | citrus      | S3        |                   9060 |                              13.3 |                   9850 |                              15.2 |                     0.722 |        17.3 |
| CanESM5 ssp245 2041-2060       | projected    | tomato      | S3        |                  10306 |                               7.8 |                  10873 |                               7.1 |                     0.542 |        37.5 |
| CanESM5 ssp245 2041-2060       | projected    | potato      | S1        |                   5640 |                               4.7 |                   6117 |                               2   |                     0.981 |         8.5 |
| CanESM5 ssp245 2041-2060       | projected    | durum_wheat | U         |                   4372 |                               1.6 |                   5295 |                               8.6 |                     1     |         1.6 |
| CanESM5 ssp245 2041-2060       | projected    | citrus      | S3        |                   8939 |                              11.8 |                   9696 |                              13.4 |                     0.735 |        17.9 |
| CanESM5 ssp585 2041-2060       | projected    | tomato      | S3        |                  10151 |                               6.1 |                  10892 |                               7.3 |                     0.541 |        37.5 |
| CanESM5 ssp585 2041-2060       | projected    | potato      | S1        |                   5678 |                               5.4 |                   6178 |                               3   |                     0.971 |         9.6 |
| CanESM5 ssp585 2041-2060       | projected    | durum_wheat | U         |                   4350 |                               1   |                   5440 |                              11.6 |                     1     |         2.2 |
| CanESM5 ssp585 2041-2060       | projected    | citrus      | S3        |                   9026 |                              12.9 |                   9809 |                              14.8 |                     0.73  |        17.6 |

## Limitations

- Delta-change keeps the baseline's daily sequence: changes in variability, dry-spell length and extremes beyond a shift of the distribution are not represented.
- Relative humidity and wind are held at baseline values.
- Crop calendars, varieties and CO2 effects on crop water use are not adapted.
- Crop parameters are literature values (needs_review); heat/frost thresholds are unverified placeholders.
- Every second year sampled per 20-year window to limit download volume.
- Groundwater response is not simulated (aquifer parameters are not available).

## Findings (written after reviewing the results)

- Only 3 of the 5 selected models were retrieved: NEX-GDDP-CMIP6 returned "not found" for the
  1995–2014 historical files of INM-CM5-0 and EC-Earth3. The ensemble is narrow, and the
  coolest selected model is the one missing; read the spread as indicative only.
- Warming of +1.4 to +2.9 °C in mean maximum temperature (2041–2060 vs 1995–2014); rainfall
  change from −19 % to +3 % depending on the model. Annual ET0 rises 4–8 % (1712 → 1788–1842 mm).
- At an unchanged quota of 6000 m³/ha, citrus is the most exposed of the four crops: its
  dry-year irrigation need rises 13–15 % in every projection, which moves it from S2 to S3.
  Durum wheat shows the widest spread (+9 % to +30 %) because the models disagree most on
  winter rainfall. Tomato (+4 % to +9 %) and potato (+2 % to +9 %) change less.
- Tomato heat days rise from about 27 to 38 per season, but this rests on an unverified
  placeholder threshold (35 °C) and is a provisional warning only.
