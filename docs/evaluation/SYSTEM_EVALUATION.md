# QATRA AI system: full evaluation

Date: 2026-11-22 · Branch `ai-engine` (includes uncommitted work) · Evaluator: AI engineering review with new measurements

## Verdict

QATRA is a **well-engineered research prototype that has not been validated on a real farm**.

- **Engineering is strong.** 296 tests pass with 90 % line coverage. Every output carries its provenance, validation status and limitations, and the system was honest about its own evidence before this review.
- **The decision core is sound but only simulation-tested.** The optimiser and anomaly detectors behave as designed in simulation. No irrigation decision has ever been checked against a real field.
- **First real-data result, from this review:** the gridded weather the engine runs on (NASA POWER) gives daily ET0 within ±0.37 mm/day of a Sidi Bouzid station, with almost no bias over 13 days. That is a good sign for the inputs, but the sample is small.
- **The LLM layer works live, but its safety net has a measurable hole.** All 6 live assistant answers passed grounding (en/fr/ar). The stress test shows the numeric check catches only 60–87 % of wrong numbers when an answer cites several large tool results. The review also found a data-class disclosure gap on the anomaly tool.
- **The market and strategy modules are new and run on assumptions.** No real price data exists yet.

**Readiness:** suitable for a **supervised pilot** on one farm as advisory decision support (every action already needs human approval), after the four P0 fixes in §6. It is not suitable for unsupervised use, and no accuracy claim can be made yet.

---

## 1. What was evaluated and how

| Evidence level | Meaning | Examples here |
|---|---|---|
| L1 Code | Unit and property tests: the code does what its specification says | 296 tests |
| L2 Reference | Reproduces published worked examples or literature values | FAO-56 ET0 examples |
| L3 Simulation | Closed-loop or synthetic benchmark. The "truth" is a model written by the same team | Scheduler, anomaly benchmarks |
| L4 Real-data component check | One component or input compared with real observations | NASA POWER vs CRRA station (new) |
| L4-LLM Live run | Live LLM calls, judged by automated checks plus human reading | 6 assistant questions, 1 strategy run (new) |
| L5 Field validation | Decisions compared with outcomes on a real farm | **None yet** |

New measurements made for this review (all reproducible, see the appendix):

1. NASA POWER vs DGACTA CRRA station, 13 complete days (Oct–Nov 2026).
2. A grounding-verifier stress test: 36,000 synthetic claims against the demo farm's real tool results.
3. A live assistant battery on Gemini: 6 questions in 3 languages, with every answer read.
4. A live strategy-agent run on Gemini.
5. Full test suite with coverage, mypy, and a code and contract review.

---

## 2. Scorecard

| Component | Role | Evidence | Key result | Verdict |
|---|---|---|---|---|
| ET0 (FAO-56 PM, Hargreaves) | Crop water demand | L1, L2 | Matches FAO-56 worked examples | ✅ Correct implementation |
| Weather input (NASA POWER) | Main driver of every decision | **L4 (new)** | Daily ET0 MAE 0.37 mm/d, total bias +0.5 % (n = 13 days) | 🟡 Promising, tiny sample |
| Crop and soil parameters | Kc, Ky, thresholds, TAW | L2 | All 6 crops `needs_review`; heat/frost thresholds unverified | 🟠 Needs agronomist review |
| Water balance + Kalman assimilation | Soil-water state | L1 | Never run on a real sensor | 🟠 Unvalidated |
| Irrigation scheduler (MILP) | 72 h plan under pump, energy and water limits | L3 | Equal to a good threshold rule on total stress; protects perennials (0–26 vs 1,071 severe h) | 🟡 Sound; policy trade-off, not a gain |
| Plan verifier / safety veto | Blocks plans that break constraints | L1, L3 | 0 unserved hours in closed loop | ✅ |
| Anomaly detection (8 detectors) | Leaks, bursts, clogging, meter faults | L3 | 100 % detection at ≤ 4 % noise; slow leaks < 0.08 m³/h missed; ≤ 0.01 false alarms/week | 🟡 Synthetic only |
| Decision orchestrator | Ranked, explained proposals | L1, L3 | Lexicographic tiers; every water action needs approval | ✅ Design |
| Suitability (FAO limiting factor) | What to grow | L1 + real weather | Provisional heat/frost; market = U | 🟡 |
| Climate scenarios | 2050 stress tests | L1 + CMIP6 | 3 of 5 models usable | 🟡 |
| Water allocation (6 strategies) | Sharing an aquifer | L1 | Synthetic only; shows consequences, never says "fair" | 🟡 |
| Market + reflexivity | Price bands, adoption cap | L1 | No price data; everything hypothetical, confidence low | 🟠 Framework only |
| Crop portfolio + regional loop | Risk-aware crop mix, plan–price equilibrium | L1 | Equilibrium optimality test passes | 🟠 Framework only |
| Assistant (LLM) | Explains outputs, ar/fr/en | L1 + **L4-LLM (new)** | 6/6 verified live in two runs, 0 fallbacks; median 14 s before P0, 38 s after (stricter checks cause rewrites) | 🟡 Works; see §3.6 and P0 status |
| Grounding verifier | LLM safety net | **Stress test (new)** | Before the fix: 99–100 % catch with one cited result, 60–87 % with four. After P0-2: four per sentence no longer allowed; two largest results 72–96 % | 🟡 Improved; residual documented |
| Strategy agent (web + sensors) | Season strategy | L1 + 1 live run | Verified; web trends blocked by the search-grounding quota (429) | 🟠 Unproven on real web data |
| ML models | Forecasting, classification | none | No model exists; none can be trained honestly yet | ⏳ Waiting for data |

---

## 3. Findings by area

### 3.1 Data and inputs

**New real-data check, NASA POWER vs CRRA station** ([details](weather_nasa_power_vs_crra.md)). 13 complete days, 23 Oct–10 Nov 2026; bias = POWER minus station:

| Variable | Bias | MAE | r |
|---|---|---|---|
| Tmax | −0.40 °C | 0.67 °C | 0.90 |
| Tmin | −1.57 °C | 1.75 °C | 0.81 |
| Solar radiation | +1.02 MJ/m²/d | 2.15 MJ/m²/d | 0.64 |
| Wind (2 m) | +0.20 m/s | 0.52 m/s | 0.74 |
| **ET0 (Penman-Monteith)** | **+0.01 mm/d** | **0.37 mm/d** | 0.62 |

What this means:

- **Errors cancel over a season.** The total ET0 differs by only +0.5 %. The daily error (about 15 % of a 2.5 mm day) matters for day-to-day scheduling, less for seasonal budgets.
- **POWER nights are colder.** Part of the Tmin gap comes from the station's 2-hourly sampling, which misses the true minimum.
- **Humidity could not be checked** (the station sensor is stuck at 100 %), and humidity is a major ET0 input here.
- **The sample is small.** It covers autumn only, the season with the least irrigation. Re-run in summer.

**Data reality** (from [the station quality report](../data/dgacta_sidi_bouzid_quality.md) and [the audit](../AUDIT_AND_DATA_PLAN.md)):

- No farm data of any kind exists: no soil moisture, flow, irrigation logs or yields.
- The government station feeds are short rolling windows with failed sensors.
- The archiver is right to keep collecting: history only exists if it runs every day.

### 3.2 Agronomy core

- **Correct implementation:** ET0 reproduces the FAO-56 examples, and the water balance closes its mass balance every day.
- **Unvalidated parameters:** every crop profile is `needs_review`, and the heat/frost thresholds are placeholders. The engine already treats them as provisional warnings instead of hard limits, which is the right design.
- **Main scientific risk:** the Kc and Ky values come from international tables, not Tunisian varieties. An agronomist review is the cheapest large improvement available.

### 3.3 Optimisation and decisions

Source: the closed-loop benchmark, March–August 2025, real weather, hypothetical farm ([report](scheduler_closed_loop_2025.md)).

- **The optimiser is not "better" overall.** Total stress is +3 % against a well-designed threshold rule, and severe hours −6 %.
- **What it changes is how scarcity is shared.** It keeps the perennial olive grove almost free of severe stress (0–26 h vs 1,071 h) at the cost of tomato yield (relative yield 0.24 vs 0.29). The report states plainly that this is a value judgement.
- **The trade-off is mapped.** The κ-curve shows a knee at κ = 2.
- **Forecasts:** persistence forecasts cost only about 1 % more stress in a dry, regular summer.
- **Limitation:** planner and "truth" use the same model, so robustness was probed only with a +10 % ET bias. **This is the biggest evaluation gap for the core product.**

### 3.4 Anomaly detection

Source: the synthetic benchmark ([report](anomaly_synthetic_benchmark.md)).

- **Detection:** 100 % for 7 fault types at ≤ 4 % meter noise. Clogging drops to 75 % at 6 % noise.
- **Sensitivity limits:** slow leaks below about 0.08 m³/h and bursts below about 10 % of zone flow are mostly missed.
- **False alarms:** ≤ 0.01 per week on clean runs.
- **Caveat:** the generator and the detectors were written by the same team, and faults are idealised steps. Real performance is unknown.

### 3.5 Market intelligence and strategy

- **The mechanics are verified on synthetic inputs:**
  - price falls monotonically with adoption;
  - every price is a P10–P90 band, never a point value;
  - the adoption cap matches the exact break-even;
  - the equilibrium plan is optimal at its own prices;
  - the forecast backtest has no look-ahead.
- **Nothing is calibrated.** Reference prices, production and elasticities are all inputs. With no ONAGRI or FAOSTAT series loaded, every output is `hypothetical` with confidence `low`, and the labels say so.
- **Strategy agent:** one live Gemini run produced a verified strategy. Web research failed with a Google Search grounding quota error (429), so its web-trend path is **unproven live**.

### 3.6 LLM layer

**Live assistant on Gemini** (6 questions, en/fr/ar; [answers](assistant_live_gemini.md)):

- **Results:** 6/6 passed the grounding check and 0 used the template fallback. Every answer stated that the water state is modelled rather than measured, gave the confidence, and said human approval is needed.
- **Latency:** median 14 s per answer. The first request took 166 s because it also built the farm's weather and suitability data (a cold-start cost of the service, not of the LLM).
- **Model:** every answer was served by the fallback `gemini-3.5-flash-lite`, because the primary `gemini-3.8-flash` was overloaded. The fallback chain works, but you are not getting the model you configured.

**Grounding verifier stress test** ([details](grounding_verifier_stress.md)). Share of claims flagged:

| Case | One cited result | Four cited results |
|---|---|---|
| Correct value (should be 0 %) | 0 % | 0 % |
| Invented number | 99 % | 85–87 % |
| True value off by 2 % | 100 % | 69 % |
| True value off by 50 % | 100 % | 60 % |
| Invented small integer 0–10 | 0 % (by design) | 0 % |

**Why:** the check accepts a number that matches any value in the cited results. The anomaly and suitability results hold 424 and 242 numbers, so wrong numbers often match something by chance. It also cannot tell which quantity a number belongs to.

**Issues found by reading the live answers.** None of these are caught by the automated checks:

| # | Issue | Evidence | Severity |
|---|---|---|---|
| 1 | **Simulated anomalies presented as real** (fixed by P0-1; confirmed live). The French answer says leaks were "détecté … sur votre réseau". The demo's hydraulic data is synthetic, but `AnomalyEvent` has no data-class field and the tool notes don't say "simulated", so the model could not know. | Confirmed in code | **High** (honesty) |
| 2 | **Combined citations are not parsed** (fixed by P0-2). `[r1, r2]` yields no citation, so an answer citing only that way is rejected (needless fallback). Citations are pooled per answer, not per claim. | Confirmed with a unit probe | Medium |
| 3 | Internal package ids shown to the farmer ("tomato zone (`demo-farm-1`)") | Answer 2 | Low |
| 4 | Arabic wording error: "مقبود" is not a word (likely meant "مقبول" or "محدود") | Arabic answer 2 | Low–medium (trust) |

**What has not been tested:**

- prompt injection (red-teaming the assistant, and web pages for the strategy agent);
- answer quality judged by farmers or agronomists;
- behaviour under long conversations;
- the Claude path of the strategy agent live.

### 3.7 Safety and responsible AI

| Property | How it is enforced | Evidence |
|---|---|---|
| No autonomous action | Every water action has `requires_human_approval`; no tool actuates hardware | Code + tests |
| Plans must respect physical limits | Independent `verify_plan` veto | Tests, closed loop |
| No blame | Anomaly language bans accusatory terms; the verifier forbids "theft/fraud" (en/fr/ar) | Tests |
| No promises | Guarantee wording is banned in the assistant verifier and the strategy checks | Stress test: 100 % caught |
| Real and synthetic data kept apart | `DataClass` on every value; the data store rejects mislabelled zones | Tests; **gap: anomaly tool output (issue 1)** |
| Fairness is not decided by the engine | Allocation shows 6 strategies and fairness metrics, never says "fair" | Design |
| Privacy | The strategy agent sends governorate and crops only, never coordinates or the farm name | Test |
| Market reflexivity | Adoption cap and boom–bust warnings; prices only as bands | Tests |

### 3.8 Engineering quality

| Metric | Value |
|---|---|
| Engine size | 12.2 k lines (`qatra_ai`), 4.3 k lines of tests |
| Tests | 296 pass (284 fast in about 26 s, 12 slow simulations) |
| Line coverage | **90 %** (6,086 statements). Gaps: PVGIS reader 0 %, `farms/check.py` 0 %, NEX-GDDP 37 %, service data provider 36 %, Open-Meteo 59 % |
| Lint (ruff) | Clean |
| Types (mypy) | **149 errors in 28 files.** 52 are in `evaluation/synthetic_water.py`; most are typing noise, but types are not enforced |
| Reproducibility | `inputs_hash` on every envelope; seeded Monte Carlo; raw downloads hashed with SHA-256 |
| Version control | **29 paths uncommitted**, including all of this session's modules |
| Secrets | The `.env.example` JWT secret flagged in the audit is now a placeholder ✅ |

### 3.9 Production and MLOps readiness

- **No ML models,** so there is no model registry, drift monitoring or retraining to evaluate. The audit's "refuse to train on insufficient measured data" design is correct.
- **No evaluation in CI.** The benchmarks are scripts run by hand; nothing fails a build when the anomaly detection rate or the verifier catch rate drops.
- **No runtime monitoring** of LLM fallback rate, verifier rejection rate or latency.
- **Cold start:** the first request per farm takes minutes (weather downloads). It needs pre-warming or a cache job.
- **Single points of failure:** NASA POWER, Open-Meteo (non-commercial free tier, daily 429s) and the Gemini quota.

---

## 4. Risks, ranked

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Decisions are wrong in the field (parameters, model structure) and nobody can tell | High | High | Pilot farm with sensors; agronomist review |
| 2 | The assistant states a wrong number that passes the verifier | Medium (40 % miss rate with broad citations) | High | Per-claim citations; field-level checks (P0-2) |
| 3 | Simulated or modelled information presented as observed | Medium (seen live) | High (trust) | Data class in every tool output (P0-1) |
| 4 | The LLM provider is unavailable or switches models silently | High (seen today) | Medium (template fallback exists) | Monitor the served model; alert on fallback |
| 5 | Market numbers taken as forecasts | Medium | Medium | Already labelled; keep confidence low until backtested |
| 6 | Work lost or unreviewable (29 uncommitted paths) | Medium | Medium | Commit in reviewed chunks |
| 7 | Prompt injection through web pages (strategy agent) | Low–medium | Medium | Red-team; the checks already block invented URLs and actions |

---

## 5. What field validation should look like

Acceptance targets for a one-season pilot. These are proposals, to be agreed with the agronomist.

| Module | Metric | Baseline to beat | Target |
|---|---|---|---|
| Weather → ET0 | Daily ET0 MAE vs an on-farm or nearby station (summer) | — | ≤ 0.6 mm/d; seasonal bias ≤ 5 % |
| Water balance | Root-zone depletion vs calibrated probes (RMSE, mm) | Open loop (no assimilation) | Kalman ≤ 0.7 × open-loop RMSE |
| Days-to-stress | Hit rate of the "stress within 3 days" warning | Threshold-rule warning | Hit rate ≥ 80 % with ≤ 1 false warning a week |
| Scheduler | Stress hours and water use vs the farmer's own practice | The farmer's schedule | Same water, fewer severe hours on perennials |
| Anomalies | Detection and false alarms on logged real incidents | — | ≥ 1 detected real leak; ≤ 1 false alarm a month |
| Assistant | Expert-rated correctness and usefulness (blind, ≥ 50 questions, ar/fr) | Template answer | ≥ 90 % correct, 0 safety violations |
| Market | Pinball loss vs seasonal naive (when ≥ 5 years of prices exist) | Seasonal naive | Beat the naive baseline, or keep using it |

---

## 6. Recommendations

**P0: before any pilot (days)**

1. **Data class in every tool output.** Add `data_class` and a "simulated" note to `AnomalyEvent` and to the assistant tool results, and add a test that fails when a tool result has no data class. *Done when:* the French anomaly question gets an answer that says the data is simulated.
2. **Close the verifier hole.**
   - Parse `[r1, r2]` citations.
   - Check numbers against the result cited **in the same sentence**, not the whole answer.
   - For irrigation amounts, compare against the exact package field.
   *Done when:* the four-results row of the stress test catches ≥ 95 % of wrong numbers.
3. **Commit the work** in reviewed commits: market, portfolio, regional, strategy, evaluations.
4. **Monitoring:** log the served model, fallback rate, verifier rejections and latency per request.

### P0 status (applied 2026-11-22, same day)

| P0 | What changed | Measured outcome |
|---|---|---|
| 1. Data class in every tool output | Every tool result has a top-level `data_class` (simulated, inferred, literature_reference, user_supplied, web_reported, unknown). Simulated, projected and unknown origins add a note telling the model to say so. The decision envelope now fills `provenance_summary`, which was empty. Real farms without a flow meter now get "no hydraulic data analysed" instead of an empty list read as "no anomalies". | Test: every tool result states its origin. **Live:** the French anomaly answer now says the events are "basées sur des données simulées" (before: "détectées sur votre réseau"). |
| 2. Verifier hole | Citations are scoped per claim (sentence, then line, paragraph, answer). `[r1, r2]` is parsed. Units are checked. Dates and times are checked whole. Small integers with a unit are checked. A sentence with numbers may cite at most two results. | One cited result: 99–100 % caught. A true value from an uncited result: 97 % caught (could pass before). Two largest results cited together: **72–96 %**, below the 95 % target, so this stays a documented residual ([details](grounding_verifier_stress.md)). False alarms stay at 0 %. All 6 earlier live answers still pass when replayed. |
| 3. Commit | See the git history on `ai-engine` | — |
| 4. Monitoring | `service/telemetry.py` writes one JSON line per assistant or strategy request: configured vs served model, verified, fallback and reason, violation rule types, tool calls and latency. It never stores question or answer text. Summary at `GET /api/telemetry/llm`. | First live data (6 answers): verified 100 %, fallback 0 %, **model switched 100 %** (always `gemini-3.5-flash-lite`), **rejected first drafts 50 %**, latency p50 38 s and p95 128 s. |

**New finding from monitoring.** The stricter verifier rejected the first draft of 3 of the 6 live answers. Each was rewritten and then passed, but median latency rose from 14 s to 38 s. The rule types of those rejections are now logged (`violation_rules`). The next live batch will show whether they were real catches or rules too strict for natural answers. That decides whether P1 should tune the rules.

**P1: next (weeks)**

5. **Evaluation in CI:** run the anomaly benchmark (reduced), the verifier stress test and the offline LLM tests on every push, with thresholds.
6. **Red-team the LLM layer:** prompt injection in user questions and in web pages, with ≥ 30 cases.
7. **Arabic and French review** of the assistant's answers by a native speaker. Add a small set of expected terms.
8. **Pre-warm the farm runtime** to remove the 166 s cold start.
9. **Re-run the weather check** with summer data, and add Open-Meteo as a second gridded source.
10. **Type health:** fix mypy in the decision path first (scheduler, water balance, orchestrator).

**P2: with data (season)**

11. Pilot farm: calibrated probes, a flow meter and an irrigation log. Run §5.
12. Agronomist review of crop parameters, then move them from `needs_review` to `reviewed`.
13. Load ONAGRI or FAOSTAT price series. Only then move market outputs past `low` confidence.
14. Start the ML pipelines only when the measured-data thresholds in the audit are met.

---

## Appendix: reproduce this evaluation

```bash
cd ai_engine
uv run pytest --cov=qatra_ai                                   # 296 tests, coverage
uv run python examples/eval_weather_vs_station.py              # -> weather_nasa_power_vs_crra.md
uv run python examples/eval_grounding_verifier.py              # -> grounding_verifier_stress.md
uv run --env-file ../.env python examples/eval_assistant_live.py   # -> assistant_live_gemini.md (quota calls)
uv run --env-file ../.env python examples/strategy_demo.py demo-farm "..." fr
uv run python examples/benchmark_anomaly.py                    # -> anomaly_synthetic_benchmark.md
uv run python examples/benchmark_scheduler.py                  # -> scheduler_closed_loop_2025.md (slow)
uv run mypy qatra_ai --ignore-missing-imports
```
