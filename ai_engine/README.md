# QATRA AI Engine (`qatra_ai`)

The decision-intelligence core of QATRA, a standalone Python package with no dependency on the web platform.
Design: [../docs/AI_ENGINE_BLUEPRINT.md](../docs/AI_ENGINE_BLUEPRINT.md).

## Status: Phase 1 (foundations), in progress

| Component | Module | State |
|---|---|---|
| Contracts (Quantity, Provenance, ModelInfo, EngineEnvelope) | `qatra_ai.contracts` | ✅ implemented |
| FAO‑56 ET0 (Penman–Monteith + Hargreaves fallback) | `agronomy.et0`, `agronomy.daily_et0` | ✅ tested against FAO‑56 worked examples |
| Crop profiles (tomato, potato, durum wheat, olive, citrus, date palm) | `reference_data/crops/*.yaml` | ✅ with citations; **all `needs_review`** |
| Kc curve, climate adjustment, root growth, p adjustment | `agronomy.kc` | ✅ |
| Soil FC/WP (Saxton & Rawls 2006), TAW | `agronomy.soil` | ✅ (reference table values need re-checking, see tests) |
| Daily root-zone water balance + Kalman sensor assimilation | `agronomy.water_balance` | ✅ mass balance verified every day |
| Days-to-stress projection | `agronomy.water_balance.days_to_stress` | ✅ |
| Irrigation requirement, FAO‑29 leaching | `agronomy.irrigation` | ✅ |
| FAO‑33 yield response (seasonal, stage-wise), salinity | `agronomy.yield_response` | ✅ |
| Zone assessment with rule-based confidence | `agronomy.assessment` | ✅ |
| Pump energy, PV power, battery | `energy` | ✅ |
| Time-series QC (range, spike, flat-line, timestamps, short-gap fill) | `data.qc` | ✅ |
| Open-Meteo reader (hourly → FAO‑56 daily) | `data.sources.open_meteo` | ✅ parser tested; **live run not yet verified** (API daily quota hit) |
| NASA POWER reader | `data.sources.nasa_power` | ✅ parser tested + **live run OK** (Sidi Bouzid, Apr–Aug 2025) |
| SoilGrids reader (→ Saxton–Rawls FC/WP) | `data.sources.soilgrids` | ✅ parser tested + **live run OK**; urban/no-data points return a clear error |
| Dual Kc, canopy-cover adjustment for young orchards | — | ⏳ planned |
| **Phase 3:** multi-zone irrigation scheduler (MILP, OR-Tools/SCIP) | `optimization.irrigation_scheduler` | ✅ pump, well caps (horizon/daily), PV + battery + grid, operating windows, hours/day; Ky × irreversibility weighting |
| Plan explanations | same | ✅ per-zone reason codes, binding constraints, LP-relaxation shadow prices, equal-weight comparison |
| Independent plan verification (safety veto input) | `irrigation_scheduler.verify_plan` | ✅ a plan with any violation is not released |
| Agronomy → scheduler builders (hourly ET/PV disaggregation) | `optimization.inputs` | ✅ |
| Closed-loop (rolling-horizon) policy benchmark: calendar / threshold / optimiser, executor + truth with stress feedback | `evaluation.closed_loop` | ✅ season run on real 2025 weather done ([report](../docs/evaluation/scheduler_closed_loop_2025.md)): optimiser ≈ threshold rule on total stress, far better perennial protection, lower annual yield |
| Well-water allocation between farms sharing an aquifer (S1–S6, fairness metrics, marginal value) | `optimization.allocation` | ✅ synthetic tests; decision support only |
| Water anomaly detection (8 detectors, hypotheses + evidence, adaptive thresholds, no accusatory language) | `predictive.anomaly` | ✅ **simulation-tested** on synthetic labelled faults ([report](../docs/evaluation/anomaly_synthetic_benchmark.md)) |
| Synthetic water-system generator with labelled faults | `evaluation.synthetic_water` | ✅ `data_class = simulated` |
| **Decision orchestrator**: quality gate → agronomy → anomalies → safety veto → 72 h optimisation → ranked decision packages (tiers: safety / irreversible risk / stress / none) | `orchestrator.decision` | ✅ synthetic tests + real-data demo; every physical action requires human approval |
| **Explainable assistant** (Claude `claude-opus-5-5`, Messages API tool loop, read-only tools, deterministic grounding verifier, ar/fr/en, template fallback) | `assistant` | ✅ tested offline with a scripted fake client; **not yet run live** (no API credentials on this machine) |
| Crop suitability (FAO limiting factor S1/S2/S3/N/U + Pareto trade-offs, multi-year dry-year water need) | `suitability.engine` | ✅ real 10-year demo; heat/frost thresholds are **unverified placeholders** → provisional warnings only; market = U |

**Validation status:** the irrigation scheduler and anomaly detectors are `simulation_tested`; everything else is `literature_parameterised`. Nothing has been validated against field data from Tunisia.

## Run

```bash
cd ai_engine
uv sync
uv run pytest -m "not slow"            # 143 fast tests (~10 s)
uv run pytest                         # + 12 slow closed-loop/benchmark tests
uv run python examples/season_demo.py --weather nasa_power   # real weather + real SoilGrids soil + HYPOTHETICAL tomato zone
uv run python examples/season_demo.py                        # same with Open-Meteo (adds ET0 cross-check)
uv run python examples/schedule_demo.py                      # real weather/soil -> 72 h plan for a HYPOTHETICAL 3-zone solar-pumped farm
uv run python examples/benchmark_scheduler.py                # season-long policy comparison (slow)
uv run python examples/benchmark_anomaly.py                  # synthetic anomaly benchmark -> docs/evaluation/
uv run python examples/suitability_demo.py                   # 6 crops, real 2015-2024 weather + soil, HYPOTHETICAL quota
uv run python examples/decision_demo.py                      # ranked 'where to intervene first' packages, real weather/soil
uv run python examples/assistant_demo.py "Why is the tomato zone first?"   # needs ANTHROPIC_API_KEY; billed API calls
```

## Rules this package follows

- Physical values cross module boundaries as `Quantity` (value and unit).
- Every engine output is an `EngineEnvelope`. It carries the input hash, provenance counts, model validation status, confidence and the reasons for it, limitations and missing inputs.
- Data is flagged, never silently altered. Gaps are filled only when short, and the fill is flagged.
- Simulated or projected inputs cap confidence at `low`.
- Open-Meteo's free API is **non-commercial only**.
