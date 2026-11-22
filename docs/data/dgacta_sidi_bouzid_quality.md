# DGACTA Sidi Bouzid stations: what the published data contains

First archive run: 2026-11-22. Source: catalog.agridata.tn, Licence Nationale de Données Publiques Ouvertes. Produced by `qatra_ai.data.sources.dgacta`, from files stored unchanged in `data/raw/dgacta_sidi_bouzid/`.

**In short:** the three stations publish about 15 days of usable data in total. At the main station (CRRA), the humidity and pressure sensors failed for the whole period, so the station's own ET0 cannot be trusted. None of this is enough to train or validate a model. Its value is in archiving it every day from now on.

## Coverage

| Station | Files | Rows | Period (UTC) | Last catalogue update |
|---|---|---|---|---|
| CRRA (`sb_crra`) | 8 (environment, rain, soil 10/20/30 cm; old and new soil uploads) | 3,357 | Soil: 2026-06-15 to 06-24, and 2026-10-22 to 11-10. Weather: 2026-10-22 to 11-10 | 2026-11-22 (content unchanged since 2026-11-10) |
| El Ayoun (`sb_el_ayoun`) | 5 | 117 | 2025-12-18 23:00 to 12-19 06:00 (6 h) | 2026-01-18 |
| Rayhana (`sb_rayhana`) | 5 | 210 | 2026-06-12 23:00 to 06-13 08:00 (10 h) | 2026-07-13 |

The catalogue says readings are taken every 15 minutes. The files contain mostly 2-hourly readings, with gaps of up to 21 hours.

## Quality findings

Values are kept as published. Flags only mark them.

| Station | Variable | Flag | Why |
|---|---|---|---|
| CRRA | Air pressure | invalid, all 249 readings | Exactly 0 hPa throughout |
| CRRA | Relative humidity | suspect, all 249 | Exactly 100 % throughout (a stuck sensor) |
| CRRA | Dew point | suspect, all 249 | Equals air temperature, as expected when derived from a stuck 100 % humidity |
| CRRA | Hourly ET0 | suspect, all 249 | Always 0, including 62 readings in sunshine of 200 W/m² or more |
| CRRA | Daily ET0 | suspect, all 249 | Computed by the station from the failed humidity and pressure readings |
| CRRA | Soil water content, 10/20/30 cm | 206 invalid, 188 suspect | Negative values (−2.0 to −2.1 %); otherwise unchanged for 72 hours or more |
| El Ayoun, Rayhana | Air pressure | suspect | Plausible values (959–988) but labelled "mm/j" instead of hPa |
| El Ayoun, Rayhana | Station ET0 | suspect | Uses the mislabelled pressure. At Rayhana, hourly ET0 is about 1 mm/h at night with no sunlight |

**Readings that pass:**

- At CRRA: air temperature, wind speed and direction, solar radiation, rain, soil temperature, and most of the raw soil-moisture signal (mV).
- At El Ayoun and Rayhana: everything except pressure and station ET0.

## What this means for QATRA

- **ET0 cross-check (plan step 3):** the CRRA station ET0 cannot serve as a reference, because its humidity input has failed. Comparing it with QATRA's FAO-56 ET0 would test nothing, so step 3 is on hold until a period with working humidity is archived.
- **Soil moisture:** the water-content channel has no usable calibrated values at CRRA. The raw mV signal responds to wetting, but without a calibration curve it cannot be converted to water content. A calibration curve from DGACTA would make it usable.
- **Training:** nothing here supports model training. History has to be built by archiving every day.
- **Time zone:** time stamps are read as Tunisian local time (UTC+1). This is inferred from when solar radiation peaks (about 12:10 clock time). Whether a time stamp marks the start or the end of its interval is unknown (±1 h).

## Suggested questions for DGACTA

1. Is a longer archive available (full 15-minute data since installation)?
2. Are the CRRA humidity and pressure sensors known to be faulty, and since when?
3. Which soil-moisture probe model is used, and is there a calibration from mV to water content?
4. Are the time stamps local time, and do they mark the start or the end of the interval?
5. How is the station ET0 computed (method and inputs)?

## Automated operations

`scripts/dgacta_archive.py` is the daily archiving entry point. It:

- discovers catalogue resources on every run;
- stores unchanged response bytes and SHA-256 manifests;
- rebuilds processed tables and QC flags;
- avoids duplicate raw files with content-addressed storage;
- detects observations older than 72 hours and prints an alert;
- exits non-zero when the catalogue or downloads fail.

The command is intentionally not a machine-learning pipeline. No DGACTA reading is suitable
for model training until a sustained, calibrated and validated history exists.
