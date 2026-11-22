# QATRA repository audit and real-data acquisition plan

Date: 2026-11-22 · Branch `ai-engine` · Phase 1 of the "research prototype to real-data platform" plan.

This audit changed no code. Every data-source status below comes from a live request made on 2026-11-21/22, not from documentation.

**In short:**

- **What works:** the decision engine and dashboard work end to end, but only on public weather and soil data plus a hypothetical farm.
- **What is missing:** QATRA has no machine-learning model and no farm or sensor data. No real field observation has been used anywhere.
- **Tunisian open data:** it exists and can be reached, but the station feeds are short rolling snapshots of uneven quality. They have to be archived on a schedule before they are worth anything.

---

## 1. Existing functionality

### Decision engine (`ai_engine/qatra_ai`, about 7,700 lines of Python, 177 tests passing)

| Area | Module | What it does | Evidence level |
|---|---|---|---|
| Reference ET0 | `agronomy/et0`, `daily_et0` | FAO-56 Penman–Monteith, plus Hargreaves as a fallback | Reproduces the FAO-56 worked examples |
| Crop demand | `agronomy/crops`, `kc`, `reference_data/crops/*.yaml` | Single Kc curve with climate adjustment for 6 crops | Literature values. Heat/frost thresholds are marked `verified: false` |
| Soil | `agronomy/soil` | Saxton & Rawls pedotransfer, TAW/RAW | Literature. Loam WP check is open (13.7 vs 12, TODO) |
| Water balance | `agronomy/water_balance` | Daily root-zone balance, Ks, Kalman assimilation of soil sensors | Unit tests only. Never run on real sensors |
| Yield and salinity | `agronomy/yield_response` | FAO-33 Ky, FAO-29 salinity | Literature |
| Energy | `energy` | Pump power, solar and battery limits | Unit tests |
| Data readers | `data/sources/{nasa_power, open_meteo, soilgrids, nex_gddp}`, `data/qc` | Weather, soil and CMIP6 downloads, range/step QC | Run live |
| Scheduler | `optimization/irrigation_scheduler` | 72-hour multi-zone MILP (OR-Tools SCIP), shadow prices, independent `verify_plan` | Closed-loop simulation, March–August 2025 |
| Allocation | `optimization/allocation` | 6 aquifer-sharing strategies (GLOP LP), fairness metrics | Synthetic only |
| Anomalies | `predictive/anomaly` | 8 rule/statistical detectors, split CUSUM, adaptive thresholds | Synthetic benchmark only |
| Suitability | `suitability/engine` | FAO limiting-factor rating, Pareto ranking | Real weather for 2015–2024. Thresholds are provisional |
| Climate | `climate/scenarios` | Delta-change from NEX-GDDP-CMIP6 | 3 of 5 models (2 historical files return 404) |
| Orchestrator | `orchestrator/decision` | Lexicographic tiers 0–3. Every water action needs human approval | Tests plus a replay demo |
| Assistant | `assistant/*` | Claude or Gemini with read-only tools and a deterministic grounding verifier | Offline tests. A live Gemini run is still pending |
| Service | `service/app` | Read-only FastAPI on port 8100 | Used by the dashboard |

The shared contract, `contracts.EngineEnvelope`, already carries `DataClass` provenance (measured / inferred / synthetic and so on), `ValidationStatus`, `Confidence` and `inputs_hash`. That is the right foundation for keeping real and synthetic data apart, so the new data layer should reuse it rather than invent a parallel one.

### Dashboard (`frontend/`, Next.js 16, about 1,400 lines)

Eight pages: overview, decisions, schedule, water balance, crops, climate, anomalies, assistant. All text is in English. The farm is the hypothetical demo farm from `service/demo_farm`.

### Platform backend (`backend/`, 868 lines)

Paused scaffold (auth, farms, PostGIS). It has no migrations and cannot run.

---

## 2. Existing data sources (in the code today)

| Source | Used for | Data class | Licence |
|---|---|---|---|
| NASA POWER (daily) | Weather 1995–2025, ET0 inputs | Measured/reanalysis (gridded, 0.5°) | Free, attribution |
| SoilGrids 250 m | Sand/silt/clay, SOC → soil water properties | Inferred (model) | CC BY 4.0 |
| NASA NEX-GDDP-CMIP6 | Climate deltas 2041–2060 | Model projection | Per-model CMIP6 terms |
| Open-Meteo | Optional forecast reader | Model forecast | Free tier is **non-commercial only** |
| Demo farm | Zones, crops, pump, quotas, past irrigation | **Hypothetical** | n/a |
| Synthetic generators | Anomaly and water-use benchmarks | **Synthetic** | n/a |

Nothing in the repository is a farm measurement.

---

## 3. Tunisian and global real-data catalogue (probed live)

| # | Source | Access tested | Result | Content relevant to QATRA | Licence / condition | Verdict |
|---|---|---|---|---|---|---|
| 1 | **DGACTA agro-weather stations**, Sidi Bouzid (CRRA, El Ayoun, Rayhana), on `catalog.agridata.tn` | CSV download | ✅ Works with TLS verification on (TunTrust CA via `truststore`) | Hourly RH, dew point, solar radiation, pressure, wind, temperature, **station ET0**; soil moisture and temperature at 10/20/30 cm | Licence Nationale de Données Publiques Ouvertes | **Highest value, but see quality notes below** |
| 2 | **Tunisia open-data portal** `catalog.data.gov.tn` (CKAN API) | `package_search` | ✅ Works | Sidi Bouzid: 38 datasets. Nationally: about 62 rainfall, 45 irrigation and 62 aquifer ("nappe") datasets, mostly XLSX from the Ministry of Agriculture | Same national open licence | Good for regional statistics, aquifer levels and irrigated areas. Not farm-level |
| 3 | **PVGIS 5.3** (JRC) | `PVcalc` and `seriescalc` hourly | ✅ Works (SARAH3 + ERA5) | Hourly solar irradiance at the farm, so the solar pump limit is no longer assumed | Free, attribution | Replace the assumed solar profile |
| 4 | **SoilGrids** extra properties | phh2o, bdod, silt | ✅ Works | pH and bulk density in addition to texture | CC BY 4.0 | Extend the soil reader |
| 5 | **FAOSTAT bulk** | Africa crops zip (4.3 MB) | ✅ Works (the REST API returns 401 without login) | Tunisian yields, areas, production by crop and year | CC BY 4.0 (FAO) | Use the bulk file, not the API |
| 6 | **FAO Crop Calendar API** | `/api/v1/countries` | ✅ Works | Planting and harvest windows by country and crop | FAO terms | Check the demo planting dates; give it to the agronomist reviewer |
| 7 | **Copernicus Data Space** (Sentinel-2) | OData search | ✅ Search works anonymously. The STAC collection name probed was wrong (404). **Download needs a free account** | NDVI / canopy cover per zone | Free, Copernicus licence | Later phase. Needs an account (user action) |
| 8 | **Open-Meteo** | Forecast | ✅ Works now, with daily 429s seen on 2026-11-21 | 7–16 day forecast for a live mode | Non-commercial on the free tier | Fine for research. A commercial use needs a paid plan or another provider |
| 9 | ONAGRI | HTML pages | Reachable, no API | Market and production bulletins | Site terms | Manual reference only |
| 10 | FAOSTAT REST API | JSON | ❌ 401 | n/a | Needs login | Use #5 instead |
| 11 | NEX-GDDP INM-CM5-0, EC-Earth3 historical | NetCDF | ❌ 404 | n/a | n/a | Report as a gap; try another mirror (e.g. the AWS open-data bucket) later |

### Quality of the DGACTA station files (downloaded and inspected)

- **Format:** a long table (`Date, nom_ar, nom_fr, unite, valeur`) with dates as `YYYY-MM-DD HH:MM:SS`. It is easy to standardise.
- **CRRA weather:**
  - covers 2026-10-23 to 2026-11-10, which is 249 distinct hours over 9 variables;
  - the latest value is about 12 days behind today;
  - invalid values include pressure of 0 hPa, and stretches of RH at 100 % with dew point equal to air temperature (a stuck or saturated sensor).
- **CRRA soil:**
  - only 270 rows, from 2026-06-15 to 2026-06-24;
  - volumetric water content reads **−2.0 %**, which is physically impossible: the sensor is uncalibrated or disconnected;
  - the other channels are raw mV readings and soil temperature.
- **El Ayoun and Rayhana:** only a few hours each.
- **Conclusion:** each published file is a **short rolling window**, not a history. It cannot train or validate anything today. It becomes useful only if QATRA **downloads it on a schedule and archives every version** with provenance, then QCs it.
  - Station ET0 is the most immediately useful variable: comparing it with QATRA's FAO-56 ET0 computed from the same station's hourly inputs is a legitimate check of the ET0 code on Tunisian data.
  - Even so, it is a code-consistency check, not field validation.

---

## 4. Missing datasets

Ranked by how much each would change QATRA's credibility.

| Missing | Why it matters | Legitimate route |
|---|---|---|
| Farm soil-moisture time series (one season, calibrated) | The water balance and Kalman assimilation have never seen a real sensor | A pilot farm with 2–3 calibrated probes per zone. No public substitute exists |
| Farm inlet flow and pump status | Anomaly detection has only seen synthetic faults | A pilot farm meter with a logger (pulse output). The sensor API in Phase 5 will receive it |
| Irrigation logs (date, zone, volume) | Needed to replay real decisions | Farmer notebook, entered through a CSV template |
| Yields per zone | The only real check of Ky/yield response | Harvest weights from the pilot farm; FAOSTAT and the regional statistics give context only |
| Local crop parameters (Kc stages, heat/frost thresholds, Ky for olive and date palm) | Placeholders today | Agronomist review (methodology document already written); FAO crop calendar |
| Groundwater level and salinity at the farm well | Salinity and well-yield limits are assumed | Farm well measurements; CKAN aquifer XLSX gives the regional trend |
| Long station history (years, not days) | Training any weather or ET0 model | Ask DGACTA/CRDA for the archive (a formal request); meanwhile archive the feed ourselves |
| Satellite canopy (NDVI) per zone | Kc from observation instead of from the calendar | Copernicus account (free), Phase 4+ |

**Nothing in this table will be replaced by generated data.** Where a dataset is missing, the related feature stays labelled "literature-parameterised" or "training pending".

---

## 5. Existing ML models

**None.**

- `predictive/` contains only the rule and statistical anomaly detectors.
- No scikit-learn, LightGBM, PyTorch or similar library is installed.
- The "AI" in QATRA today is physics (FAO-56), optimisation (MILP/LP), statistics (CUSUM) and an LLM explainer.

The master prompt lists models A–D. None can be trained honestly yet:

| Model | Needs | Earliest realistic data |
|---|---|---|
| A. ET0 / weather gap-filling | Months of archived station data plus NASA POWER | After about 3–6 months of scheduled archiving |
| B. Soil-moisture forecasting | One season of pilot-farm sensors | After a pilot season |
| C. Anomaly classifier (supervised) | Labelled real faults | After a pilot season, plus incident labels |
| D. Yield estimation | Multiple seasons × zones of yields | Years. Regional FAOSTAT only gives context |

What can be built now is the pipeline: data loading, features, splits, a training script and a model card. It should refuse to train, or report "insufficient data, training pending", until a minimum volume of `DataClass.MEASURED` rows exists. It must never be run on synthetic data and reported as a result.

---

## 6. Components requiring improvement

| Item | Where | Why |
|---|---|---|
| Day-parameter logic duplicated in 4 places | `agronomy/water_balance`, `evaluation/closed_loop`, `optimization/inputs`, `suitability/engine` | Divergence risk when real data adds new inputs. Refactor into one helper, with the tests unchanged |
| Frontend hard-codes zone and crop names | `frontend/src` (ZONE_NAME / CROP_NAME) | Breaks as soon as a real farm has different zones. Read them from `/api/farm` |
| No `data/` layer | repository root | Needs `data/raw/`, `processed/`, `external/`, `sensors/`, `synthetic/` and a standard long-format schema with provenance |
| No sensor ingestion | `service/app` is read-only | Needs `POST /api/v1/sensors/measurements` with validation, QC flags and idempotency |
| Gemini retry/fallback fix uncommitted | `assistant/backends.py`, `tests/test_assistant_gemini.py` | Tested; waiting for your OK to commit |
| `.env.example` holds a real-looking JWT secret | root | Must go back to a placeholder before any commit touches it |
| Open-Meteo reader not fully verified live | `data/sources/open_meteo` | Blocked by the daily 429 limit on 2026-11-21 |
| Saxton loam WP mismatch | `agronomy/soil` tests | Check against the original paper's table |
| Dashboard in English only | `frontend` | ar/fr/en planned for Phase 6 |
| Backend has no migrations | `backend/` | Only needed when the platform resumes |

---

## 7. Risks and dependencies

- **The station feed may disappear or change format.**
  - Archive raw files byte-for-byte with SHA-256 hashes, and parse defensively.
  - Alert when the schema changes.
- **Station data quality:** the zero pressure, saturated RH and −2 % VWC above show the need for QC flags on every value. Bad values are kept and flagged, never silently fixed.
- **TLS:** `catalog.agridata.tn` uses a TunTrust chain that Python's bundled certifi does not include.
  - Use `truststore` (the OS store) with verification **on**. Never disable verification.
  - This works on Windows; it must be checked on any Linux server.
- **Licences:**
  - Open-Meteo's free tier is non-commercial.
  - The Copernicus download needs an account (your action).
  - FAOSTAT is CC BY with attribution.
  - The Tunisian open licence requires attribution.
- **Quotas:** Open-Meteo returns 429 when the daily limit is hit. Cache everything and stagger requests.
- **Field data depends on people:** a pilot farm, an agronomist, and a DGACTA/CRDA archive request. No amount of code replaces these.
- **Misrepresentation risk:** backtesting, replay and synthetic benchmarks must keep their labels. The validation framework (Phase 8) will label them "historical backtest" or "simulation", never "field validation".

---

## 8. Implemented trustworthy-data milestone

The next milestone adds reliable operations around the existing physics and optimisation
engine, rather than training models:

- DGACTA snapshots are archived unchanged with SHA-256 manifests and rebuild processed
  observations with quality flags.
- A station-selection service evaluates every variable independently. It rejects invalid,
  missing and suspect readings, checks freshness, calculates geographic distance and records
  the selected station/source. It never chooses a source by distance alone.
- The data-fusion service keeps measured, inferred, projected and synthetic classes separate.
  A model estimate is returned only as an explicit fallback and is never presented as a physical
  measurement.
- Sensor and irrigation CSV imports validate timestamps, units, zones and duplicate keys.
- PVGIS exposes hourly estimated solar production separately from the existing assumed profile.
- The API and dashboard can list and select farms, while legacy routes remain for compatibility.

## 9. Recommended implementation sequence

Each step is small, keeps the existing tests green, and adds its own tests.

1. **Data layer foundation** (no new sources yet)
   - Create `data/{raw, processed, external, sensors, synthetic}` with a README per folder. Git-ignore the bulk data; keep only manifests.
   - Define a long-format observation schema: `timestamp_utc, site_id, variable, value, unit, source, data_class, qc_flag, raw_file_sha256`.
   - Add a manifest per downloaded file: URL, retrieval time, licence, hash.
2. **DGACTA station archiver**
   - Fetch the three Sidi Bouzid stations, store raw files unchanged, parse them to the schema, and apply QC flags (range, stuck value, RH/dew-point consistency, impossible VWC).
   - Run it on a schedule, daily, to build history going forward.
3. **ET0 cross-check on station data:** compute FAO-56 ET0 from the station's hourly inputs and compare it with the station's own ET0. Report it as a code-consistency check.
4. **PVGIS hourly solar** for the farm location, replacing the assumed solar profile in the scheduler inputs.
5. **Static reference ingestion:** SoilGrids extra properties, FAOSTAT Tunisia crop statistics (bulk), the FAO crop calendar, and the CKAN Sidi Bouzid XLSX (rainfall, irrigation, aquifer), each with a manifest and licence.
6. **Refactors from §6:** a single day-parameter helper, and frontend names read from the API.
7. **Sensor ingestion API:** `POST /api/v1/sensors/measurements` into `data/sensors/`, with a schema, QC, an API key loaded from the environment, and a CSV import path for farmer logs.
8. **ML pipelines A–D**
   - Build the loaders, features, time-based splits, training scripts and model cards.
   - Each one checks the measured-data volume first and reports "training pending" until the threshold is met.
9. **Decision-engine integration:** use measured data where it exists, fall back to the current sources otherwise, and show the data class of every input on the dashboard.
10. **Dashboard:** data-provenance badges, a station data page, and ar/fr/en.
11. **Validation framework:** separate reports for code checks, historical backtests, simulations and (later) field validation, each with its own label.

**Steps needing your action, which can start in parallel:**

- find one pilot farm (soil-moisture probes, an inlet flow meter, pump status);
- send the methodology document to an agronomist;
- send a formal request to DGACTA/CRDA Sidi Bouzid for station history;
- create a Copernicus Data Space account (only needed for satellite data later).
