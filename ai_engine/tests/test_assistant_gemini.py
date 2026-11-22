"""Gemini backend tests with a FAKE client returning real google-genai types (no network)."""

from datetime import date, datetime
from types import SimpleNamespace

import pandas as pd
import pytest
from google.genai import types

from qatra_ai.agronomy.crops import get_crop
from qatra_ai.agronomy.soil import SoilWaterProperties
from qatra_ai.agronomy.water_balance import ZoneSetup
from qatra_ai.assistant.assistant import QatraAssistant
from qatra_ai.assistant.backends import (
    GEMINI_DEFAULT_MODEL,
    AnthropicBackend,
    GeminiBackend,
    make_backend,
)
from qatra_ai.assistant.tools import AssistantContext
from qatra_ai.contracts import DataClass, Provenance
from qatra_ai.optimization.schedule_models import PumpSystem
from qatra_ai.orchestrator.decision import FarmContext, ZoneContext, decide

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
        )
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


def response(parts=None, finish="STOP", candidates=True, block=None):
    if not candidates:
        return types.GenerateContentResponse(
            candidates=[],
            prompt_feedback=types.GenerateContentResponsePromptFeedback(block_reason=block),
        )
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=parts or []),
                finish_reason=types.FinishReason[finish],
            )
        ]
    )


def call(name, args, cid="fc-1", signature=None):
    return types.Part(
        function_call=types.FunctionCall(name=name, args=args, id=cid), thought_signature=signature
    )


class FakeGemini:
    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        self.models = SimpleNamespace(generate_content=self._generate)

    def _generate(self, model, contents, config):
        self.requests.append({"model": model, "contents": list(contents), "config": config})
        return self.script.pop(0)


def grounded(context):
    p = context.decision.payload.packages[0]
    return f"First: {p.action} {p.target} {p.amount.value} m3 [r1]. Needs your approval [r1]."


def test_gemini_tool_loop_verified_and_request_shape(context):
    fake = FakeGemini(
        [
            response([call("list_decisions", {}, signature=b"sig")]),
            response([types.Part(text=grounded(context))]),
        ]
    )
    ans = QatraAssistant(context, backend=GeminiBackend(client=fake)).ask("What first?")
    assert ans.verified and ans.provider == "gemini" and ans.model == GEMINI_DEFAULT_MODEL
    cfg = fake.requests[0]["config"]
    assert cfg.automatic_function_calling.disable is True  # QATRA runs every tool itself
    names = {d.name for d in cfg.tools[0].function_declarations}
    assert {"list_decisions", "get_decision", "compare_priority"} <= names
    assert "QATRA assistant" in cfg.system_instruction
    second = fake.requests[1]["contents"]
    model_turn, tool_turn = second[1], second[2]
    assert model_turn.parts[0].thought_signature == b"sig"  # model turn kept unchanged
    fr = tool_turn.parts[0].function_response
    assert fr.id == "fc-1" and fr.name == "list_decisions"
    assert fr.response["output"]["result_id"] == "r1"


def test_gemini_rewrite_after_failed_grounding(context):
    fake = FakeGemini(
        [
            response([call("list_decisions", {})]),
            response([types.Part(text="Irrigate 999 m3 [r1].")]),
            response([types.Part(text=grounded(context))]),
        ]
    )
    ans = QatraAssistant(context, backend=GeminiBackend(client=fake)).ask("What first?")
    assert ans.verified
    assert "999" in fake.requests[2]["contents"][-1].parts[0].text


def test_gemini_safety_and_blocked_prompt_fall_back(context):
    a = QatraAssistant(
        context, backend=GeminiBackend(client=FakeGemini([response(finish="SAFETY")]))
    ).ask("hello there")
    assert a.used_fallback and "SAFETY" in a.fallback_reason
    b = QatraAssistant(
        context,
        backend=GeminiBackend(
            client=FakeGemini([response(candidates=False, block=types.BlockedReason.SAFETY)])
        ),
    ).ask("hello there")
    assert b.used_fallback and b.fallback_reason.startswith("model declined")


def test_gemini_tool_error_returned_as_error(context):
    fake = FakeGemini(
        [
            response([call("get_decision", {"package_id": "nope"})]),
            response([types.Part(text="QATRA has no package with that id.")]),
        ]
    )
    ans = QatraAssistant(context, backend=GeminiBackend(client=fake)).ask("Explain nope")
    fr = fake.requests[1]["contents"][-1].parts[0].function_response
    assert "error" in fr.response and "valid ids" in fr.response["error"]
    assert ans.verified and ans.tool_calls[0].error


def test_missing_gemini_key_gives_clear_fallback(context, monkeypatch):
    for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI"):
        monkeypatch.delenv(var, raising=False)
    ans = QatraAssistant(context, backend=GeminiBackend()).ask("What first?")
    assert ans.used_fallback and "Gemini API key" in ans.fallback_reason


def test_provider_selection(monkeypatch):
    for var in ("QATRA_LLM_PROVIDER", "GEMINI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    assert isinstance(make_backend(), AnthropicBackend)
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    assert isinstance(make_backend(), GeminiBackend)  # only a Gemini key -> Gemini
    monkeypatch.setenv("ANTHROPIC_API_KEY", "y")
    assert isinstance(make_backend(), AnthropicBackend)
    monkeypatch.setenv("QATRA_LLM_PROVIDER", "gemini")
    assert isinstance(make_backend(), GeminiBackend)  # explicit setting wins
    monkeypatch.setenv("QATRA_GEMINI_MODEL", "gemini-test-model")
    assert make_backend().model == "gemini-test-model"
    monkeypatch.setenv("QATRA_LLM_PROVIDER", "other")
    with pytest.raises(ValueError, match="unknown"):
        make_backend()


# --- Transient errors, fallback models, clear failures -------------------------------------

from google.genai import errors  # noqa: E402


def _overloaded():
    return errors.ServerError(
        503, {"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}}
    )


class ScriptedGemini(FakeGemini):
    """Items may be exceptions (raised) or responses; records the model used per call."""

    def _generate(self, model, contents, config):
        self.requests.append({"model": model, "contents": list(contents), "config": config})
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_overloaded_model_falls_back_and_then_stays_fixed(context):
    fake = ScriptedGemini(
        [
            _overloaded(),
            _overloaded(),  # primary: 2 attempts
            response([call("list_decisions", {})]),  # fallback answers
            response([types.Part(text=grounded(context))]),
        ]
    )
    backend = GeminiBackend(
        client=fake, model="primary-model", fallback_models=["backup-model"], retry_delay_s=0
    )
    ans = QatraAssistant(context, backend=backend).ask("What first?")
    assert ans.verified and ans.model == "backup-model"
    assert [r["model"] for r in fake.requests] == [
        "primary-model",
        "primary-model",
        "backup-model",
        "backup-model",
    ]


def test_all_models_overloaded_gives_clear_reason(context):
    fake = ScriptedGemini([_overloaded()] * 4)
    backend = GeminiBackend(client=fake, model="a", fallback_models=["b"], retry_delay_s=0)
    ans = QatraAssistant(context, backend=backend).ask("What first?")
    assert ans.used_fallback and "Gemini unavailable (503" in ans.fallback_reason


def test_permanent_error_is_not_retried(context):
    bad = errors.ClientError(
        404, {"error": {"code": 404, "message": "model not found", "status": "NOT_FOUND"}}
    )
    fake = ScriptedGemini([bad])
    backend = GeminiBackend(client=fake, model="gone", fallback_models=["b"], retry_delay_s=0)
    ans = QatraAssistant(context, backend=backend).ask("What first?")
    assert len(fake.requests) == 1 and "Gemini error 404 on gone" in ans.fallback_reason
