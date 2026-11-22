"""LLM backends for the assistant. The loop, tools, grounding verifier and template fallback are
provider-neutral (assistant.py); a backend only sends turns and reports what came back.

Backends:
  anthropic  Claude via the Anthropic Messages API (manual tool loop, adaptive thinking,
             explicit effort, server-side refusal fallback)
  gemini     Gemini via google-genai `models.generate_content`, automatic function calling
             DISABLED so QATRA executes (and audits) every tool call itself; the model's turns
             are appended unchanged (they may carry thought signatures)

Selection (make_backend): QATRA_LLM_PROVIDER=anthropic|gemini; if unset, Gemini is used when
only a Gemini key (GEMINI_API_KEY or GOOGLE_API_KEY) is present, otherwise Claude.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from qatra_ai.assistant.tools import TOOL_DEFINITIONS

Stop = Literal["tool_calls", "end", "refusal", "max_tokens", "pause"]

ANTHROPIC_MODEL = "claude-opus-5-5"
ANTHROPIC_FALLBACK_BETA = "server-side-fallback-2026-07-01"
GEMINI_DEFAULT_MODEL = "gemini-4-hydrogen"


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]


@dataclass
class Turn:
    stop: Stop
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str | None = None
    detail: str | None = None  # e.g. the safety category or finish reason


class Backend(Protocol):
    provider: str
    model: str

    def start(self, system: str, question: str, history: list | None) -> None: ...
    def step(self) -> Turn: ...
    def add_tool_results(self, results: list[tuple[ToolCall, str, bool]]) -> None: ...
    def add_user_text(self, text: str) -> None: ...


class MissingCredentialsError(RuntimeError):
    pass


# --- Claude -------------------------------------------------------------------------------------


class AnthropicBackend:
    provider = "anthropic"

    def __init__(
        self, client: Any | None = None, model: str = ANTHROPIC_MODEL, effort: str = "medium"
    ):
        self._client = client
        self.model = model
        self.effort = effort
        self.messages: list = []
        self.system = ""

    def _get_client(self):
        if self._client is None:
            import anthropic  # lazy: the engine works without the SDK

            self._client = anthropic.Anthropic()
        return self._client

    def start(self, system: str, question: str, history: list | None) -> None:
        self.system = system
        self.messages = list(history or []) + [{"role": "user", "content": question}]

    def step(self) -> Turn:
        try:
            response = self._get_client().beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=[
                    {"type": "text", "text": self.system, "cache_control": {"type": "ephemeral"}}
                ],
                tools=[{**t, "strict": True} for t in TOOL_DEFINITIONS],
                messages=self.messages,
                output_config={"effort": self.effort},
                betas=[ANTHROPIC_FALLBACK_BETA],
                fallbacks="default",
            )
        except Exception as exc:
            if "authentication method" in str(exc):
                raise MissingCredentialsError("no Claude API credentials configured") from exc
            raise
        model = getattr(response, "model", self.model)
        stop = response.stop_reason
        if stop == "refusal":
            return Turn("refusal", model=model)
        if stop == "max_tokens":
            return Turn("max_tokens", model=model)
        self.messages.append({"role": "assistant", "content": response.content})
        if stop == "pause_turn":
            return Turn("pause", model=model)
        uses = [b for b in response.content if b.type == "tool_use"]
        if uses:
            return Turn(
                "tool_calls",
                tool_calls=[ToolCall(b.id, b.name, dict(b.input or {})) for b in uses],
                model=model,
            )
        text = "\n".join(b.text for b in response.content if b.type == "text").strip()
        return Turn("end", text=text, model=model)

    def add_tool_results(self, results: list[tuple[ToolCall, str, bool]]) -> None:
        blocks = []
        for call, content, is_error in results:
            block = {"type": "tool_result", "tool_use_id": call.id, "content": content}
            if is_error:
                block["is_error"] = True
            blocks.append(block)
        self.messages.append({"role": "user", "content": blocks})  # all results, one turn

    def add_user_text(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})


# --- Gemini -------------------------------------------------------------------------------------

_GEMINI_BLOCKED = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION"}
_GEMINI_TRANSIENT = {429, 500, 503}


class GeminiUnavailableError(RuntimeError):
    """Gemini could not answer (overloaded, rate-limited, or rejected the request)."""


class GeminiBackend:
    provider = "gemini"

    def __init__(
        self,
        client: Any | None = None,
        model: str | None = None,
        max_output_tokens: int = 8192,
        fallback_models: list[str] | None = None,
        retry_delay_s: float = 2.0,
    ):
        self._client = client
        self.model = model or os.environ.get("QATRA_GEMINI_MODEL", GEMINI_DEFAULT_MODEL)
        self.max_output_tokens = max_output_tokens
        fallbacks = os.environ.get("QATRA_GEMINI_FALLBACK_MODELS", "")
        self.fallback_models = (
            list(fallback_models)
            if fallback_models is not None
            else [m.strip() for m in fallbacks.split(",") if m.strip()]
        )
        self.retry_delay_s = retry_delay_s
        self._locked = False
        self.contents: list = []
        self.system = ""

    def _get_client(self):
        if self._client is None:
            from google import genai  # lazy

            try:
                self._client = genai.Client()  # reads GOOGLE_API_KEY or GEMINI_API_KEY
            except ValueError as exc:
                raise MissingCredentialsError(
                    "no Gemini API key configured (set GEMINI_API_KEY)"
                ) from exc
        return self._client

    def _config(self):
        from google.genai import types

        decls = [
            types.FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters_json_schema=t["input_schema"],
            )
            for t in TOOL_DEFINITIONS
        ]
        return types.GenerateContentConfig(
            system_instruction=self.system,
            tools=[types.Tool(function_declarations=decls)],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            max_output_tokens=self.max_output_tokens,
        )

    def start(self, system: str, question: str, history: list | None) -> None:
        from google.genai import types

        self.system = system
        self._locked = False
        self.contents = list(history or []) + [
            types.Content(role="user", parts=[types.Part(text=question)])
        ]

    def _generate(self):
        """Call Gemini, retrying transient errors (429/500/503) briefly. Before the first
        successful turn, an overloaded model is replaced by the next fallback model; after it,
        the model is kept fixed (its thought signatures are only valid for that model)."""
        from google.genai import errors

        candidates = [self.model] if self._locked else [self.model, *self.fallback_models]
        last: Exception | None = None
        for model in dict.fromkeys(candidates):
            for attempt in range(2):
                try:
                    response = self._get_client().models.generate_content(
                        model=model, contents=self.contents, config=self._config()
                    )
                    self.model, self._locked = model, True
                    return response
                except errors.APIError as exc:
                    last = exc
                    if exc.code not in _GEMINI_TRANSIENT:
                        raise GeminiUnavailableError(
                            f"Gemini error {exc.code} on {model}: {str(exc.message)[:120]}"
                        ) from exc
                    if attempt == 0:
                        time.sleep(self.retry_delay_s)
        code = getattr(last, "code", "?")
        raise GeminiUnavailableError(
            f"Gemini unavailable ({code}: overloaded or rate-limited) on "
            f"{', '.join(dict.fromkeys(candidates))}"
        ) from last

    def step(self) -> Turn:
        response = self._generate()
        feedback = getattr(response, "prompt_feedback", None)
        if not response.candidates:
            reason = getattr(feedback, "block_reason", None)
            return Turn("refusal", model=self.model, detail=str(reason) if reason else None)
        cand = response.candidates[0]
        finish = getattr(cand.finish_reason, "name", str(cand.finish_reason or ""))
        if finish in _GEMINI_BLOCKED:
            return Turn("refusal", model=self.model, detail=finish)
        if finish == "MAX_TOKENS":
            return Turn("max_tokens", model=self.model)
        if cand.content is not None:
            self.contents.append(cand.content)  # unchanged: keeps thought signatures
        calls = response.function_calls or []
        if calls:
            return Turn(
                "tool_calls",
                model=self.model,
                tool_calls=[
                    ToolCall(c.id or f"call_{i}", c.name, dict(c.args or {}))
                    for i, c in enumerate(calls)
                ],
            )
        text = "\n".join(
            p.text
            for p in (cand.content.parts if cand.content else []) or []
            if getattr(p, "text", None) and not getattr(p, "thought", False)
        )
        return Turn("end", text=text.strip(), model=self.model, detail=finish or None)

    def add_tool_results(self, results: list[tuple[ToolCall, str, bool]]) -> None:
        from google.genai import types

        parts = []
        for call, content, is_error in results:
            if is_error:
                payload = {"error": content}
            else:
                try:
                    payload = {"output": json.loads(content)}
                except json.JSONDecodeError:
                    payload = {"output": content}
            parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        id=call.id if not call.id.startswith("call_") else None,
                        name=call.name,
                        response=payload,
                    )
                )
            )
        self.contents.append(types.Content(role="user", parts=parts))

    def add_user_text(self, text: str) -> None:
        from google.genai import types

        self.contents.append(types.Content(role="user", parts=[types.Part(text=text)]))


def make_backend(provider: str | None = None) -> Backend:
    p = (provider or os.environ.get("QATRA_LLM_PROVIDER") or "").strip().lower()
    if not p:
        has_gemini = bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
        p = "gemini" if has_gemini and not os.environ.get("ANTHROPIC_API_KEY") else "anthropic"
    if p == "gemini":
        return GeminiBackend()
    if p == "anthropic":
        return AnthropicBackend()
    raise ValueError(f"unknown QATRA_LLM_PROVIDER {p!r} (use 'anthropic' or 'gemini')")
