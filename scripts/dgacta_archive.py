"""Daily DGACTA archive entry point (run once per day or from a scheduler)."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ai_engine"))

from qatra_ai.data.sources.dgacta import archive


if __name__ == "__main__":
    runs = archive()
    failed = False
    for run in runs:
        if run.errors or run.files_seen == 0:
            failed = True
        if run.stale:
            print(
                f"ALERT {run.station}: stale publication "
                f"(lag {run.publication_lag_hours:.1f} hours)"
            )
        print(
            f"{run.station}: seen={run.files_seen} new={run.files_new} "
            f"rows={run.processed_rows} stale={run.stale}"
        )
    raise SystemExit(1 if failed else 0)
