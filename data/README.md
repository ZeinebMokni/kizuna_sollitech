# QATRA data store

| Folder | Holds | Data classes allowed |
|---|---|---|
| [raw/](raw/) | Downloaded files, unchanged, with a manifest each | all except simulated |
| [external/](external/) | Third-party reference data (statistics, soil maps, projections) | official, inferred, remote_sensed, projected, measured |
| [processed/](processed/) | Real observations in the standard schema | measured, official, farmer_reported, remote_sensed, inferred |
| [sensors/](sensors/) | Farm sensor readings and farmer logs | measured, farmer_reported |
| [synthetic/](synthetic/) | Simulated data only | simulated |

The rules are enforced in code (`ai_engine/qatra_ai/data/store.py`), not by convention: writing a simulated row outside `synthetic/`, or a real row into it, raises an error.

**Git:** only READMEs, `*.manifest.json` and `*.meta.json` are tracked. Data files stay local. Set `QATRA_DATA_DIR` to put the store elsewhere.

## Observation schema (long format, CSV, one row per value)

| Column | Meaning |
|---|---|
| `timestamp_utc` | ISO-8601 UTC, e.g. `2026-10-23T10:00:00Z` |
| `site_id` | Station or farm site |
| `variable` | Standard variable name, e.g. `air_temperature`, `soil_vwc_10cm` |
| `value` | The value **as published** (empty only when `qc_flag` is `missing`) |
| `unit` | Unit of `value` |
| `source` | Source id, matching the `raw/<source>/` folder |
| `data_class` | measured, official, farmer_reported, remote_sensed, inferred, projected, simulated |
| `qc_flag` | unchecked, valid, suspect, invalid, missing, gap_filled |
| `raw_file_sha256` | Hash of the raw file the row came from (required except in `synthetic/`) |

No two rows may share `timestamp_utc, site_id, variable, source`. Each CSV has a `.meta.json` summary: row count, time span, variables, QC counts and the raw files used.

## Licences

Each manifest records the licence of its file. Attribution is required for the Tunisian open-data licence (Licence Nationale de Données Publiques Ouvertes), SoilGrids (CC BY 4.0), FAOSTAT (CC BY 4.0) and PVGIS.

## Sources archived so far

| Source | Folder | How to update | Notes |
|---|---|---|---|
| DGACTA stations, Sidi Bouzid (CRRA, El Ayoun, Rayhana) | `raw/dgacta_sidi_bouzid/` → `processed/dgacta_sidi_bouzid/<station>.csv` | `cd ai_engine && uv run python -m qatra_ai.data.sources.dgacta` | Run once a day: the catalogue only publishes a short rolling window. Each run logs to `raw/dgacta_sidi_bouzid/runs.jsonl`. Quality findings: [docs/data/dgacta_sidi_bouzid_quality.md](../docs/data/dgacta_sidi_bouzid_quality.md) |
