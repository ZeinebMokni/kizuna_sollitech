"""QATRA explainable assistant: a tool-calling LLM loop wrapped by a deterministic verifier.

The LLM explains engine outputs; it does not compute recommendations, cannot write state and
has no tool that actuates hardware. Each final draft is checked by `verifier.verify`:
  pass        -> returned (verified=True)
  fail once   -> the model is asked to rewrite with the list of violations
  fail twice  -> a deterministic template answer built from the tools is returned instead
Refusals, token-limit stops and API errors also fall back to the template.

The LLM provider (Claude or Gemini) is a pluggable backend (backends.py); the tools, the
verifier and the fallback are the same for every provider.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from qatra_ai.assistant.backends import (
    ANTHROPIC_MODEL,
    AnthropicBackend,
    Backend,
    GeminiUnavailableError,
    MissingCredentialsError,
    make_backend,
)
from qatra_ai.assistant.tools import AssistantContext, ToolError, ToolRegistry
from qatra_ai.assistant.verifier import verify

DEFAULT_MODEL = ANTHROPIC_MODEL
MAX_ITERATIONS = 8
Language = Literal["ar", "fr", "en"]

SYSTEM_PROMPT = """You are the QATRA assistant. QATRA is an agricultural decision-support engine for farms in Tunisia that pump their own irrigation water. You explain the engine's outputs to farmers, operators and water managers in plain language.

How to work:
- Facts come only from your tools. Call list_decisions first for any question about what to do or why, then get_decision or compare_priority for detail. Never state a measurement, model output, price or date that is not in a tool result.
- After each fact, cite the tool result it came from with its result_id in square brackets, for example [r2] (at most two ids per sentence that contains numbers, e.g. [r1, r2]). Copy numbers exactly as the tool gives them (you may round, and you may write a fraction as a percentage).
- Every tool result has a data_class (measured, inferred = modelled, simulated, projected, web_reported, literature_reference, unknown). Say where information comes from, and always say so when it is simulated or of unknown origin, and mention the confidence level and the main data limitation when it matters to the decision.
- If no tool has the answer, say plainly that QATRA does not have that information. Do not guess.
- Recommendations are proposals. Any irrigation or hold needs a person's approval; never say an action has been carried out.
- Water anomalies are hypotheses with evidence and suggested checks. Never suggest that a person is responsible or did something wrong.
- Never promise yields, prices or outcomes. Allocation comparisons show consequences of options; they are not fair, legal or official decisions.
- Market outlooks are scenarios. Quote prices and margins as ranges (P10 to P90) with the main assumption, never as one expected price. When a crop is recommended to many farms, say that the extra supply can lower its price and point to the adoption cap or diversification signal.

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
    provider: str | None = None
    rejected_drafts: int = 0  # drafts the grounding check rejected before this answer
    draft_violations: list[str] = field(default_factory=list)  # why the first draft failed


class QatraAssistant:
    """Provider-neutral loop. Pass `backend` (see backends.py), or a Claude `client` (kept for
    tests and backwards compatibility); with neither, `make_backend()` chooses from the
    environment (QATRA_LLM_PROVIDER, available API keys)."""

    def __init__(
        self,
        context: AssistantContext,
        client: Any | None = None,
        model: str | None = None,
        effort: str = "medium",
        backend: Backend | None = None,
    ):
        if backend is None:
            if client is not None:
                backend = AnthropicBackend(client, model or DEFAULT_MODEL, effort)
            else:
                backend = make_backend()
        self.backend = backend
        self.context = context

    def ask(self, question: str, history: list | None = None) -> AssistantAnswer:
        lang = detect_language(question)
        registry = ToolRegistry(self.context)
        calls: list[ToolCallRecord] = []
        retried = False
        draft_violations: list[str] = []
        last_violations: list[str] = []
        self.backend.start(SYSTEM_PROMPT, question, history)

        for _ in range(MAX_ITERATIONS):
            try:
                turn = self.backend.step()
            except (MissingCredentialsError, GeminiUnavailableError) as exc:
                return self._template(lang, registry, calls, str(exc), last_violations)
            except Exception as exc:  # network/API failure -> deterministic answer
                return self._template(
                    lang, registry, calls, f"API error: {type(exc).__name__}", last_violations
                )
            if turn.stop == "refusal":
                reason = "model declined the request"
                if turn.detail:
                    reason += f" ({turn.detail})"
                return self._template(lang, registry, calls, reason, last_violations)
            if turn.stop == "max_tokens":
                return self._template(
                    lang, registry, calls, "answer exceeded the token limit", last_violations
                )
            if turn.stop == "pause":
                continue

            if turn.stop == "tool_calls":
                results = []
                for tc in turn.tool_calls:
                    try:
                        content = registry.call(tc.name, tc.args)
                        rid = json.loads(content)["result_id"]
                        calls.append(ToolCallRecord(tc.name, tc.args, rid))
                        results.append((tc, content, False))
                    except (ToolError, TypeError) as exc:
                        calls.append(ToolCallRecord(tc.name, tc.args, None, str(exc)))
                        results.append((tc, f"Error: {exc}", True))
                self.backend.add_tool_results(results)
                continue

            text = turn.text
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
                    turn.model or self.backend.model,
                    self.backend.provider,
                    rejected_drafts=int(retried),
                    draft_violations=draft_violations,
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
            draft_violations = list(last_violations)
            self.backend.add_user_text(
                "Your draft failed QATRA's grounding check:\n- "
                + "\n- ".join(last_violations)
                + "\nRewrite the answer using only values that appear in tool results, citing "
                "each with its [rN] id. Call tools again if you need more data."
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
