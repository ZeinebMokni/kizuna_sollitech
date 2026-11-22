"""Stress test of the assistant's deterministic grounding verifier (no LLM calls).

The verifier is the safety net between the LLM and the farmer: an answer whose numbers are not
found in the cited tool results is rewritten or replaced. This measures how often it catches
wrong numbers, on the real tool results of the demo farm (real weather/soil, hypothetical farm).

Claims are synthetic one-sentence answers written with the unit of the value they quote
("... is 64.9 mm [r2]"), so this measures the numeric check only, not language understanding.
Output: docs/evaluation/grounding_verifier_stress.md

    uv run python examples/eval_grounding_verifier.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from qatra_ai.assistant import verifier as ver
from qatra_ai.assistant.tools import AssistantContext, ToolRegistry
from qatra_ai.contracts import DataClass
from qatra_ai.farms.registry import PACKAGE_FARMS_DIR, load_registry
from qatra_ai.service.data import PublicDataProvider
from qatra_ai.service.runtime import FarmRuntime

OUT = Path(__file__).resolve().parents[2] / "docs" / "evaluation" / "grounding_verifier_stress.md"
N = 2000
UNIT = {
    "volume": "m3",
    "depth": "mm",
    "depth_time": "mm·h",
    "energy": "kWh",
    "percent": "%",
    "area": "ha",
    "temperature": "°C",
    None: "",
}
# flagged rates of the first verifier (measured 2026-11-22, before per-claim scoping,
# combined citations and units), for the cases that exist in both versions
BEFORE = {
    ("one result [r1]", "correct value, own unit (false-alarm rate)"): 0.000,
    ("one result [r1]", "invented decimal 11-500 m3"): 0.986,
    ("one result [r1]", "invented integer 11-999 m3"): 0.990,
    ("all 4 results", "correct value, own unit (false-alarm rate)"): 0.000,
    ("all 4 results", "invented decimal 11-500 m3"): 0.848,
    ("all 4 results", "invented integer 11-999 m3"): 0.874,
    ("all 4 results", "true value off by 2 %"): 0.694,
    ("all 4 results", "true value off by 5 %"): 0.805,
    ("all 4 results", "true value off by 10 %"): 0.784,
    ("all 4 results", "true value off by 25 %"): 0.731,
    ("all 4 results", "true value off by 50 %"): 0.596,
    ("any", "invented small integer 0-10, no unit"): 0.000,
}
rng = np.random.default_rng(0)


def fmt(v: float) -> str:
    return f"{v:.0f}" if abs(v) >= 100 else f"{v:.1f}"


def claim(v: float, fam: str | None, cite: str) -> str:
    unit = UNIT[fam]
    return f"The engine reports {fmt(v)}{' ' + unit if unit else ''} for this zone {cite}."


def rate(texts: list[str], results: dict) -> float:
    return float(np.mean([not ver.verify(t, results).ok for t in texts]))


def main() -> None:
    profile = load_registry([PACKAGE_FARMS_DIR]).get("demo-farm")
    rt = FarmRuntime(profile, PublicDataProvider())
    day = rt.valid_day(None)
    env = rt.decision(day)
    suit, wd = rt.suitability
    ctx = AssistantContext(
        decision=env,
        suitability=suit,
        suitability_data_class=wd.data_class,
        anomalies=rt.anomalies[1].events,
        anomalies_data_class=DataClass.SIMULATED,
    )
    reg = ToolRegistry(ctx)
    reg.call("list_decisions", {})
    reg.call("get_decision", {"package_id": env.payload.packages[0].package_id})
    reg.call("get_anomalies", {})
    reg.call("get_suitability", {"crop_code": ""})
    results = reg.results
    pools: dict[str, list] = {}
    for rid, res in results.items():
        p = ver._Pool()
        ver._collect(res["data"], p)
        pools[rid] = [(s.value, s.family) for s in p.numbers]
    all_ids = "[" + ", ".join(results) + "]"
    sizes = {rid: len(v) for rid, v in pools.items()}
    tagged = sum(1 for v in pools.values() for _, f in v if f is not None)

    rows = []
    for label, cite, rids in (
        ("one result [r1]", "[r1]", ["r1"]),
        ("all 4 results", all_ids, list(results)),
        ("two largest results [r3, r4]", "[r3, r4]", ["r3", "r4"]),
    ):
        picks = [(v, f) for r in rids for v, f in pools[r] if abs(v) > 10]
        idx = rng.integers(0, len(picks), N)
        correct = [picks[i] for i in idx]
        rows.append(
            (
                label,
                "correct value, own unit (false-alarm rate)",
                rate([claim(v, f, cite) for v, f in correct], results),
            )
        )
        rows.append(
            (
                label,
                "invented decimal 11-500 m3",
                rate([claim(v, "volume", cite) for v in rng.uniform(11, 500, N)], results),
            )
        )
        rows.append(
            (
                label,
                "invented integer 11-999 m3",
                rate([f"About {int(v)} m3 {cite}." for v in rng.integers(11, 1000, N)], results),
            )
        )
        rows.append(
            (
                label,
                "invented decimal 11-500, no unit",
                rate([claim(v, None, cite) for v in rng.uniform(11, 500, N)], results),
            )
        )
        for pct in (2, 5, 10, 25, 50):
            sign = rng.choice([-1, 1], N)
            pert = [(v * (1 + s * pct / 100), f) for (v, f), s in zip(correct, sign, strict=True)]
            rows.append(
                (
                    label,
                    f"true value off by {pct} %",
                    rate([claim(v, f, cite) for v, f in pert], results),
                )
            )
        wrong_unit = [
            (v, next(u for u in ("volume", "depth", "energy") if u != f))
            for v, f in correct
            if f is not None and f != "percent"
        ]
        if wrong_unit:
            rows.append(
                (
                    label,
                    "true number, wrong unit",
                    rate([claim(v, f, cite) for v, f in wrong_unit], results),
                )
            )
    # a value that exists only in another result than the one cited
    other = [
        v
        for v, _ in pools["r3"]
        if abs(v) > 10 and all(abs(v - w) > 0.01 * abs(v) for w, _ in pools["r1"])
    ]
    rows.append(
        (
            "cites [r1], value from r3",
            "true value from an uncited result",
            rate([claim(other[i], None, "[r1]") for i in rng.integers(0, len(other), N)], results),
        )
    )
    rows.append(
        (
            "any",
            "invented small integer 0-10, no unit",
            rate([f"Irrigate {int(v)} hours [r1]." for v in rng.integers(0, 11, N)], results),
        )
    )
    rows.append(
        (
            "any",
            "invented small integer 0-10 m3",
            rate([f"Irrigate {int(v)} m3 [r1]." for v in rng.integers(1, 11, N)], results),
        )
    )
    rows.append(
        (
            "no citation",
            "correct value but no [rN]",
            rate([f"The engine reports {fmt(v)}." for v, _ in correct], results),
        )
    )
    guar = ["Yields are guaranteed [r1].", "Le rendement est garanti [r1].", "المحصول مضمون [r1]."]
    rows.append(("any", "guarantee wording (en/fr/ar)", rate(guar, results)))

    df = pd.DataFrame(rows, columns=["citation", "case", "flagged_now"])
    df["flagged_before"] = [BEFORE.get((c, k)) for c, k, _ in rows]
    df["flagged_now"] = df.flagged_now.round(3)
    md = f"""# Grounding verifier stress test

> Deterministic test of `assistant/verifier.py`, **no LLM involved**. Synthetic one-sentence
> claims are checked against the real tool results of the demo farm on {day} (real weather and
> soil, hypothetical farm). It measures the numeric safety net, not the assistant's answers.

- Tool results: list_decisions (r1), get_decision for the top package (r2), get_anomalies (r3),
  get_suitability (r4). Numeric values per result: {json.dumps(sizes)}; {tagged} carry a known
  unit (from Quantity objects or key names).
- {N} claims per case, seed 0. Claims quote values with their own unit, as real answers do.
  "Flagged" = the verifier rejects the answer (rewrite, then template fallback).
- Ideal: correct values flagged 0 %, wrong values flagged 100 %.
- `flagged_before` = the first verifier (2026-11-22), which pooled all citations of an answer,
  ignored units and did not parse `[r1, r2]`; empty where the case did not exist.

{df.to_markdown(index=False)}

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
"""
    OUT.write_text(md, encoding="utf-8")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
