"""Score anomaly detectors on SYNTHETIC labelled faults (simulation-tested only).

A fault counts as detected if an event of one of its `detectable_by` kinds overlaps the
fault window extended by `grace_h` hours. Time-to-detect = first such event's detected_at
minus the fault start. A false alarm is any event that overlaps no (extended) fault window.
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from qatra_ai.evaluation.synthetic_water import ALL_FAULTS, SyntheticSystem, generate
from qatra_ai.predictive.anomaly import DetectionResult, DetectorConfig, detect_anomalies


def score(
    system: SyntheticSystem, result: DetectionResult, grace_h: int = 24
) -> tuple[list[dict], int]:
    grace = pd.Timedelta(hours=grace_h)
    rows = []
    matched: set[int] = set()
    for f in system.faults:
        hits = []
        for i, e in enumerate(result.events):
            overlaps = e.start <= f.end + grace and e.end >= f.start
            if overlaps:
                matched.add(i)
                if e.kind in f.detectable_by:
                    hits.append(e)
        first = min(hits, key=lambda e: e.detected_at) if hits else None
        rows.append(
            {
                "fault": f.name,
                "detected": first is not None,
                "ttd_h": None
                if first is None
                else max(0.0, (pd.Timestamp(first.detected_at) - f.start).total_seconds() / 3600),
                "kinds": sorted({e.kind for e in hits}),
            }
        )
    false_alarms = sum(1 for i in range(len(result.events)) if i not in matched)
    return rows, false_alarms


def run_benchmark(
    seeds: Iterable[int] = range(20),
    days: int = 42,
    faults: tuple[str, ...] = ALL_FAULTS,
    cfg_overrides: dict | None = None,
    gen_kwargs: dict | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (per-fault summary, false-alarm summary)."""
    fault_rows, fa_rows = [], []
    for seed in seeds:
        for label, fset in (("with faults", faults), ("clean", ())):
            sysd = generate(days=days, seed=seed, faults=fset, **(gen_kwargs or {}))
            cfg = DetectorConfig(design_flow_m3h=sysd.design_flow_m3h, **(cfg_overrides or {}))
            res = detect_anomalies(sysd.data, sysd.schedule, cfg)
            rows, fa = score(sysd, res)
            eval_weeks = (days - cfg.train_days) / 7
            fa_rows.append(
                {"run": label, "seed": seed, "false_alarms": fa, "per_week": fa / eval_weeks}
            )
            for r in rows:
                fault_rows.append({**r, "seed": seed})
    df = pd.DataFrame(fault_rows)
    summary = (
        df.groupby("fault", sort=False)
        .agg(
            detection_rate=("detected", "mean"),
            median_ttd_h=("ttd_h", "median"),
            max_ttd_h=("ttd_h", "max"),
            runs=("detected", "size"),
        )
        .reset_index()
    )
    fa = (
        pd.DataFrame(fa_rows)
        .groupby("run")
        .agg(
            runs=("seed", "size"),
            total_false_alarms=("false_alarms", "sum"),
            mean_per_week=("per_week", "mean"),
        )
        .reset_index()
    )
    return summary, fa
