"""Deterministic grounding verifier for assistant answers.

Checks, in order:
  1. every number in the answer matches a numeric value in the cited/available tool results
     (tolerance: rounding to the precision written, or 1 % relative); small counting integers
     (0-10) and numbers that appear in the user's question are allowed;
  2. every cited result id [rN] exists; an answer containing numbers must cite at least one;
  3. no forbidden claims (accusations, guarantees) in English, French or Arabic.

Handles Arabic-Indic digits (٠-٩, ۰-۹) and decimal commas ("12,5").
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
CITATION = re.compile(r"\[(r\d+)\]")
# Numbers: optional sign, digits with optional thousands separators, optional decimal part.
NUMBER = re.compile(
    r"(?<![\w.])[-+]?\d{1,3}(?:[   ]\d{3})+(?:[.,]\d+)?|(?<![\w.])[-+]?\d+(?:[.,]\d+)?"
)

FORBIDDEN = {
    "accusation": [
        r"\btheft\b",
        r"\bsteal",
        r"\bstolen\b",
        r"\bfraud",
        r"\billegal",
        r"\bvol d'eau\b",
        r"\bvoleur",
        r"\bfraude\b",
        r"\bill[ée]gal",
        "سرقة",
        "سارق",
        "احتيال",
        "غير قانوني",
    ],
    "guarantee": [
        r"\bguarantee",
        r"\bcertainly will\b",
        r"\bgaranti",
        r"\bassur[ée]ment\b",
        "مضمون",
        "نضمن",
        "بالتأكيد سي",
    ],
}


@dataclass
class VerificationResult:
    ok: bool
    violations: list[str] = field(default_factory=list)
    numbers_checked: int = 0
    citations: list[str] = field(default_factory=list)


def _numeric_leaves(obj, out: list[float]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, int | float):
        if math.isfinite(obj):
            out.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _numeric_leaves(v, out)
    elif isinstance(obj, list | tuple):
        for v in obj:
            _numeric_leaves(v, out)
    elif isinstance(obj, str):
        # numbers embedded in strings produced by the engine (e.g. "36 of 72 slots")
        for m in NUMBER.finditer(obj.translate(ARABIC_DIGITS)):
            v = _parse(m.group())
            if v is not None:
                out.append(v)


def _parse(tok: str) -> float | None:
    t = re.sub(r"[   ]", "", tok)
    t = t.replace(",", ".") if "," in t and "." not in t else t.replace(",", "")
    try:
        return float(t)
    except ValueError:
        return None


def _decimals(tok: str) -> int:
    t = tok.replace(",", ".")
    return len(t.split(".", 1)[1]) if "." in t else 0


def _matches(value: float, decimals: int, sources: list[float]) -> bool:
    half_step = 0.5 * 10 ** (-decimals)
    for s in sources:
        if abs(s - value) <= half_step + 1e-9:
            return True
        if abs(value) > 0 and abs(s - value) / abs(value) <= 0.01:
            return True
        # percentages written from fractions (0.52 -> 52 %)
        if abs(s * 100 - value) <= half_step + 1e-9:
            return True
    return False


def verify(answer: str, tool_results: dict[str, dict], question: str = "") -> VerificationResult:
    text = answer.translate(ARABIC_DIGITS)
    violations: list[str] = []

    cited = CITATION.findall(text)
    for c in cited:
        if c not in tool_results:
            violations.append(f"cites unknown result id [{c}]")

    pool_ids = [c for c in cited if c in tool_results] or list(tool_results)
    sources: list[float] = []
    for rid in pool_ids:
        _numeric_leaves(tool_results[rid].get("data"), sources)
    q_numbers = [
        v
        for m in NUMBER.finditer(question.translate(ARABIC_DIGITS))
        if (v := _parse(m.group())) is not None
    ]

    body = CITATION.sub(" ", text)
    checked = 0
    for m in NUMBER.finditer(body):
        tok = m.group()
        v = _parse(tok)
        if v is None:
            continue
        if float(v).is_integer() and 0 <= v <= 10:
            continue  # counting words / ranks / tiers
        checked += 1
        if v in q_numbers:
            continue
        if not _matches(v, _decimals(tok), sources):
            violations.append(f"number {tok!r} does not match any value in the tool results")
    if checked and not cited:
        violations.append("answer states numbers but cites no tool result [rN]")

    low = text.lower()
    for kind, patterns in FORBIDDEN.items():
        for p in patterns:
            if re.search(p, low):
                violations.append(f"forbidden {kind} wording matched {p!r}")

    return VerificationResult(
        ok=not violations,
        violations=violations,
        numbers_checked=checked,
        citations=sorted(set(cited)),
    )


def tool_results_from_json(contents: dict[str, str]) -> dict[str, dict]:
    return {rid: json.loads(c) for rid, c in contents.items()}
