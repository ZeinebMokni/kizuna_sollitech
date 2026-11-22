"""Strategy agent on Gemini: fake client returning real google-genai types (no network).

Step 1 = Google Search grounding (sources from grounding metadata), step 2 = function calling."""

from datetime import date
from types import SimpleNamespace

import pytest
from google.genai import types
from test_assistant import context  # noqa: F401
from test_assistant_gemini import call, response

from qatra_ai.assistant.backends import GeminiBackend, MissingCredentialsError
from qatra_ai.strategy.agent import FarmBrief, FarmStrategyAgent

U1 = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AAA111"
U2 = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/BBB222"
BRIEF = FarmBrief(region="Sidi Bouzid", crops=[("tomato", 1.0)], language="fr")


def research(chunks=((U1, "onagri.nat.tn"), (U2, "fao.org")), queries=("q1", "q2")):
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(
                    role="model", parts=[types.Part(text="- tomate: prix en baisse (2026-10)")]
                ),
                finish_reason=types.FinishReason.STOP,
                grounding_metadata=types.GroundingMetadata(
                    web_search_queries=list(queries),
                    grounding_chunks=[
                        types.GroundingChunk(web=types.GroundingChunkWeb(uri=u, title=t, domain=t))
                        for u, t in chunks
                    ],
                ),
            )
        ]
    )


class FakeGenai:
    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        self.models = SimpleNamespace(generate_content=self._gen)

    def _gen(self, model, contents, config):
        self.requests.append({"model": model, "contents": list(contents), "config": config})
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def draft(context, src="S1"):
    p = context.decision.payload.packages[0]
    return {
        "summary": "Irriguer la zone tomate; les prix pourraient baisser.",
        "immediate_actions": [
            {
                "action": p.action,
                "target": p.target,
                "why": f"{p.amount.value} m3 proposés par le moteur; à approuver",
                "result_ids": ["r1"],
            }
        ],
        "season_strategy": [
            {
                "recommendation": "Ne pas étendre la tomate.",
                "rationale": "Prix signalés en baisse.",
                "result_ids": [],
                "source_urls": [src],
            }
        ],
        "market_trends": [
            {
                "crop": "tomato",
                "trend": "Prix de gros en baisse",
                "direction": "falling",
                "evidence": "bulletin ONAGRI",
                "source_urls": [src],
                "published": "2026-10",
                "source_kind": "official",
            }
        ],
        "risks": ["Si beaucoup de fermes plantent de la tomate, le prix peut baisser."],
        "watch_next": [],
        "data_gaps": [],
    }


def run(context, script):
    fake = FakeGenai(script)
    backend = GeminiBackend(client=fake, model="gemini-test", fallback_models=[])
    from qatra_ai.strategy.agent import (
        RUN_MARKET_SCENARIO_TOOL,
        SUBMIT_STRATEGY_TOOL,
        TOOL_DEFINITIONS,
    )

    backend.tools = [*TOOL_DEFINITIONS, RUN_MARKET_SCENARIO_TOOL, SUBMIT_STRATEGY_TOOL]
    agent = FarmStrategyAgent(context, gemini_backend=backend)
    return agent.run(BRIEF, as_of=date(2026, 6, 15)), fake


def test_gemini_two_step_run_is_verified_and_maps_source_ids(context):
    rep, fake = run(
        context,
        [
            research(),
            response([call("list_decisions", {}, "c1")]),
            response([call("submit_strategy", draft(context, "S1"), "c2")]),
        ],
    )
    assert rep.verified and rep.provider == "gemini" and rep.web_searches == 2
    assert [s.url for s in rep.sources] == [U1]  # S1 mapped back to the retrieved URL
    assert rep.strategy.market_trends[0].source_urls == [U1]
    # step 1: Google Search only; step 2: function declarations only
    r_cfg, s_cfg = fake.requests[0]["config"], fake.requests[1]["config"]
    assert r_cfg.tools[0].google_search is not None and not r_cfg.tools[0].function_declarations
    names = {d.name for d in s_cfg.tools[0].function_declarations}
    assert {"submit_strategy", "run_market_scenario", "list_decisions"} <= names
    assert s_cfg.tools[0].google_search is None
    # the strategy pass sees the research notes and the numbered sources, not raw coordinates
    prompt = fake.requests[1]["contents"][0].parts[0].text
    assert "WEB RESEARCH NOTES" in prompt and f"S1: onagri.nat.tn <{U1}>" in prompt


def test_gemini_unknown_source_id_rejected_then_accepted(context):
    rep, fake = run(
        context,
        [
            research(),
            response([call("list_decisions", {}, "c1")]),
            response([call("submit_strategy", draft(context, "S9"), "c2")]),
            response([call("submit_strategy", draft(context, "S2"), "c3")]),
        ],
    )
    assert rep.verified and [s.url for s in rep.sources] == [U2]
    feedback = fake.requests[3]["contents"][-1].parts[0].function_response.response
    assert "was not returned by web_search" in feedback["error"]


def test_gemini_without_sources_cannot_claim_trends(context):
    rep, _ = run(
        context,
        [
            research(chunks=(), queries=()),
            response([call("list_decisions", {}, "c1")]),
            response([call("submit_strategy", draft(context, "S1"), "c2")]),
            response([call("submit_strategy", draft(context, "S1"), "c3")]),
        ],
    )
    assert rep.used_fallback and rep.strategy.market_trends == []
    assert rep.fallback_reason == "strategy failed QATRA's checks twice"


def test_gemini_missing_key_falls_back(context, monkeypatch):
    def no_key(self):
        raise MissingCredentialsError("no Gemini API key configured (set GEMINI_API_KEY)")

    monkeypatch.setattr(GeminiBackend, "_get_client", no_key)
    rep = FarmStrategyAgent(context, provider="gemini").run(BRIEF, as_of=date(2026, 6, 15))
    assert rep.used_fallback and "GEMINI_API_KEY" in rep.fallback_reason
    assert rep.provider == "gemini" and rep.strategy.immediate_actions


@pytest.mark.parametrize(
    "env,expected",
    [
        ({"QATRA_LLM_PROVIDER": "gemini"}, "gemini"),
        ({"QATRA_LLM_PROVIDER": "anthropic"}, "anthropic"),
    ],
)
def test_provider_follows_assistant_setting(context, monkeypatch, env, expected):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert FarmStrategyAgent(context).provider == expected


def test_search_quota_exhausted_still_gives_engine_based_strategy(context):
    from google.genai import errors

    quota = errors.ClientError(429, {"error": {"message": "You exceeded your current quota"}})
    d = draft(context)
    d["market_trends"], d["season_strategy"][0]["source_urls"] = [], []
    d["season_strategy"][0]["result_ids"] = ["r1"]
    rep, fake = run(
        context,
        [
            quota,
            quota,  # research: first try + transient retry
            response([call("list_decisions", {}, "c1")]),
            response([call("submit_strategy", d, "c2")]),
        ],
    )
    assert rep.verified and not rep.used_fallback
    assert rep.web_research.startswith("failed:") and "429" in rep.web_research
    assert rep.strategy.market_trends == [] and rep.sources == []
    assert any("web trend research unavailable" in g for g in rep.strategy.data_gaps)
    prompt = fake.requests[2]["contents"][0].parts[0].text
    assert "WEB RESEARCH FAILED" in prompt
