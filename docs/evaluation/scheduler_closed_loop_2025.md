# Closed-loop benchmark: irrigation policies (simulation only)

> **Simulation-tested, not field-validated.** The "truth" water balance uses the same FAO‑56
> model as the planner. Results compare decision policies *given that model*. They do not show
> real-world performance.

- **Period:** 2025-03-02 → 2025-08-23. Each policy re-plans daily at 00:00 and executes 24 h.
- **Weather (real):** NASA POWER daily, grid cell containing 35.1 N, 9.3 E (~50 km cells; data_class `inferred`).
- **Soil (real):** SoilGrids 0–60 cm → Saxton–Rawls: FC 0.2787, WP 0.1551 (`inferred`).
- **Farm (hypothetical):** olive 2 ha (cycle from Mar 1), tomato 1 ha (planted Apr 1), potato 1 ha (planted Mar 1);
  drip, application efficiency 0.9; well pump max 15 m³/h, one zone at a time, 60 m head;
  off-grid PV 12 kWp + 20 kWh battery; well cap 120 m³/day.
- **Fixed calendar hours per event (every 2 days):** {'olive-north': 15.4, 'tomato-east': 14.5, 'potato-south': 11.4}
- **Shared knowledge:** every policy sees the exact current soil-water state (as with calibrated sensors).
- **Executor:** requests beyond pump, energy or water limits are dropped and counted as "unserved".
- **Baselines are made competent on purpose:** the calendar scales every zone to fit the well cap
  and rotates which zone goes first; the threshold rule serves the driest zone first.
- **Optimiser settings:** 72 h horizon re-solved daily, MIP gap 0.1 %, 10 s time limit per solve,
  PV derated 20 % in planning (actual PV is not derated in the executor).
- **Not included:** an equal-seasonal-water comparison (needs a seasonal water budget, not yet built).

## Findings (written after reviewing the results)

1. The fixed calendar performs worst even when sized to season-average demand and fitted to the
   well cap. It under-delivers at peak demand.
2. The optimiser does **not** dominate a well-designed threshold rule (refill when Dr ≥ RAW,
   driest zone first). Total stress is similar (optimiser +3 %) and severe hours slightly
   lower (−6 %). The difference is **allocation**: the optimiser keeps the perennial olive
   grove almost free of severe stress (0–26 h vs 1,071 h). It pays with lower tomato yield
   (0.24 vs 0.29 relative yield). This follows directly from the default irreversibility
   weight (perennial severe-stress multiplier 5). It is a policy choice, not an objective gain.
3. Persistence forecasts cost about 1 % more stress than perfect forecasts on this dry,
   regular summer. Expect a larger gap in seasons with rain events.
4. With true ET 10 % above the planners' assumption, the same pattern holds: the optimiser
   protects the perennial (268 vs 1,494 severe hours) at the expense of annual crops.
5. An earlier run of this benchmark used unfair baselines (fixed zone order starving two zones)
   and overstated the optimiser's advantage. It was discarded.

Suggested follow-up: run the optimiser with `kappa_perennial = 1` to trace the trade-off
between perennial protection and annual yield, so decision makers see the whole curve.

## Farm totals

| scenario                                                                              |   water_m3 |   stress_mm_h |   severe_hours |   unserved_zone_hours |   pump_energy_kwh |
|:--------------------------------------------------------------------------------------|-----------:|--------------:|---------------:|----------------------:|------------------:|
| Fixed calendar (every 2 d, season-average sizing, scaled to well cap, rotating order) |       9570 |        227864 |           5361 |                     4 |              3160 |
| Threshold rule (refill when Dr >= RAW, driest first)                                  |      15300 |        159358 |           2587 |                   744 |              5052 |
| Optimiser, perfect forecast                                                           |      15618 |        163626 |           2429 |                     0 |              5157 |
| Optimiser, persistence forecast                                                       |      15506 |        165898 |           2522 |                     2 |              5120 |

## Per zone

| scenario                                                                              | zone         |   water_m3 |   eta_over_etc |   stress_mm_h |   severe_hours |   days_with_stress | relative_yield   |
|:--------------------------------------------------------------------------------------|:-------------|-----------:|---------------:|--------------:|---------------:|-------------------:|:-----------------|
| Fixed calendar (every 2 d, season-average sizing, scaled to well cap, rotating order) | olive-north  |       4860 |          0.59  |         76099 |           1792 |                 87 | n/a              |
| Fixed calendar (every 2 d, season-average sizing, scaled to well cap, rotating order) | potato-south |       2060 |          0.449 |         47296 |           1481 |                 87 | 0.401            |
| Fixed calendar (every 2 d, season-average sizing, scaled to well cap, rotating order) | tomato-east  |       2650 |          0.401 |        104469 |           2088 |                107 | 0.085            |
| Threshold rule (refill when Dr >= RAW, driest first)                                  | olive-north  |       6120 |          0.654 |         65003 |           1071 |                119 | n/a              |
| Threshold rule (refill when Dr >= RAW, driest first)                                  | potato-south |       4260 |          0.717 |         23765 |            553 |                 96 | 0.708            |
| Threshold rule (refill when Dr >= RAW, driest first)                                  | tomato-east  |       4920 |          0.591 |         70590 |            963 |                118 | 0.292            |
| Optimiser, perfect forecast                                                           | olive-north  |       9108 |          0.8   |         37980 |              0 |                104 | n/a              |
| Optimiser, perfect forecast                                                           | potato-south |       3400 |          0.638 |         30894 |            732 |                 62 | 0.700            |
| Optimiser, perfect forecast                                                           | tomato-east  |       3110 |          0.468 |         94752 |           1697 |                111 | 0.239            |
| Optimiser, persistence forecast                                                       | olive-north  |       9036 |          0.795 |         38657 |             26 |                104 | n/a              |
| Optimiser, persistence forecast                                                       | potato-south |       3400 |          0.631 |         31492 |            732 |                 68 | 0.690            |
| Optimiser, persistence forecast                                                       | tomato-east  |       3070 |          0.464 |         95749 |           1764 |                114 | 0.237            |

## Robustness: real ET 10 % higher than planners assume

| scenario                                                                                               | zone         |   water_m3 |   eta_over_etc |   stress_mm_h |   severe_hours |   days_with_stress | relative_yield   |
|:-------------------------------------------------------------------------------------------------------|:-------------|-----------:|---------------:|--------------:|---------------:|-------------------:|:-----------------|
| Fixed calendar (every 2 d, season-average sizing, scaled to well cap, rotating order) [truth ET +10 %] | olive-north  |       4860 |          0.536 |         91658 |           1968 |                 96 | n/a              |
| Fixed calendar (every 2 d, season-average sizing, scaled to well cap, rotating order) [truth ET +10 %] | potato-south |       2060 |          0.407 |         53171 |           1649 |                102 | 0.354            |
| Fixed calendar (every 2 d, season-average sizing, scaled to well cap, rotating order) [truth ET +10 %] | tomato-east  |       2650 |          0.369 |        115142 |           2140 |                118 | 0.067            |
| Threshold rule (refill when Dr >= RAW, driest first) [truth ET +10 %]                                  | olive-north  |       6468 |          0.609 |         78071 |           1494 |                126 | n/a              |
| Threshold rule (refill when Dr >= RAW, driest first) [truth ET +10 %]                                  | potato-south |       4430 |          0.67  |         28805 |            753 |                 98 | 0.648            |
| Threshold rule (refill when Dr >= RAW, driest first) [truth ET +10 %]                                  | tomato-east  |       5040 |          0.55  |         81306 |           1287 |                122 | 0.248            |
| Optimiser, persistence forecast [truth ET +10 %]                                                       | olive-north  |       9612 |          0.754 |         49613 |            268 |                114 | n/a              |
| Optimiser, persistence forecast [truth ET +10 %]                                                       | potato-south |       3420 |          0.581 |         37558 |            757 |                 78 | 0.617            |
| Optimiser, persistence forecast [truth ET +10 %]                                                       | tomato-east  |       2910 |          0.407 |        110236 |           1911 |                125 | 0.185            |

## How to read this

- `stress_mm_h`: sum over hours of depletion beyond RAW (mm·h). `severe_hours`: hours beyond
  RAW + 50 % of (TAW − RAW). For perennials, severe hours are the irreversibility proxy.
- `relative_yield`: FAO‑33 stage-wise Ya/Ym, only where every growth stage has a Ky and fell
  inside the period. Olive has no Ky in its profile, so its yield is not estimated.
- Crop parameters are international reference values (`needs_review`). Weights follow the
  default `PriorityPolicy` (perennial severe-stress multiplier 5, annual 1).

## Limitations

- Same model for planner and truth. Robustness is probed only through the ET bias and forecast mode.
- The farm is deliberately water-short (seasonal crop demand far exceeds the 120 m3/day well cap),
  so every policy causes stress. Differences show *how* scarcity is shared, not whether it is avoided.
- No rainfall forecast skill is modelled beyond perfect vs persistence.
- No sensor noise; no pump breakdowns; constant pump head.
- One location, one season, one hypothetical farm: not generalisable.
