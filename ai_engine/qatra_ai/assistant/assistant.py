"""QATRA explainable assistant: a tool-calling LLM loop wrapped by a deterministic verifier.

The LLM explains engine outputs; it does not compute recommendations, cannot write state and
has no tool that actuates hardware. Each final draft is checked by `verifier.verify`:
  pass        -> returned (verified=True)
  fail once   -> the model is asked to rewrite with the list of violations
  fail twice  -> a deterministic template answer built from the tools is returned instead
Refusals, token-limit stops and API errors also fall back to the template.

Model and API usage follow the Anthropic Messages API (manual tool loop, adaptive thinking,
explicit effort, server-side refusal fallback).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from qatra_ai.assistant.tools import TOOL_DEFINITIONS, AssistantContext, ToolError, ToolRegistry
from qatra_ai.assistant.verifier import verify

DEFAULT_MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_ITERATIONS = 8
Language = Literal["ar", "fr", "en"]

SYSTEM_PROMPT = """You are the QATRA assistant. QATRA is an agricultural decision-support engine for farms in Tunisia that pump their own irrigation water. You explain the engine's outputs to farmers, operators and water managers in plain language.

How to work:
- Facts come only from your tools. Call list_decisions first for any question about what to do or why, then get_decision or compare_priority for detail. Never state a measurement, model output, price or date that is not in a tool result.
- After each fact, cite the tool result it came from with its result_id in square brackets, for example [r2]. Copy numbers exactly as the tool gives them (you may round, and you may write a fraction as a percentage).
- Say where information comes from: measured, inferred (modelled), simulated or projected, and mention the confidence level and the main data limitation when it matters to the decision.
- If no tool has the answer, say plainly that QATRA does not have that information. Do not guess.
- Recommendations are proposals. Any irrigation or hold needs a person's approval; never say an action has been carried out.
- Water anomalies are hypotheses with evidence and suggested checks. Never suggest that a person is responsible or did something wrong.
- Never promise yields, prices or outcomes. Allocation comparisons show consequences of options; they are not fair, legal or official decisions.

Answer in the language of the user's question (Arabic, French or English). Keep answers short: lead with the action and the main reason, then at most a few supporting points."""

TEMPLATE_HEADERS = {
    "en": (
        "QATRA could not produce a checked explanation, so here are the engine's ranked "
        "proposals as computed:",
        "needs approval",
    ),
    "fr": (
        "QATRA n'a pas pu produire une explication vérifiée ; voici les propositions "
        "classées telles que calculées par le moteur :",
        "nécessite une approbation",
    ),
    "ar": (
        "لم يتمكن QATRA من إنتاج شرح موثّق، وهذه هي المقترحات المرتبة كما حسبها المحرك:",
        "يتطلب موافقة",
    ),
}


def detect_language(text: str) -> Language:
    if re.search(r"[؀-ۿ]", text):
        return "ar"
    fr_words = r"\b(le|la|les|des|pourquoi|quelle?|quoi|est|zone|irriguer|eau|dois|faut)\b"
    if re.search(r"[éèêàçù]", text.lower()) or len(re.findall(fr_words, text.lower())) >= 2:
        return "fr"
    return "en"


@dataclass
class ToolCallRecord:
    name: str
    input: dict[str, Any]
    result_id: str | None
    error: str | None = None


@dataclass
class AssistantAnswer:
    text: str
    language: Language
    verified: bool
    used_fallback: bool
    fallback_reason: str | None
    violations: list[str]
    citations: list[str]
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    model: str | None = None


class QatraAssistant:
    def __init__(
        self,
        context: AssistantContext,
        client: Any | None = None,
        model: str = DEFAULT_MODEL,
        effort: str = "medium",
    ):
        if client is None:
            import anthropic  # imported lazily so the engine works without the SDK

            client = anthropic.Anthropic()
        self.client = client
        self.model = model
        self.effort = effort
        self.context = context

    def _create(self, messages: list) -> Any:
        return self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            system=[
                {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
            ],
            tools=[{**t, "strict": True} for t in TOOL_DEFINITIONS],
            messages=messages,
            output_config={"effort": self.effort},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )

    def ask(self, question: str, history: list | None = None) -> AssistantAnswer:
        lang = detect_language(question)
        registry = ToolRegistry(self.context)
        calls: list[ToolCallRecord] = []
        messages = list(history or []) + [{"role": "user", "content": question}]
        retried = False
        last_violations: list[str] = []

        for _ in range(MAX_ITERATIONS):
            try:
                response = self._create(messages)
            except Exception as exc:  # network/API failure -> deterministic answer
                reason = (
                    "no Claude API credentials configured"
                    if "authentication method" in str(exc)
                    else f"API error: {type(exc).__name__}"
                )
                return self._template(lang, registry, calls, reason, last_violations)
            stop = response.stop_reason
            if stop == "refusal":
                return self._template(
                    lang, registry, calls, "model declined the request", last_violations
                )
            if stop == "max_tokens":
                return self._template(
                    lang, registry, calls, "answer exceeded the token limit", last_violations
                )
            messages.append({"role": "assistant", "content": response.content})
            if stop == "pause_turn":
                continue

            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if tool_uses:
                results = []
                for tu in tool_uses:
                    try:
                        content = registry.call(tu.name, dict(tu.input or {}))
                        rid = json.loads(content)["result_id"]
                        calls.append(ToolCallRecord(tu.name, dict(tu.input or {}), rid))
                        results.append(
                            {"type": "tool_result", "tool_use_id": tu.id, "content": content}
                        )
                    except (ToolError, TypeError) as exc:
                        calls.append(ToolCallRecord(tu.name, dict(tu.input or {}), None, str(exc)))
                        results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tu.id,
                                "content": f"Error: {exc}",
                                "is_error": True,
                            }
                        )
                messages.append({"role": "user", "content": results})  # all results, one turn
                continue

            text = "\n".join(b.text for b in response.content if b.type == "text").strip()
            check = verify(text, registry.results, question)
            if check.ok and text:
                return AssistantAnswer(
                    text,
                    lang,
                    True,
                    False,
                    None,
                    [],
                    check.citations,
                    calls,
                    getattr(response, "model", self.model),
                )
            last_violations = check.violations or ["empty answer"]
            if retried:
                return self._template(
                    lang,
                    registry,
                    calls,
                    "draft failed grounding verification twice",
                    last_violations,
                )
            retried = True
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your draft failed QATRA's grounding check:\n- "
                        + "\n- ".join(last_violations)
                        + "\nRewrite the answer using only values that appear in tool results, citing "
                        "each with its [rN] id. Call tools again if you need more data."
                    ),
                }
            )
        return self._template(lang, registry, calls, "too many tool iterations", last_violations)

    def _template(
        self,
        lang: Language,
        registry: ToolRegistry,
        calls: list[ToolCallRecord],
        reason: str,
        violations: list[str],
    ) -> AssistantAnswer:
        header, approval = TEMPLATE_HEADERS[lang]
        lines = [header]
        try:
            res = json.loads(registry.call("list_decisions", {}))
            rid = res["result_id"]
            for p in res["data"]["packages"][:5]:
                amt = f" {p['amount']['value']} {p['amount']['unit']}" if p["amount"] else ""
                flag = f" ({approval})" if p["requires_human_approval"] else ""
                lines.append(
                    f"{p['rank']}. {p['action']}{amt} -> {p['target']} | "
                    f"tier {p['tier']} {p['tier_label']} | {p['confidence']}{flag} [{rid}]"
                )
            citations = [rid]
        except ToolError as exc:
            lines.append(str(exc))
            citations = []
        return AssistantAnswer(
            "\n".join(lines), lang, False, True, reason, violations, citations, calls, None
        )
