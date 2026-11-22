"""LLM telemetry: event content, privacy and summary."""

import json

from qatra_ai.service import telemetry


def _rec(**kw):
    base = dict(
        farm_id="f1",
        language="fr",
        provider="gemini",
        model="gemini-3.5-flash-lite",
        verified=True,
        used_fallback=False,
        fallback_reason=None,
        violations=0,
        tool_calls=2,
        latency_s=12.0,
    )
    base.update(kw)
    return telemetry.record("assistant", **base)


def test_record_flags_model_switch_and_never_stores_text(monkeypatch):
    monkeypatch.setenv("QATRA_GEMINI_MODEL", "gemini-3.8-flash")
    ev = _rec()
    assert ev["configured_model"] == "gemini-3.8-flash" and ev["model_switched"] is True
    line = telemetry.telemetry_path().read_text(encoding="utf-8").strip().splitlines()[-1]
    assert set(json.loads(line)) == set(ev)  # no question/answer fields
    assert not {"question", "text", "answer"} & set(ev)


def test_summary_rates_and_latency(monkeypatch):
    monkeypatch.setenv("QATRA_GEMINI_MODEL", "gemini-3.8-flash")
    _rec(latency_s=10)
    _rec(model="gemini-3.8-flash", latency_s=20, violations=1)
    _rec(verified=False, used_fallback=True, fallback_reason="Gemini unavailable", latency_s=30)
    s = telemetry.summarize(telemetry.read_events())["by_kind"]["assistant"]
    assert s["requests"] == 3
    assert s["fallback_rate"] == round(1 / 3, 3) and s["rejected_drafts_rate"] == round(1 / 3, 3)
    assert s["model_switched_rate"] == round(2 / 3, 3)
    assert s["latency_s_p50"] == 20.0 and s["fallback_reasons"] == {"Gemini unavailable": 1}


def test_torn_line_is_skipped():
    _rec()
    with telemetry.telemetry_path().open("a", encoding="utf-8") as f:
        f.write('{"kind": "assis')
    assert len(telemetry.read_events()) == 1


def test_violation_rules_are_types_not_text():
    msgs = [
        "number '333' (volume) does not match any value in the cited tool results",
        "number '12' does not match any value in the cited tool results",
        "a sentence with numbers cites 3 results; cite the specific result (at most 2) for each",
        "market_trends[0]: https://x.example was not returned by web_search/web_fetch in this run",
    ]
    ev = _rec(violation_messages=msgs, violations=len(msgs))
    assert ev["violation_rules"] == sorted(
        [
            "number_not_in_results_with_unit",
            "number_not_in_results",
            "citation_breadth",
            "unretrieved_source",
        ]
    )
    assert "333" not in json.dumps(ev) and "x.example" not in json.dumps(ev)
