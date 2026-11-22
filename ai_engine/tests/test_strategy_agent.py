"""Strategy agent tests with a scripted fake Claude client (no network, no billing).

Engine context is the synthetic decision fixture from test_assistant; web results are fake."""

import json
from datetime import date

import pytest
from test_assistant import NS, FakeClient, context, msg, text, tool_use  # noqa: F401

from qatra_ai.strategy.agent import (
    FarmBrief,
    FarmStrategyAgent,
    _user_prompt,
    brief_from_profile,
)

URL = "https://www.onagri.example/prix-tomate-2026"
BRIEF = FarmBrief(region="Sidi Bouzid", crops=[("tomato", 1.0), ("citrus", 1.0)], language="en")


def web_turn(*extra, url=URL):
    return [
        NS(type="server_tool_use", name="web_search", id="srv1", input={"query": "q"}),
        NS(
            type="web_search_tool_result",
            tool_use_id="srv1",
            content=[NS(type="web_search_result", url=url, title="Prix", page_age="2026-11-01")],
        ),
        *extra,
    ]


def draft(context, **over):
    p = context.decision.payload.packages[0]
    d = {
        "summary": "Irrigate the stressed zone now; tomato prices may soften if supply rises.",
        "immediate_actions": [
            {
                "action": p.action,
                "target": p.target,
                "why": f"{p.amount.value} m3 proposed by the engine; needs your approval",
                "result_ids": ["r1"],
            }
        ],
        "season_strategy": [
            {
                "recommendation": "Do not expand tomato area; keep citrus.",
                "rationale": "Reported prices fell; many farms planting tomato could push them "
                "lower.",
                "result_ids": ["r1"],
                "source_urls": [URL],
            }
        ],
        "market_trends": [
            {
                "crop": "tomato",
                "trend": "Wholesale prices reported lower than last season",
                "direction": "falling",
                "evidence": "ONAGRI bulletin",
                "source_urls": [URL],
                "published": "2026-11",
                "source_kind": "official",
            }
        ],
        "risks": ["If many farms switch to the same crop, its price can fall."],
        "watch_next": ["Next ONAGRI price bulletin"],
        "data_gaps": ["No local farm-gate price series"],
    }
    d.update(over)
    return d


def submit(d, i="sub1"):
    return tool_use("submit_strategy", d, i)


def run(context, script, brief=BRIEF):
    client = FakeClient(script)
    rep = FarmStrategyAgent(context, client=client).run(brief, as_of=date(2026, 6, 15))
    return rep, client


def test_happy_path_is_verified_with_sources_and_request_shape(context):
    rep, client = run(
        context,
        [
            msg([tool_use("list_decisions", {})], "tool_use"),
            msg(web_turn(submit(draft(context))), "tool_use"),
        ],
    )
    assert rep.verified and not rep.used_fallback
    assert [s.url for s in rep.sources] == [URL] and rep.web_searches == 1
    assert rep.market_confidence == "low" and "never guaranteed" in rep.disclaimer
    req = client.requests[0]
    assert req["model"] == "claude-opus-5-5" and req["output_config"] == {"effort": "high"}
    assert req["fallbacks"] == "default" and "tool_choice" not in req
    types = {t.get("type") for t in req["tools"]}
    assert {"web_search_20260209", "web_fetch_20260209"} <= types
    client_tools = [t for t in req["tools"] if "input_schema" in t]
    assert all(t["strict"] for t in client_tools)
    assert {"submit_strategy", "run_market_scenario", "list_decisions"} <= {
        t["name"] for t in client_tools
    }


def test_invented_url_is_rejected_then_resubmission_accepted(context):
    bad = draft(context)
    bad["market_trends"][0]["source_urls"] = ["https://made-up.example/x"]
    rep, client = run(
        context,
        [
            msg([tool_use("list_decisions", {})], "tool_use"),
            msg(web_turn(submit(bad)), "tool_use"),
            msg([submit(draft(context), "sub2")], "tool_use"),
        ],
    )
    assert rep.verified and not rep.used_fallback
    feedback = client.requests[2]["messages"][-1]["content"][0]
    assert feedback["is_error"] and "was not returned by web_search" in feedback["content"]


def test_invented_irrigation_target_falls_back_to_engine_only(context):
    bad = draft(context)
    bad["immediate_actions"][0]["target"] = "zone:made_up"
    rep, _ = run(
        context,
        [
            msg([tool_use("list_decisions", {})], "tool_use"),
            msg(web_turn(submit(bad)), "tool_use"),
            msg([submit(bad, "sub2")], "tool_use"),
        ],
    )
    assert rep.used_fallback and not rep.verified
    assert "failed QATRA's checks twice" in rep.fallback_reason
    assert any("not an engine decision target" in v for v in rep.violations)
    assert rep.strategy.market_trends == []  # no unchecked web claims in the fallback
    assert rep.strategy.immediate_actions[0].target == context.decision.payload.packages[0].target


@pytest.mark.parametrize(
    "mutate,expected",
    [
        (lambda d: d.update(summary="Tomato profit is guaranteed this season."), "guarantee"),
        (
            lambda d: d["immediate_actions"][0].update(why="apply 987.6 m3 tonight"),
            "987.6",
        ),
        (lambda d: d["market_trends"][0].update(source_urls=[]), "no source URL"),
        (lambda d: d["season_strategy"][0].update(result_ids=["r99"]), "unknown result ids"),
    ],
)
def test_checks_reject_unsafe_drafts(context, mutate, expected):
    bad = draft(context)
    mutate(bad)
    _, client = run(
        context,
        [
            msg([tool_use("list_decisions", {})], "tool_use"),
            msg(web_turn(submit(bad)), "tool_use"),
            msg([submit(draft(context), "sub2")], "tool_use"),
        ],
    )
    feedback = client.requests[2]["messages"][-1]["content"][0]["content"]
    assert expected in feedback


def test_pause_turn_resumes_without_extra_user_message(context):
    rep, client = run(
        context,
        [
            msg([tool_use("list_decisions", {})], "tool_use"),
            msg(web_turn(), "pause_turn"),
            msg([submit(draft(context))], "tool_use"),
        ],
    )
    assert rep.verified
    resumed = client.requests[2]["messages"]
    assert resumed[-1]["role"] == "assistant"  # sent back as is, no "continue" message


@pytest.mark.parametrize(
    "error,reason",
    [
        ("Could not resolve authentication method", "no Claude API credentials configured"),
        ("connection reset", "API error: RuntimeError: connection reset"),
    ],
)
def test_api_error_returns_engine_only_fallback(context, error, reason):
    def boom(_):
        raise RuntimeError(error)

    rep, _ = run(context, [boom])
    assert rep.used_fallback and rep.fallback_reason == reason
    assert rep.strategy.immediate_actions and rep.sources == []


def test_market_scenario_tool_requires_retrieved_sources(context):
    args = {
        "crop": "tomato",
        "region": "Sidi Bouzid",
        "price_unit": "TND/t",
        "reference_price": 900,
        "reference_production_t": 120000,
        "elasticity_low": -0.8,
        "elasticity_high": -0.3,
        "other_production_low_t": 105000,
        "other_production_high_t": 130000,
        "imports_high_t": 0,
        "exports_high_t": 8000,
        "candidate_area_ha": 800,
        "yield_p10_t_per_ha": 40,
        "yield_p50_t_per_ha": 55,
        "yield_p90_t_per_ha": 65,
        "cost_per_ha": 22000,
        "alternative_margin_per_ha": 15000,
        "source_urls": ["https://not-retrieved.example"],
        "assumption_note": "elasticity assumed",
    }
    ok = {**args, "source_urls": [URL]}
    _, client = run(
        context,
        [
            msg([tool_use("list_decisions", {})], "tool_use"),
            msg(web_turn(tool_use("run_market_scenario", args, "m1")), "tool_use"),
            msg([tool_use("run_market_scenario", ok, "m2")], "tool_use"),
            msg([submit(draft(context))], "tool_use"),
        ],
    )
    first = client.requests[2]["messages"][-1]["content"][0]
    assert first["is_error"] and "not retrieved" in first["content"]
    second = json.loads(client.requests[3]["messages"][-1]["content"][0]["content"])
    assert second["tool"] == "run_market_scenario" and second["data"]["confidence"] == "low"
    assert (
        second["data"]["adoption"][0]["price_p10_p50_p90"][0]
        < second["data"]["adoption"][0]["price_p10_p50_p90"][2]
    )


def test_prompt_has_no_farm_name_or_coordinates():
    from qatra_ai.farms.registry import PACKAGE_FARMS_DIR, load_registry

    reg = load_registry([PACKAGE_FARMS_DIR])
    profile = reg.get("demo-farm")
    prompt = _user_prompt(brief_from_profile(profile), date(2026, 6, 15))
    assert profile.name not in prompt and profile.farm_id not in prompt
    assert f"{profile.location.latitude}" not in prompt
    assert f"{profile.location.longitude}" not in prompt
