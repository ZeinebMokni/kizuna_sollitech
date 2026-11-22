"""LLM telemetry: one JSON line per assistant / strategy request, plus a summary.

Recorded: kind, farm id, language, provider, configured vs served model, verified, fallback
and reason, verifier violation count and rule types, tool calls, latency, web research status.
Never recorded: the question or answer text (they can contain farm details).

File: $QATRA_TELEMETRY_PATH, default <data root>/telemetry/llm_events.jsonl (git-ignored).
Added after the 2026-11-22 evaluation, which found the served model silently differing from the
configured one and no way to see fallback or rejection rates.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from qatra_ai.assistant.backends import ANTHROPIC_MODEL, GEMINI_DEFAULT_MODEL
from qatra_ai.data.store import data_root

log = logging.getLogger("qatra.llm")
_lock = threading.Lock()


def telemetry_path() -> Path:
    env = os.environ.get("QATRA_TELEMETRY_PATH")
    return Path(env) if env else data_root() / "telemetry" / "llm_events.jsonl"


def configured_model(provider: str | None) -> str | None:
    if provider == "gemini":
        return os.environ.get("QATRA_GEMINI_MODEL", GEMINI_DEFAULT_MODEL)
    if provider == "anthropic":
        return ANTHROPIC_MODEL
    return None


RULES = (  # violation message fragment -> rule type (no numbers or text are stored)
    ("cites unknown result", "unknown_result_id"),
    ("cites no tool result", "no_citation"),
    ("results; cite the specific", "citation_breadth"),
    ("date ", "date_not_in_results"),
    ("time ", "time_not_in_results"),
    ("forbidden accusation", "accusation_wording"),
    ("forbidden guarantee", "guarantee_wording"),
    ("does not match", "number_not_in_results"),
    ("was not returned by web", "unretrieved_source"),
    ("not an engine decision target", "invented_action_target"),
    ("guarantee language", "guarantee_wording"),
    ("schema:", "schema"),
)


def rule_types(violations: list[str]) -> list[str]:
    out = []
    for v in violations:
        kind = next((k for frag, k in RULES if frag in v), "other")
        if kind == "number_not_in_results" and re.search(r"\(\w+\) does not match", v):
            kind = "number_not_in_results_with_unit"
        out.append(kind)
    return sorted(out)


def record(
    kind: str,
    *,
    farm_id: str,
    language: str | None,
    provider: str | None,
    model: str | None,
    verified: bool,
    used_fallback: bool,
    fallback_reason: str | None,
    violations: int,
    tool_calls: int,
    latency_s: float,
    web_research: str | None = None,
    violation_messages: list[str] | None = None,
) -> dict[str, Any]:
    configured = configured_model(provider)
    event = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "kind": kind,
        "farm_id": farm_id,
        "language": language,
        "provider": provider,
        "configured_model": configured,
        "served_model": model,
        "model_switched": bool(model and configured and model != configured),
        "verified": verified,
        "used_fallback": used_fallback,
        "fallback_reason": fallback_reason,
        "violations": violations,
        "violation_rules": rule_types(violation_messages or []),
        "tool_calls": tool_calls,
        "latency_s": round(latency_s, 2),
        "web_research": web_research,
    }
    log.info(json.dumps(event, ensure_ascii=False))
    path = telemetry_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _lock, path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError as exc:  # telemetry must never break a request
        log.warning("telemetry write failed: %s", exc)
    return event


def read_events(path: Path | None = None) -> list[dict]:
    path = path or telemetry_path()
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # a torn line must not hide the rest
    return events


def summarize(events: list[dict]) -> dict[str, Any]:
    out: dict[str, Any] = {"events": len(events), "by_kind": {}}
    for kind in sorted({e["kind"] for e in events}):
        ev = [e for e in events if e["kind"] == kind]
        lat = np.array([e["latency_s"] for e in ev], dtype=float)
        n = len(ev)
        out["by_kind"][kind] = {
            "requests": n,
            "verified_rate": round(sum(e["verified"] for e in ev) / n, 3),
            "fallback_rate": round(sum(e["used_fallback"] for e in ev) / n, 3),
            "rejected_drafts_rate": round(sum(e["violations"] > 0 for e in ev) / n, 3),
            "model_switched_rate": round(sum(e["model_switched"] for e in ev) / n, 3),
            "served_models": dict(Counter(e["served_model"] or "none" for e in ev)),
            "violation_rules": dict(
                Counter(r for e in ev for r in e.get("violation_rules", [])).most_common()
            ),
            "fallback_reasons": dict(
                Counter(e["fallback_reason"] for e in ev if e["fallback_reason"]).most_common(5)
            ),
            "latency_s_p50": round(float(np.percentile(lat, 50)), 1),
            "latency_s_p95": round(float(np.percentile(lat, 95)), 1),
            "first_ts": ev[0]["ts"],
            "last_ts": ev[-1]["ts"],
        }
    return out
