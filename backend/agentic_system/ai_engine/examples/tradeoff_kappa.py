"""Trade-off curve: perennial protection vs annual-crop yield, as a function of the optimiser's
irreversibility weight (kappa_perennial). Same real weather/soil and hypothetical farm as
benchmark_scheduler.py; persistence forecasts. Simulation only (same model for planner and truth).

Appends a section to docs/evaluation/scheduler_closed_loop_2025.md.
Usage: uv run python examples/tradeoff_kappa.py   (~10 min per kappa value)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from benchmark_scheduler import END, REPORT, START, build_inputs  # noqa: E402

from qatra_ai.evaluation.closed_loop import optimizer_policy, run_policy, summarise  # noqa: E402
from qatra_ai.optimization.schedule_models import PriorityPolicy  # noqa: E402

KAPPAS = [1.0, 2.0, 5.0, 10.0]


def main() -> None:
    _, w, _, farm = build_inputs()
    rows = []
    for k in KAPPAS:
        pol = optimizer_policy(
            policy_weights=PriorityPolicy(kappa_perennial=k),
            mip_relative_gap=1e-3,
            time_limit_s=10,
        )
        run = run_policy(pol, farm, w, START, END, forecast_mode="persistence")
        s = summarise(run, farm).set_index("zone")
        rows.append(
            {
                "kappa_perennial": k,
                "water_m3": round(s["water_m3"].sum()),
                "total_stress_mm_h": round(s["stress_mm_h"].sum()),
                "olive_severe_hours": int(s.loc["olive-north", "severe_hours"]),
                "olive_eta_over_etc": round(s.loc["olive-north", "eta_over_etc"], 3),
                "tomato_relative_yield": round(s.loc["tomato-east", "relative_yield"], 3),
                "potato_relative_yield": round(s.loc["potato-south", "relative_yield"], 3),
            }
        )
        print(rows[-1], flush=True)
    table = pd.DataFrame(rows)
    text = REPORT.read_text(encoding="utf-8")
    marker = "\n## Trade-off: irreversibility weight"
    if marker in text:
        text = text[: text.index(marker)]
    text += f"""
## Trade-off: irreversibility weight (kappa_perennial)

Optimiser with persistence forecasts; only the perennial severe-stress multiplier changes
(annual multiplier stays 1). Each row is one full-season closed-loop simulation.

{table.to_markdown(index=False)}

Choosing a point on this curve is a value judgement about protecting long-lived trees versus
this season's annual harvest. It belongs to the farmer or water authority, not to QATRA.
"""
    REPORT.write_text(text, encoding="utf-8")
    print(f"Appended to {REPORT}")


if __name__ == "__main__":
    main()
