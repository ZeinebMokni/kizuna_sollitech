# QATRA: Agronomic Methodology and Review Request

*Version 0.1, 21 November 2026. Prepared for agronomists and research partners reviewing the QATRA engine.*

## 1. Purpose of this document

QATRA is decision-support software for irrigated farms in Tunisia that pump their own water. Its central question is: **when water, energy and information are scarce, where should we intervene first to prevent the most irreversible damage?**

This document explains:
- what QATRA computes;
- which published methods it relies on;
- which parameters it currently uses;
- **exactly what we are asking you to verify.**

Nothing in QATRA has yet been validated against field data from Tunisia. Every value marked *placeholder* or *needs review* below is a request for your expertise.

## 2. Validation status

| Component | Method | Status | Evidence so far |
|---|---|---|---|
| Reference evapotranspiration (ET0) | FAO‑56 Penman–Monteith | Reproduces FAO‑56 worked examples | Automated tests against Examples 2–3, 8 and 18 of FAO‑56 |
| Crop water requirement and soil water balance | FAO‑56 single Kc, daily root-zone balance | Literature-parameterised | Mass balance checked daily; no field comparison yet |
| Soil water-holding capacity | Saxton & Rawls (2006) pedotransfer from SoilGrids texture | Literature-parameterised | One reference value to confirm (see §8) |
| Yield response to water and salinity | FAO‑33 (Ky), FAO‑29 | Literature-parameterised | Not compared with Tunisian yields |
| Irrigation scheduling across zones | Mixed-integer optimisation | Simulation-tested | Full-season simulation on real 2025 weather, hypothetical farm |
| Leak and anomaly detection | Rule-based and statistical | Simulation-tested | Synthetic faults only; no real incidents yet |
| Crop suitability | FAO land-evaluation limiting-factor method | Literature-parameterised | Results compared informally with known regional cropping |
| Climate scenarios | Delta-change on CMIP6 models | Method implemented | Scenarios, not forecasts |

The status levels are: *literature-parameterised* → *simulation-tested* → *pilot-validated* → *field-validated*. No component has reached the last two.

## 3. Data sources

| Data | Source | Resolution | Classed as |
|---|---|---|---|
| Daily weather (baseline, history) | NASA POWER; Open-Meteo (ERA5 reanalysis) | ~50 km; ~10–25 km | Inferred (model/reanalysis, not station measurements) |
| Soil texture and organic carbon | ISRIC SoilGrids 2.0 | 250 m | Inferred (machine-learning prediction) |
| Climate projections | NASA NEX-GDDP-CMIP6 (bias-corrected, downscaled) | 0.25° | Projected |
| Crop parameters | FAO‑56, FAO‑33, FAO‑29 | Reference tables | Literature, not locally calibrated |

Farm-level measurements (soil-moisture sensors, flow meters, laboratory soil analyses) replace these estimates when available. QATRA labels every value as measured, inferred, simulated or projected, and lowers its confidence accordingly.

## 4. Agronomic methods

### 4.1 Reference evapotranspiration

ET0 is computed daily with the FAO‑56 Penman–Monteith equation (Allen et al., 1998, Eq. 6) from minimum and maximum temperature, humidity, solar radiation and wind.
- When only temperature is available, Hargreaves–Samani (FAO‑56 Eq. 52) is used, and the result is flagged as lower confidence.
- Where minimum relative humidity is missing, it is estimated from dew point and maximum temperature for the Kc climate adjustment.

### 4.2 Crop evapotranspiration

ETc = Kc × ET0, using the FAO‑56 single-coefficient curve:
- constant Kc_ini during the initial stage;
- a linear rise to Kc_mid during development;
- constant Kc_mid at mid-season;
- a linear decline to Kc_end during the late stage.

Kc_mid and Kc_end are adjusted for local wind and minimum humidity (FAO‑56 Eq. 62). Under water stress, ETa = Ks × Kc × ET0.

### 4.3 Soil water balance

Root-zone depletion Dr is tracked daily (FAO‑56 Eq. 85):

- Total available water: TAW = 1000 (θFC − θWP) × Zr.
- Readily available water: RAW = p × TAW, with p adjusted for evaporative demand (FAO‑56 Table 22 footnote).
- Stress coefficient: Ks = (TAW − Dr) / ((1 − p) TAW) when Dr > RAW; otherwise Ks = 1.
- Root depth Zr grows linearly in annual crops until the start of mid-season. In perennials it is constant.

Simplifying assumptions:
- Runoff and capillary rise are zero.
- Rain below 0.2 × ET0 is treated as evaporated.
- Water above field capacity drains the same day.

When a **calibrated** soil-moisture sensor is available, the estimate is corrected towards the sensor reading, weighted by the uncertainty of each. Uncalibrated sensors are recorded but not used.

### 4.4 Irrigation requirement

- Net depth to refill to field capacity: In = Dr.
- Gross depth: In / (Ea × (1 − LR)), where Ea is application efficiency.
- Leaching requirement LR (FAO‑29):
  - surface and sprinkler: ECw / (5 ECe_threshold − ECw);
  - drip: ECw / (2 ECe_max).

### 4.5 Yield response

- Water (FAO‑33): 1 − Ya/Ym = Ky (1 − ETa/ETm). It is applied seasonally, or stage by stage as a product over growth stages.
- Salinity (FAO‑29): Y/Ym = 1 − b/100 × (ECe − ECe_threshold).

All yields are relative (0 to 1). Absolute yields need locally known potential yields, which QATRA does not have.

### 4.6 Soil hydraulic properties

Field capacity (33 kPa) and wilting point (1500 kPa) are estimated from sand, clay and organic matter with Saxton & Rawls (2006) when no laboratory analysis exists. Organic matter = SOC × 1.724. These values are always labelled *inferred*.

## 5. Decision methods (summary)

- **Irrigation scheduling.** A 72‑hour optimisation decides which zone to irrigate each hour within pump, well, solar, battery and operating-hour limits. It minimises water stress weighted by:
  - the stage sensitivity Ky;
  - an extra multiplier for severe stress in perennial crops, because tree losses last for years.

  These weights are policy choices, visible to the user. In a full-season simulation the optimiser matched a well-designed "irrigate when dry" rule on total stress. It protected perennials much better, at the cost of annual-crop yield.
- **Intervention priority.** Interventions are ranked in a fixed order, with no hidden score:
  1. safety (e.g. a suspected burst);
  2. irreversible risk (a perennial heading for severe stress, or a sensitive stage close to stress);
  3. stress within 72 hours;
  4. no action.

  Every action that moves water requires human approval.
- **Crop suitability.** Each factor is classed S1/S2/S3/N, or U when data is missing (FAO Framework for Land Evaluation). The overall class is the most limiting factor, never an average. Factors that rest on unverified thresholds are reported as warnings and do not decide the class. Water need is sized for a dry year (80th percentile over the available years).
- **Climate scenarios.** Monthly temperature, rainfall and radiation changes from each climate model (2041–2060 against 1995–2014) are applied to the observed 1995–2014 baseline. Results are shown as a range across models, never as one forecast.

## 6. Crop parameters currently in use

Values marked *placeholder* were set by the QATRA team to make the software run. **They have no scientific standing and must be replaced.**

| Parameter | Tomato | Potato | Durum wheat | Olive | Citrus | Date palm |
|---|---|---|---|---|---|---|
| Perennial | no | no | no | yes | yes | yes |
| Stage lengths ini/dev/mid/late (days) | 30/40/45/30 | 25/30/45/30 | 30/60/70/40 | 30/90/60/185 | 60/90/120/95 | 60/90/120/95 |
| Kc ini / mid / end | 0.6 / 1.15 / 0.8 | 0.5 / 1.15 / 0.75 | 0.3 / 1.15 / 0.3 | 0.65 / 0.7 / 0.7 | 0.65 / 0.6 / 0.65 | 0.9 / 0.95 / 0.95 |
| Max crop height (m) | 0.6 | 0.6 | 1 | 4 | 3 | 8 |
| Root depth initial → max (m) | 0.2 → 0.7 | 0.15 → 0.4 | 0.2 → 1.5 | 1.2 → 1.2 | 1.2 → 1.2 | 1.5 → 1.5 |
| Depletion fraction p | 0.4 | 0.35 | 0.55 | 0.65 | 0.5 | 0.5 |
| Ky seasonal | 1.05 | 1.1 | 1.15 | — | 0.9 | — |
| Ky by stage ini/dev/mid/late | 0.4/0.4/1.1/0.4 | 0.45/0.45/0.8/0.2 | 0.2/0.2/0.6/0.5 | — | — | — |
| Salinity ECe threshold (dS/m) | 2.5 | 1.7 | — | — | 1.7 | 4 |
| Salinity yield slope (% per dS/m) | 9.9 | 12 | — | — | 16 | 3.6 |
| Heat-stress Tmax (°C), *placeholder* | 35 | 30 | 32 | 40 | 40 | — |
| Heat-sensitive stages | mid | mid | mid | development | development | — |
| Frost-damage Tmin (°C), *placeholder* | 0 | −1 | −2 | −7 | −2 | −5 |
| Frost-sensitive stages | all | all | mid | all | all | all |

### Sources and notes by crop

**Tomato**
- Stage lengths: FAO‑56 Table 11 (Mediterranean spring planting), to be verified for Tunisian seasons and varieties.
- Kc: FAO‑56 Table 12 (Kc_end midpoint of 0.70–0.90).
- Root depth: FAO‑56 Table 22, lower bound of 0.7–1.5 m. The initial depth is a QATRA assumption.
- p: FAO‑56 Table 22.
- Ky: FAO‑33.
- Salinity: FAO‑29.

**Potato**
- Stage lengths: FAO‑56 Table 11 (semi-arid range). Which Tunisian season does this represent: spring, late season, or *arrière-saison*?
- Kc, root depth (lower bound of 0.4–0.6 m) and p: FAO‑56.
- Ky: FAO‑33.
- Salinity: FAO‑29.

**Durum wheat**
- Stage lengths: **QATRA assumption** (autumn-sown, 200-day cycle).
- Kc and root depth: FAO‑56.
- Ky: FAO‑33 spring-wheat value, used for autumn-sown durum.
- **Salinity tolerance: missing.**
- Most Tunisian durum is rainfed; irrigation logic applies to supplementary irrigation only.

**Olive**
- Kc: FAO‑56 Table 12 (40–60 % ground cover).
- Root depth and p: FAO‑56.
- **Stage split: QATRA placeholder.**
- **No Ky:** yield response to deficit is not computed.
- **No salinity tolerance.**
- Kc is not yet adjusted for young or sparse orchards.

**Citrus**
- Kc: FAO‑56 Table 12 (no ground cover, ~50 % canopy).
- Root depth and p: FAO‑56.
- Ky 0.9: within the FAO‑33 range of 0.8–1.1.
- Salinity: FAO‑29 orange values.
- **Stage split: QATRA placeholder.**

**Date palm**
- Kc, root depth and p: FAO‑56.
- Salinity: FAO‑29.
- **Stage split: QATRA placeholder.**
- **No Ky.**
- A single-crop Kc may not represent multi-storey oasis plots.

## 7. What we ask reviewers to check

Please answer whichever items fall within your expertise. A short note with a reference is ideal.

1. **Heat and frost thresholds** (table rows marked *placeholder*): the temperatures that cause damage, and the growth stages at which they matter, for each crop under Tunisian conditions.
2. **Ky for olive and date palm**, or guidance on how deficit irrigation of these crops should be represented. Regulated deficit irrigation of olive is common, and QATRA currently cannot judge it.
3. **Salinity tolerance of durum wheat** and of olive (threshold ECe and yield slope).
4. **Stage lengths and planting dates** used in the main Tunisian production regions (e.g. Sidi Bouzid, Kairouan, Nabeul), especially:
   - the durum-wheat calendar;
   - potato seasons;
   - the annual cycle of the perennials.
5. **Kc adjustments for young or sparse orchards** (canopy cover), and whether the Kc values for olive and citrus suit local orchard densities.
6. **Root depths:** QATRA uses the *lower* bound of FAO‑56 ranges, which gives a conservative estimate of soil storage. Is that appropriate for local soils and drip irrigation?
7. **The priority rule:** is a ×2 extra weight on severe stress in perennials, relative to annual crops, a reasonable *default*? Users can change it; we want a defensible starting point. In a season-long simulation, ×2 cut olive severe-stress hours by 90 % compared with ×1 for about 0.04 of tomato relative yield, and higher weights added little.
8. **The suitability class boundaries** (relative yield ≥ 0.9 for S1, ≥ 0.75 for S2, ≥ 0.5 for S3). These are QATRA rules, not published standards.
9. **Local data:** any station records, soil analyses, measured crop water use or yield trials that could be used to calibrate or validate QATRA.

## 8. Known issues

- **Saxton & Rawls reference values.** For a loam (40 % sand, 20 % clay, 2.5 % OM), QATRA computes a wilting point of 13.7 %. The reference table as we recalled it gives 12 %. The equations match the paper as implemented, but the table value has not been re-checked against the original publication.
- **Weather resolution.** NASA POWER cells are about 50 km wide and do not capture local microclimate. Station data would improve every estimate.
- **Rainfed systems.** QATRA's water logic assumes irrigation. Rainfed olive and cereal systems are outside its current scope.
- **Climate scenarios.** The delta-change method shifts the whole climate but does not change the sequence of wet and dry days or the frequency of extremes. CO₂ effects on crop water use are not included.

## 9. References

- Allen, R.G., Pereira, L.S., Raes, D., Smith, M. (1998). *Crop evapotranspiration: Guidelines for computing crop water requirements.* FAO Irrigation and Drainage Paper 56. Rome: FAO.
- Doorenbos, J., Kassam, A.H. (1979). *Yield response to water.* FAO Irrigation and Drainage Paper 33. Rome: FAO.
- Ayers, R.S., Westcot, D.W. (1985). *Water quality for agriculture.* FAO Irrigation and Drainage Paper 29 Rev. 1. Rome: FAO.
- Saxton, K.E., Rawls, W.J. (2006). Soil water characteristic estimates by texture and organic matter for hydrologic solutions. *Soil Science Society of America Journal* 70: 1569–1578.
- FAO (1976). *A framework for land evaluation.* FAO Soils Bulletin 32. Rome: FAO.
- Poggio, L., et al. (2021). SoilGrids 2.0: producing soil information for the globe with quantified spatial uncertainty. *SOIL* 7: 217–240.
- Thrasher, B., et al. (2022). NASA Global Daily Downscaled Projections, CMIP6. *Scientific Data* 9: 262.
