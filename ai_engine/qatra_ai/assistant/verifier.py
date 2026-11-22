"""Deterministic grounding verifier for assistant answers.

Checks:
  1. Citations: every cited result id exists. Single ([r2]) and combined ([r1, r2]) forms are
     parsed. An answer that states numbers must cite at least one result.
  2. Numbers, per claim: each number is checked only against the results cited in the same
     sentence; if the sentence cites nothing, the citations of its line (bullet), then of its
     paragraph, then of the whole answer are used. Matching tolerance: rounding to the precision
     written, or 1 % relative; fractions may be written as percentages.
  3. Units: a number written with a unit (m3, mm, mm*h, kWh, %, ha, degC) only matches source
     values of the same kind or of unknown kind, never a value of another unit that happens to
     be equal. Source units come from Quantity {"value", "unit"} objects and from key names
     (water_m3, depletion_mm, energy_kwh_per_ha, ..._pct, ...).
  4. Dates (YYYY-MM-DD) and clock times (HH:MM) must appear as such in the cited results; they
     are not split into small numbers.
  5. Small integers 0-10 are treated as counts, ranks and tiers and not checked, unless they
     carry a physical unit (e.g. "6 m3" is checked).
  6. A sentence that states numbers may cite at most two results: citing many large results
     at once makes almost any number "match" something (measured in the stress test).
  7. No forbidden claims (accusations, guarantees) in English, French or Arabic.
  Numbers that appear in the user's question are allowed.

History: per-claim scoping, combined citations, units and dates were added after the
2026-11-22 evaluation (docs/evaluation/grounding_verifier_stress.md), which found that wrong
numbers passed 13-40 % of the time when an answer cited several large results.

Handles Arabic-Indic digits (٠-٩, ۰-۹) and decimal commas ("12,5").
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
CITATION = re.compile(r"\[\s*(r\d+(?:\s*[,;،]\s*r\d+)*)\s*\]")
_CITE_ID = re.compile(r"r\d+")
# Numbers: optional sign, digits with optional thousands separators, optional decimal part.
NUMBER = re.compile(
    r"(?<![\w.])[-+]?\d{1,3}(?:[   ]\d{3})+(?:[.,]\d+)?|(?<![\w.])[-+]?\d+(?:[.,]\d+)?"
)
DATE = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)")
TIME = re.compile(r"(?<![\d:])\d{1,2}:\d{2}(?!\d)")
SMALL_COUNT_EXEMPT_UNITS = {None, "temperature"}  # small ints with these "units" are counts
MAX_CITES_PER_NUMERIC_SENTENCE = 2  # keeps every number checkable against a small pool

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


@dataclass
class _Source:
    value: float
    family: str | None  # unit kind, None if unknown


@dataclass
class _Pool:
    numbers: list[_Source] = field(default_factory=list)
    dates: set[str] = field(default_factory=set)
    times: set[str] = field(default_factory=set)


# --- units --------------------------------------------------------------------------------


def unit_family(text: str | None) -> str | None:
    """Kind of physical unit named in a unit string, key name or the words after a number."""
    if not text:
        return None
    u = text.lower().replace("_", " ").replace("*", " ").replace("`", " ")
    if re.search(r"mm\s*[·.]?\s*h\b|ملم\s*ساعة|mm\s*heure", u):
        return "depth_time"
    if re.search(r"m3|m³|m\^3|متر\s*مكعب|مترمكعب|أمتار\s*مكعبة", u):
        return "volume"
    if re.search(r"kwh|kw\s*h|كيلوواط", u):
        return "energy"
    if re.search(r"(?<![a-z])mm(?![a-z])|ملم|مم(?!\w)", u):
        return "depth"
    if re.search(r"%|٪|\bpct\b|percent|pourcent|بالمئة|بالمائة", u):
        return "percent"
    if re.search(r"(?<![a-z])ha(?![a-z])|hectare|هكتار", u):
        return "area"
    if re.search(r"°\s*c|\bdegc\b|درجة\s*مئوية", u):
        return "temperature"
    return None


def _text_unit(after: str) -> str | None:
    """Unit family of the words right after a number in the answer."""
    head = after[:24]
    if re.match(r"\s*[%٪]", head):
        return "percent"
    m = re.match(r"[\s*_`]*([^\s\[\]()]+)(\s+[^\s\[\]()]+)?", head)
    if not m:
        return None
    two = (m.group(1) + (m.group(2) or "")).strip()
    return unit_family(two) if unit_family(two) == "depth_time" else unit_family(m.group(1))


# --- source extraction --------------------------------------------------------------------


def _parse(tok: str) -> float | None:
    t = re.sub(r"[   ]", "", tok)
    t = t.replace(",", ".") if "," in t and "." not in t else t.replace(",", "")
    try:
        return float(t)
    except ValueError:
        return None


def _string_numbers(s: str, pool: _Pool) -> None:
    s = s.translate(ARABIC_DIGITS)
    pool.dates.update(DATE.findall(s))
    pool.times.update(t.zfill(5) for t in TIME.findall(s))
    s = TIME.sub(" ", DATE.sub(" ", s))
    for m in NUMBER.finditer(s):
        v = _parse(m.group())
        if v is not None:
            pool.numbers.append(_Source(v, _text_unit(s[m.end() :])))


def _collect(obj, pool: _Pool, family: str | None = None) -> None:
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, int | float):
        if math.isfinite(obj):
            pool.numbers.append(_Source(float(obj), family))
    elif isinstance(obj, dict):
        skip: set[str] = set()
        if "value" in obj and isinstance(obj.get("unit"), str):  # Quantity-like: value + unit
            fam = unit_family(obj["unit"]) or family
            _collect(obj["value"], pool, fam)
            _collect(obj.get("interval"), pool, fam)
            skip = {"value", "unit", "interval"}  # other keys (rule, note, ...) still read
        for k, v in obj.items():
            if k not in skip:
                _collect(v, pool, unit_family(str(k)) or family)
    elif isinstance(obj, list | tuple):
        for v in obj:
            _collect(v, pool, family)
    elif isinstance(obj, str):
        _string_numbers(obj, pool)  # numbers embedded in engine strings ("36 of 72 slots")


def _numeric_leaves(obj, out: list[float]) -> None:
    """All numeric values in a tool result (kept for evaluation scripts)."""
    pool = _Pool()
    _collect(obj, pool)
    out.extend(s.value for s in pool.numbers)


# --- matching -----------------------------------------------------------------------------


def _decimals(tok: str) -> int:
    t = tok.replace(",", ".")
    return len(t.split(".", 1)[1]) if "." in t else 0


def _matches(value: float, decimals: int, family: str | None, sources: list[_Source]) -> bool:
    half_step = 0.5 * 10 ** (-decimals)
    for s in sources:
        if family is not None and s.family is not None and s.family != family:
            continue  # same number, different quantity
        if abs(s.value - value) <= half_step + 1e-9:
            return True
        if abs(value) > 0 and abs(s.value - value) / abs(value) <= 0.01:
            return True
        # percentages written from fractions (0.52 -> 52 %)
        if family in (None, "percent") and abs(s.value * 100 - value) <= half_step + 1e-9:
            return True
    return False


def _ids(text: str) -> list[str]:
    return [i for m in CITATION.finditer(text) for i in _CITE_ID.findall(m.group(1))]


def _claims(text: str):
    """Yield (sentence, scoped citation ids): sentence -> line -> paragraph -> answer."""
    answer_ids = _ids(text)
    for para in re.split(r"\n\s*\n", text):
        para_ids = _ids(para)
        for line in para.split("\n"):
            line_ids = _ids(line)
            for sent in re.split(r"(?<=[.!?؟])\s+", line):
                yield sent, (_ids(sent) or line_ids or para_ids or answer_ids)


def verify(answer: str, tool_results: dict[str, dict], question: str = "") -> VerificationResult:
    text = answer.translate(ARABIC_DIGITS)
    violations: list[str] = []
    cited = _ids(text)
    for c in dict.fromkeys(cited):
        if c not in tool_results:
            violations.append(f"cites unknown result id [{c}]")

    pools: dict[tuple[str, ...], _Pool] = {}

    def pool_for(ids: list[str]) -> _Pool:
        key = tuple(sorted({i for i in ids if i in tool_results}))
        if not key:
            key = tuple(sorted(tool_results))
        if key not in pools:
            p = _Pool()
            for rid in key:
                _collect(tool_results[rid].get("data"), p)
            pools[key] = p
        return pools[key]

    q_text = question.translate(ARABIC_DIGITS)
    q_numbers = {v for m in NUMBER.finditer(q_text) if (v := _parse(m.group())) is not None}
    q_tokens = set(DATE.findall(q_text)) | {t.zfill(5) for t in TIME.findall(q_text)}

    checked = 0
    for sentence, ids in _claims(text):
        body = CITATION.sub(" ", sentence)
        if not NUMBER.search(body):
            continue
        own = {i for i in _ids(sentence)}
        if len(own) > MAX_CITES_PER_NUMERIC_SENTENCE:
            violations.append(
                f"a sentence with numbers cites {len(own)} results; cite the specific result "
                f"(at most {MAX_CITES_PER_NUMERIC_SENTENCE}) for each number"
            )
        pool = pool_for(ids)
        for d in DATE.findall(body):
            checked += 1
            if d not in pool.dates and d not in q_tokens:
                violations.append(f"date {d!r} does not appear in the cited tool results")
        for t in TIME.findall(body):
            checked += 1
            if t.zfill(5) not in pool.times and t.zfill(5) not in q_tokens:
                violations.append(f"time {t!r} does not appear in the cited tool results")
        body = TIME.sub(" ", DATE.sub(" ", body))
        for m in NUMBER.finditer(body):
            tok = m.group()
            v = _parse(tok)
            if v is None:
                continue
            fam = _text_unit(body[m.end() :])
            if float(v).is_integer() and 0 <= v <= 10 and fam in SMALL_COUNT_EXEMPT_UNITS:
                continue  # counting words / ranks / tiers
            checked += 1
            if v in q_numbers:
                continue
            if not _matches(v, _decimals(tok), fam, pool.numbers):
                unit = f" ({fam})" if fam else ""
                violations.append(
                    f"number {tok!r}{unit} does not match any value in the cited tool results"
                )
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
