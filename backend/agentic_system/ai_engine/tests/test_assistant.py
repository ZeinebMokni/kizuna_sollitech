"""Assistant tests with a FAKE LLM client (scripted responses): no network, no API cost.
They test the loop, the read-only tools, the grounding verifier and the fallbacks."""

import json
from datetime import date, datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from qatra_ai.agronomy.crops import get_crop
from qatra_ai.agronomy.soil import SoilWaterProperties
from qatra_ai.agronomy.water_balance import ZoneSetup
from qatra_ai.assistant.assistant import DEFAULT_MODEL, QatraAssistant, detect_language
from qatra_ai.assistant.tools import AssistantContext, ToolRegistry
from qatra_ai.assistant.verifier import verify
from qatra_ai.contracts import DataClass, Provenance
from qatra_ai.optimization.schedule_models import PumpSystem
from qatra_ai.orchestrator.decision import FarmContext, ZoneContext, decide

NS = SimpleNamespace
SOIL = SoilWaterProperties(
    theta_fc=0.28, theta_wp=0.155, data_class=DataClass.INFERRED, source="t", method="t"
)
PROV = Provenance(data_class=DataClass.INFERRED, source="water_balance", quality_grade="C")


@pytest.fixture(scope="module")
def context():
    zones = [
        ZoneContext(
            "tomato",
            ZoneSetup(
                crop=get_crop("tomato"),
                season_start=date(2026, 4, 1),
                soil=SOIL,
                area_ha=1.0,
                application_efficiency=0.9,
            ),
            10.0,
            30.0,
            PROV,
        ),
        ZoneContext(
            "citrus",
            ZoneSetup(
                crop=get_crop("citrus"),
                season_start=date(2026, 3, 1),
                soil=SOIL,
                area_ha=1.0,
                application_efficiency=0.9,
            ),
            10.0,
            0.0,
            PROV,
        ),
    ]
    as_of = datetime(2026, 6, 15)
    fc = pd.DataFrame(
        {"et0": 7.0, "precip": 0.0, "rs": 28.0},
        index=pd.date_range(as_of.date(), periods=5, freq="D"),
    )
    env = decide(
        FarmContext(
            farm_id="F1",
            as_of=as_of,
            zones=zones,
            forecast_daily=fc,
            forecast_source="synthetic",
            pump=PumpSystem(
                max_flow_m3h=12, max_simultaneous_zones=1, total_head_m=50, pump_efficiency=0.55
            ),
            grid_hours=frozenset(range(24)),
            grid_max_kw=20,
        )
    )
    return AssistantContext(decision=env)


def text(t):
    return NS(type="text", text=t)


def tool_use(name, inp, i="tu1"):
    return NS(type="tool_use", name=name, input=inp, id=i)


def msg(content, stop):
    return NS(content=content, stop_reason=stop, model=DEFAULT_MODEL)


class FakeClient:
    """Scripted model: each call pops the next response; records every request."""

    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        self.beta = NS(messages=NS(create=self._create))

    def _create(self, **kw):
        # snapshot: the caller keeps appending to the same messages list
        self.requests.append({**kw, "messages": list(kw["messages"])})
        step = self.script.pop(0)
        return step(kw) if callable(step) else step


def first_package(context):
    return context.decision.payload.packages[0]


def grounded_answer(context):
    p = first_package(context)
    return f"Priority 1: {p.action} {p.target} {p.amount.value} m3 [r1]. Needs your approval [r1]."


def test_grounded_answer_is_verified_and_request_shape(context):
    client = FakeClient(
        [
            msg([tool_use("list_decisions", {})], "tool_use"),
            msg([text(grounded_answer(context))], "end_turn"),
        ]
    )
    ans = QatraAssistant(context, client=client).ask("What should I do first?")
    assert ans.verified and not ans.used_fallback and ans.citations == ["r1"]
    req = client.requests[0]
    assert req["model"] == "claude-opus-5-5"
    assert req["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in req["betas"]
    assert req["output_config"] == {"effort": "medium"} and "tool_choice" not in req
    assert all(
        t["strict"] and t["input_schema"]["additionalProperties"] is False for t in req["tools"]
    )
    # Tool results are returned in one user turn, after the assistant turn with tool_use
    second = client.requests[1]["messages"]
    assert second[-1]["role"] == "user" and second[-1]["content"][0]["type"] == "tool_result"


def test_hallucinated_number_triggers_rewrite_then_passes(context):
    client = FakeClient(
        [
            msg([tool_use("list_decisions", {})], "tool_use"),
            msg([text("Irrigate the tomato with 999 m3 [r1].")], "end_turn"),
            msg([text(grounded_answer(context))], "end_turn"),
        ]
    )
    ans = QatraAssistant(context, client=client).ask("What should I do first?")
    assert ans.verified
    feedback = client.requests[2]["messages"][-1]["content"]
    assert "999" in feedback and "grounding check" in feedback


def test_two_failures_fall_back_to_template(context):
    bad = msg([text("Irrigate 999 m3 [r1].")], "end_turn")
    client = FakeClient([msg([tool_use("list_decisions", {})], "tool_use"), bad, bad])
    ans = QatraAssistant(context, client=client).ask("What should I do first?")
    assert ans.used_fallback and not ans.verified
    assert "failed grounding" in ans.fallback_reason and ans.violations
    assert first_package(context).target in ans.text  # template comes from engine data


def test_refusal_and_api_error_fall_back(context):
    ans = QatraAssistant(context, client=FakeClient([msg([], "refusal")])).ask("hello")
    assert ans.used_fallback and ans.fallback_reason == "model declined the request"

    def boom(_):
        raise RuntimeError("network down")

    ans2 = QatraAssistant(context, client=FakeClient([boom])).ask("hello")
    assert ans2.used_fallback and "API error" in ans2.fallback_reason


def test_tool_error_is_returned_as_error_result(context):
    client = FakeClient(
        [
            msg([tool_use("get_decision", {"package_id": "nope"})], "tool_use"),
            msg([text("QATRA has no package with that id.")], "end_turn"),
        ]
    )
    ans = QatraAssistant(context, client=client).ask("Explain package nope")
    result = client.requests[1]["messages"][-1]["content"][0]
    assert result["is_error"] and "valid ids" in result["content"]
    assert ans.verified and ans.tool_calls[0].error


def test_arabic_question_answer_and_template_language(context):
    p = first_package(context)
    arabic_digits = str(int(p.amount.value)).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))
    client = FakeClient(
        [
            msg([tool_use("list_decisions", {})], "tool_use"),
            msg([text(f"الأولوية: ري {p.target} بكمية {arabic_digits} م3 [r1]")], "end_turn"),
        ]
    )
    ans = QatraAssistant(context, client=client).ask("ماذا يجب أن أفعل أولاً؟")
    assert ans.language == "ar" and ans.verified
    fb = QatraAssistant(context, client=FakeClient([msg([], "refusal")])).ask("لماذا؟")
    assert fb.text.startswith("لم يتمكن")


def test_language_detection():
    assert detect_language("Pourquoi la zone tomate est prioritaire ?") == "fr"
    assert detect_language("Why is the tomato zone first?") == "en"
    assert detect_language("لماذا الطماطم أولاً؟") == "ar"


# --- verifier unit tests -------------------------------------------------------------------

RESULTS = {
    "r1": {"data": {"volume": 120.0, "ratio": 0.523, "note": "36 of 72 slots", "big": 11083.0}}
}


@pytest.mark.parametrize(
    "answer",
    [
        "Volume 120 m3 [r1]",
        "Volume 120,0 m3 [r1]",
        "yield 52 % [r1]",
        "yield 0.52 [r1]",
        "36 of 72 slots [r1]",
        "about 11 083 m3/ha [r1]",
        "11083 [r1]",
    ],
)
def test_verifier_accepts_grounded_forms(answer):
    assert verify(answer, RESULTS).ok


@pytest.mark.parametrize(
    "answer, reason",
    [
        ("Volume 150 m3 [r1]", "does not match"),
        ("Volume 120 m3", "cites no tool result"),
        ("Volume 120 m3 [r9]", "unknown result id"),
        ("This looks like water theft [r1]", "accusation"),
        ("Ceci est un vol d'eau [r1]", "accusation"),
        ("هذه سرقة مياه [r1]", "accusation"),
        ("We guarantee a full harvest [r1]", "guarantee"),
    ],
)
def test_verifier_rejects(answer, reason):
    res = verify(answer, RESULTS)
    assert not res.ok and any(reason in v for v in res.violations)


def test_numbers_from_question_and_small_counts_allowed():
    assert verify(
        "For your 250 m3 question: 3 zones are listed [r1].", RESULTS, question="Is 250 m3 enough?"
    ).ok


def test_registry_is_read_only_and_ids_sequential(context):
    reg = ToolRegistry(context)
    a = json.loads(reg.call("list_decisions", {}))
    b = json.loads(reg.call("get_crop_profile", {"crop_code": "olive"}))
    assert (a["result_id"], b["result_id"]) == ("r1", "r2")
    assert not any(
        n.startswith(("set_", "write", "execute", "irrigate"))
        for n in dir(reg)
        if n.startswith("_t_")
    )


def test_market_tool_returns_ranges_and_disclaimer():
    from test_market import request as market_request

    from qatra_ai.assistant.tools import ToolError
    from qatra_ai.market import market_outlook

    reg = ToolRegistry(AssistantContext(market=[market_outlook(market_request())]))
    out = json.loads(reg.call("get_market_outlook", {"crop_code": "tomato"}))
    o = out["data"]["outlooks"][0]
    assert o["confidence"] == "low" and o["scenario_kind"] == "hypothetical"
    assert o["adoption"][0]["price"]["interval_kind"] == "quantile_10_90"
    assert any("never as expected or guaranteed" in n for n in out["notes"])
    assert out["data_class"] == "simulated" and "SIMULATED" in out["notes"][0]
    with pytest.raises(ToolError):
        reg.call("get_market_outlook", {"crop_code": "olive"})
    with pytest.raises(ToolError):
        ToolRegistry(AssistantContext()).call("get_market_outlook", {"crop_code": ""})


def test_every_tool_result_states_its_data_class(context):
    """P0-1 (evaluation 2026-11-22): the model must always know where data comes from."""
    from qatra_ai.assistant.tools import TOOL_DEFINITIONS, ToolError
    from qatra_ai.contracts import DataClass
    from qatra_ai.predictive.anomaly import AnomalyEvent

    ev = AnomalyEvent(
        kind="slow_leak",
        start=datetime(2026, 6, 1),
        end=datetime(2026, 6, 2),
        detected_at=datetime(2026, 6, 1, 12),
        hours=24,
        estimated_volume_m3=5.0,
        severity="low",
        confidence="low",
        hypotheses=[],
        recommended_checks=[],
    )
    ctx = AssistantContext(
        decision=context.decision,
        anomalies=[ev],
        anomalies_data_class=DataClass.SIMULATED,
    )
    reg = ToolRegistry(ctx)
    pid = context.decision.payload.packages[0].package_id
    args = {
        "list_decisions": {},
        "get_decision": {"package_id": pid},
        "compare_priority": {"package_a": pid, "package_b": pid},
        "get_crop_profile": {"crop_code": "tomato"},
        "get_anomalies": {},
    }
    for t in TOOL_DEFINITIONS:
        if t["name"] not in args:
            with pytest.raises(ToolError):  # no data in this context: refused, not empty
                reg.call(t["name"], {"crop_code": ""} if t["input_schema"]["required"] else {})
            continue
        out = json.loads(reg.call(t["name"], args[t["name"]]))
        assert out["data_class"] and out["data_class"] != "unknown", t["name"]
    anomalies = json.loads(reg.call("get_anomalies", {}))
    assert anomalies["data_class"] == "simulated"
    assert "SIMULATED" in anomalies["notes"][0] and "never describe" in anomalies["notes"][0]
    crop = json.loads(reg.call("get_crop_profile", {"crop_code": "tomato"}))
    assert crop["data_class"] == "literature_reference"


def test_unknown_origin_is_flagged(context):
    reg = ToolRegistry(AssistantContext(anomalies=[]))  # origin not given
    out = json.loads(reg.call("get_anomalies", {}))
    assert out["data_class"] == "unknown" and "not stated" in out["notes"][0]


# --- verifier: per-claim scoping, combined citations, units, dates (P0-2) -------------------

SCOPED = {
    "r1": {"data": {"amount": {"value": 120.0, "unit": "m3"}, "window": "2025-06-15T00:00/16:00"}},
    "r2": {"data": {"depletion_mm": 64.89, "raw_mm": 21.7, "hours": [333.0, 47.0]}},
}


@pytest.mark.parametrize(
    "answer",
    [
        "Irrigate 120 m3 [r1, r2].",
        "Irrigate 120 m³ [r1;r2]. Depletion is 64.89 mm against 21.7 mm [r2].",
        "Irrigate 120 m3 [r1][r2].",
        "Window: 2025-06-15 from 00:00 to 16:00 [r1].",
        "Irrigate 120 m3.\n- details [r1]",  # sentence without citation -> its line/paragraph
        "Depletion 64.89 ملم [r2].",
    ],
)
def test_verifier_scoped_forms_accepted(answer):
    res = verify(answer, SCOPED)
    assert res.ok, res.violations


@pytest.mark.parametrize(
    "answer, reason",
    [
        # 333 exists in r2 but the sentence cites only r1
        ("Irrigate 333 m3 [r1]. Depletion 64.89 mm [r2].", "333"),
        # 120 exists, but as m3: written as mm it is a different quantity
        ("Depletion is 120 mm [r1, r2].", "(depth)"),
        ("Window 2025-06-16 [r1].", "date '2025-06-16'"),
        ("Start at 07:00 [r1].", "time '07:00'"),
        ("Irrigate 6 m3 [r1].", "'6' (volume)"),  # small int with a unit is checked
        ("Irrigate 120 m3 [r1, r9].", "unknown result id [r9]"),
    ],
)
def test_verifier_scoped_rejections(answer, reason):
    res = verify(answer, SCOPED)
    assert not res.ok and any(reason in v for v in res.violations), res.violations


def test_combined_citation_alone_is_a_citation():
    res = verify("Irrigate 120 m3 [r1, r2].", SCOPED)
    assert res.ok and res.citations == ["r1", "r2"]


def test_quantity_like_objects_keep_their_text_fields():
    """Regression (replay of a live Arabic answer): suitability factors have value+unit AND
    rule/note strings; numbers in those strings must stay available."""
    res = {
        "r1": {
            "data": [
                {
                    "factor": "water",
                    "value": 0.523,
                    "unit": "relative yield",
                    "note": "available 6000 vs required 11083 m3/ha (P80)",
                    "rule": "Tmax > 35.0 C",
                }
            ]
        }
    }
    assert verify("المتوفر 6000 متر مكعب/هكتار مقابل 11083 [r1]، 52.3% [r1]، 35 [r1].", res).ok


def test_numeric_sentence_may_not_cite_many_results():
    res = {f"r{i}": {"data": {"v": 120.0}} for i in range(1, 4)}
    assert verify("Irrigate 120 m3 [r1, r2].", res).ok
    bad = verify("Irrigate 120 m3 [r1, r2, r3].", res)
    assert not bad.ok and any("cites 3 results" in v for v in bad.violations)
    assert verify("See results [r1, r2, r3].", res).ok  # no numbers: no limit
