"""Live evaluation of the explainable assistant on the configured LLM (quota/billed calls).

Asks a fixed battery of farmer questions (en/fr/ar) about the demo farm through the API and
records: verified by the grounding check, fallback used and why, latency, tools called.
Output: docs/evaluation/assistant_live_<provider>.md (answers included for human review).

    uv run --env-file ../.env python examples/eval_assistant_live.py
"""

from __future__ import annotations

import os
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from qatra_ai.service.app import create_app

sys.stdout.reconfigure(encoding="utf-8")
QUESTIONS = [
    ("en", "What should I do first today, and why?"),
    ("en", "Why is the tomato zone ranked above the potato zone?"),
    ("fr", "Combien d'eau faut-il pour la zone tomate et quand ?"),
    ("fr", "Y a-t-il une fuite ou une anomalie sur mon réseau ?"),
    ("ar", "ما هي أولوية الري اليوم ولماذا؟"),
    ("ar", "هل الطماطم مناسبة لمزرعتي؟"),
]


def main() -> None:
    client = TestClient(create_app())
    rows, answers = [], []
    for lang, q in QUESTIONS:
        t0 = time.perf_counter()
        r = client.post("/api/farms/demo-farm/assistant", json={"question": q})
        dt = time.perf_counter() - t0
        d = r.json()["data"]
        rows.append(
            {
                "lang": lang,
                "question": q,
                "verified": d["verified"],
                "fallback": d["used_fallback"],
                "fallback_reason": d["fallback_reason"] or "",
                "violations": len(d["violations"]),
                "tools": ", ".join(d["tool_calls"]),
                "latency_s": round(dt, 1),
                "model": d["model"] or "",
            }
        )
        answers.append((lang, q, d["text"], d["violations"]))
        print(f"[{lang}] verified={d['verified']} fallback={d['used_fallback']} {dt:.1f}s")
    df = pd.DataFrame(rows)
    provider = os.environ.get("QATRA_LLM_PROVIDER", "auto")
    n = len(df)
    summary = (
        f"- Questions: {n} (2 per language). Verified by the grounding check: "
        f"{int(df.verified.sum())}/{n}. Template fallback: {int(df.fallback.sum())}/{n}.\n"
        f"- Median latency {df.latency_s.median():.1f} s (max {df.latency_s.max():.1f} s)."
    )
    body = "\n\n".join(
        f"### [{lang}] {q}\n\n{text}\n\n_violations:_ {v or 'none'}" for lang, q, text, v in answers
    )
    md = f"""# Assistant live evaluation ({provider}, {date.today()})

> Live calls to the configured LLM on the demo farm (real weather/soil, hypothetical farm).
> {n} questions is a smoke test, not a statistically meaningful evaluation. Answers are shown
> for human review: the grounding check verifies numbers and citations, not usefulness.

{summary}

{df.drop(columns=["question"]).assign(q=[q[:45] for _, q in QUESTIONS]).to_markdown(index=False)}

## Answers

{body}
"""
    out = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "evaluation"
        / f"assistant_live_{provider}.md"
    )
    out.write_text(md, encoding="utf-8")
    print(summary)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
