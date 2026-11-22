# Grounding verifier stress test

> Deterministic test of `assistant/verifier.py`, **no LLM involved**. Synthetic one-sentence
> claims are checked against the real tool results of the demo farm on 2025-06-15 (real weather and
> soil, hypothetical farm). It measures the numeric safety net, not the assistant's answers.

- Tool results: list_decisions (r1), get_decision for the top package (r2), get_anomalies (r3),
  get_suitability (r4). Numeric values per result: {"r1": 11, "r2": 19, "r3": 208, "r4": 242}; 163 carry a known
  unit (from Quantity objects or key names).
- 2000 claims per case, seed 0. Claims quote values with their own unit, as real answers do.
  "Flagged" = the verifier rejects the answer (rewrite, then template fallback).
- Ideal: correct values flagged 0 %, wrong values flagged 100 %.
- `flagged_before` = the first verifier (2026-11-22), which pooled all citations of an answer,
  ignored units and did not parse `[r1, r2]`; empty where the case did not exist.

| citation                     | case                                       |   flagged_now |   flagged_before |
|:-----------------------------|:-------------------------------------------|--------------:|-----------------:|
| one result [r1]              | correct value, own unit (false-alarm rate) |         0     |            0     |
| one result [r1]              | invented decimal 11-500 m3                 |         0.992 |            0.986 |
| one result [r1]              | invented integer 11-999 m3                 |         0.999 |            0.99  |
| one result [r1]              | invented decimal 11-500, no unit           |         0.988 |          nan     |
| one result [r1]              | true value off by 2 %                      |         1     |          nan     |
| one result [r1]              | true value off by 5 %                      |         1     |          nan     |
| one result [r1]              | true value off by 10 %                     |         1     |          nan     |
| one result [r1]              | true value off by 25 %                     |         1     |          nan     |
| one result [r1]              | true value off by 50 %                     |         1     |          nan     |
| one result [r1]              | true number, wrong unit                    |         1     |          nan     |
| all 4 results                | correct value, own unit (false-alarm rate) |         1     |            0     |
| all 4 results                | invented decimal 11-500 m3                 |         1     |            0.848 |
| all 4 results                | invented integer 11-999 m3                 |         1     |            0.874 |
| all 4 results                | invented decimal 11-500, no unit           |         1     |          nan     |
| all 4 results                | true value off by 2 %                      |         1     |            0.694 |
| all 4 results                | true value off by 5 %                      |         1     |            0.805 |
| all 4 results                | true value off by 10 %                     |         1     |            0.784 |
| all 4 results                | true value off by 25 %                     |         1     |            0.731 |
| all 4 results                | true value off by 50 %                     |         1     |            0.596 |
| all 4 results                | true number, wrong unit                    |         1     |          nan     |
| two largest results [r3, r4] | correct value, own unit (false-alarm rate) |         0     |          nan     |
| two largest results [r3, r4] | invented decimal 11-500 m3                 |         0.918 |          nan     |
| two largest results [r3, r4] | invented integer 11-999 m3                 |         0.95  |          nan     |
| two largest results [r3, r4] | invented decimal 11-500, no unit           |         0.862 |          nan     |
| two largest results [r3, r4] | true value off by 2 %                      |         0.782 |          nan     |
| two largest results [r3, r4] | true value off by 5 %                      |         0.778 |          nan     |
| two largest results [r3, r4] | true value off by 10 %                     |         0.804 |          nan     |
| two largest results [r3, r4] | true value off by 25 %                     |         0.753 |          nan     |
| two largest results [r3, r4] | true value off by 50 %                     |         0.719 |          nan     |
| two largest results [r3, r4] | true number, wrong unit                    |         0.955 |          nan     |
| cites [r1], value from r3    | true value from an uncited result          |         0.974 |          nan     |
| any                          | invented small integer 0-10, no unit       |         0     |            0     |
| any                          | invented small integer 0-10 m3             |         0.698 |          nan     |
| no citation                  | correct value but no [rN]                  |         1     |          nan     |
| any                          | guarantee wording (en/fr/ar)               |         1     |          nan     |

## What changed (P0-2, 2026-11-22)

- Citations are scoped per claim (sentence, then line, paragraph, answer), so a number is only
  checked against the results cited next to it.
- `[r1, r2]` and `[r1][r2]` are parsed.
- Numbers written with a unit only match source values of the same unit kind (or of unknown
  kind); dates and clock times must appear whole; small integers with a unit are checked.

- A sentence with numbers may cite at most two results ("all 4 results" rows are now rejected
  by this rule, which is why they reach 100 %; the `[r3, r4]` rows show the honest residual).

## Remaining blind spots

- A sentence citing the **two largest results** still has a large pool (several hundred
  values); a nudged number then often lands within 1 % of some value. Untagged numbers (no unit
  in the answer or the source) are the weakest. Real answers so far cite small results.
- The check cannot tell **which** quantity of the same unit a number belongs to (the right
  volume attached to the wrong zone passes). Structured answers with field references would
  close this; the strategy agent's `immediate_actions` already restate engine fields.
- Small integers without a unit (counts, hours written as "6 hours") are not checked.
