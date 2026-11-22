"""Output contract and deterministic checks for the farm strategy agent.

The model must deliver its strategy through the `submit_strategy` tool (strict JSON schema).
Before the strategy is accepted, QATRA checks it without any LLM:
  - every market trend cites at least one URL, and every URL was actually returned by the
    web search/fetch tools in this run (no invented sources);
  - immediate (sensor-based) actions only restate the engine's decision packages: same
    target, cited result ids, and every number found in the engine result it cites;
  - every season recommendation rests on an engine result id or a retrieved URL;
  - no guarantee language (prices, yields and profits are never promised).
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from qatra_ai.assistant.verifier import verify

Direction = Literal["rising", "falling", "stable", "mixed", "unclear"]
SourceKind = Literal["official", "international_org", "news", "trade", "other"]

GUARANTEE = re.compile(
    r"\b(guarantee[sd]?|guaranteeing|risk[- ]free|sure (profit|gain)s?|will definitely|"
    r"certain to (rise|increase|fall|pay)|garanti(e|es|s)?|sans risque|profit assur[ée])\b"
    r"|مضمون|مضمونة|بدون مخاطر",
    re.IGNORECASE,
)


class ImmediateAction(BaseModel):
    action: str
    target: str
    why: str
    result_ids: list[str]


class SeasonRecommendation(BaseModel):
    recommendation: str
    rationale: str
    result_ids: list[str]
    source_urls: list[str]


class MarketTrend(BaseModel):
    crop: str
    trend: str
    direction: Direction
    evidence: str
    source_urls: list[str]
    published: str = Field(description="publication date or period, or 'unknown'")
    source_kind: SourceKind


class StrategyDraft(BaseModel):
    summary: str
    immediate_actions: list[ImmediateAction]
    season_strategy: list[SeasonRecommendation]
    market_trends: list[MarketTrend]
    risks: list[str]
    watch_next: list[str]
    data_gaps: list[str]


def _obj(props: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "properties": props,
        "required": required if required is not None else list(props),
        "additionalProperties": False,
    }


_S = {"type": "string"}
_LS = {"type": "array", "items": _S}

SUBMIT_STRATEGY_TOOL = {
    "name": "submit_strategy",
    "description": "Deliver the final farm strategy. Call it exactly once, when your research "
    "is complete. QATRA checks it: sources must be URLs you actually retrieved, immediate "
    "actions must restate engine decision packages with their result ids, and nothing may be "
    "promised. If the check fails you get the violations and may resubmit once.",
    "input_schema": _obj(
        {
            "summary": _S,
            "immediate_actions": {
                "type": "array",
                "items": _obj(
                    {"action": _S, "target": _S, "why": _S, "result_ids": _LS},
                ),
            },
            "season_strategy": {
                "type": "array",
                "items": _obj(
                    {
                        "recommendation": _S,
                        "rationale": _S,
                        "result_ids": _LS,
                        "source_urls": _LS,
                    }
                ),
            },
            "market_trends": {
                "type": "array",
                "items": _obj(
                    {
                        "crop": _S,
                        "trend": _S,
                        "direction": {
                            "type": "string",
                            "enum": ["rising", "falling", "stable", "mixed", "unclear"],
                        },
                        "evidence": _S,
                        "source_urls": _LS,
                        "published": _S,
                        "source_kind": {
                            "type": "string",
                            "enum": ["official", "international_org", "news", "trade", "other"],
                        },
                    }
                ),
            },
            "risks": _LS,
            "watch_next": _LS,
            "data_gaps": _LS,
        }
    ),
}


def _norm(url: str) -> str:
    return url.strip().rstrip("/").split("#")[0].lower()


def check_strategy(
    draft: StrategyDraft,
    seen_urls: set[str],
    engine_results: dict[str, dict],
    decision_targets: set[str],
) -> list[str]:
    v: list[str] = []
    seen = {_norm(u) for u in seen_urls}

    def urls_ok(where: str, urls: list[str]) -> None:
        for u in urls:
            if _norm(u) not in seen:
                v.append(f"{where}: {u} was not returned by web_search/web_fetch in this run")

    for i, t in enumerate(draft.market_trends):
        if not t.source_urls:
            v.append(f"market_trends[{i}] ({t.crop}) has no source URL")
        urls_ok(f"market_trends[{i}]", t.source_urls)

    for i, a in enumerate(draft.immediate_actions):
        where = f"immediate_actions[{i}]"
        if not decision_targets:
            v.append(f"{where}: the engine has no decision packages; leave this list empty")
            continue
        if a.target not in decision_targets:
            v.append(
                f"{where}: target {a.target!r} is not an engine decision target "
                f"{sorted(decision_targets)}; immediate actions only restate engine packages"
            )
        if not a.result_ids:
            v.append(f"{where}: cite the engine result id(s) it comes from")
        bad = [r for r in a.result_ids if r not in engine_results]
        if bad:
            v.append(f"{where}: unknown result ids {bad}")
        if a.result_ids and not bad:
            cited = " ".join(f"[{r}]" for r in a.result_ids)
            check = verify(f"{a.action} {a.target}. {a.why} {cited}", engine_results)
            v.extend(f"{where}: {x}" for x in check.violations)

    for i, s in enumerate(draft.season_strategy):
        where = f"season_strategy[{i}]"
        if not s.result_ids and not s.source_urls:
            v.append(f"{where}: needs an engine result id or a retrieved source URL")
        bad = [r for r in s.result_ids if r not in engine_results]
        if bad:
            v.append(f"{where}: unknown result ids {bad}")
        urls_ok(where, s.source_urls)

    texts = [draft.summary, *draft.risks, *draft.watch_next]
    texts += [f"{a.action} {a.why}" for a in draft.immediate_actions]
    texts += [f"{s.recommendation} {s.rationale}" for s in draft.season_strategy]
    texts += [f"{t.trend} {t.evidence}" for t in draft.market_trends]
    for t in texts:
        if m := GUARANTEE.search(t):
            v.append(f"guarantee language {m.group()!r}: present outcomes as possibilities")
    return v
