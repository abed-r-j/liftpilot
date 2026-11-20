"""Numeric grounding: the agent may only state numbers that a tool returned.

Language models are fluent with numbers and unreliable at arithmetic. After
the agent writes its answer, every number in it is compared with the numbers
found in the tool results of the same run (and in the user's own request).
A number counts as grounded if it is a correctly rounded rendering of a tool
number, directly or after the usual presentation changes (fraction <-> percent,
thousands / millions). Anything else is reported as ungrounded.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

NUM = re.compile(
    r"(?<![\w.])([-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|[-+]?\d+(?:\.\d+)?)\s*(%|k\b|m\b|million\b|thousand\b|bn\b|billion\b)?",
    re.IGNORECASE,
)
ID_LIKE = re.compile(r"\b(plan-[0-9a-f]{8}|[0-9a-f]{10}|\d{4}-\d{2}-\d{2}|h\d{5})\b", re.IGNORECASE)
SCALE = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "bn": 1e9, "billion": 1e9}
ALWAYS_OK = {float(i) for i in range(0, 11)} | {95.0, 100.0}
MAX_RELATIVE_ROUNDING = 0.02

CURRENCY_WORDS: dict[str, tuple[str, ...]] = {
    "BRL": ("brl", "reais", "real ", "r$"),
    "USD": ("usd", "dollar", "us$"),
    "EUR": ("eur", "euro", "€"),
    "RUB": ("rub", "rouble", "ruble", "₽"),
    "LBP": ("lbp", "lebanese pound", "lira"),
    "GBP": ("gbp", "pound sterling", "£"),
}

SPACED = re.compile(r"(?<![\d.,])(\d{1,3}(?:[  ]\d{3})+)(?![\d])")


def stated_amounts(text: str) -> set[float]:
    """Numbers a person wrote, read the way a person means them:
    '1,000,000', '1 000 000', '1 million', '50k' and '25%' (as 25)."""
    found: set[float] = set()
    clean = ID_LIKE.sub(" ", text)
    for m in SPACED.finditer(clean):
        found.add(float(re.sub(r"[  ]", "", m.group(1))))
    for m in NUM.finditer(clean):
        value = float(m.group(1).replace(",", ""))
        unit = (m.group(2) or "").lower()
        found.add(value)
        if unit in SCALE:
            found.add(value * SCALE[unit])
    return found


@dataclass
class GroundingReport:
    checked: int = 0
    grounded: int = 0
    ungrounded: list[str] = field(default_factory=list)

    @property
    def rate(self) -> float:
        return 1.0 if self.checked == 0 else self.grounded / self.checked

    @property
    def ok(self) -> bool:
        return not self.ungrounded


def numbers_in(obj: Any) -> set[float]:
    """All numeric values inside a JSON-like object, including digits in strings."""
    found: set[float] = set()
    if isinstance(obj, bool) or obj is None:
        return found
    if isinstance(obj, (int, float)):
        found.add(float(obj))
    elif isinstance(obj, str):
        for m in NUM.finditer(ID_LIKE.sub(" ", obj)):
            found.add(float(m.group(1).replace(",", "")))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            found |= numbers_in(k) | numbers_in(v)
    elif isinstance(obj, (list, tuple, set)):
        for v in obj:
            found |= numbers_in(v)
    return found


def _rounding_step(raw: str) -> float:
    """Size of the last digit the writer kept: '0.70' -> 0.01, '19.0' -> 0.1,
    '6,098' -> 1, '740,000' -> 10,000 (trailing zeros read as rounding)."""
    digits = raw.lstrip("+-").replace(",", "")
    if "." in digits:
        return float(10.0 ** -len(digits.split(".")[1]))
    stripped = digits.rstrip("0")
    zeros = len(digits) - len(stripped) if stripped else 0
    return float(10.0**zeros)


def _matches(value: float, unit: str, step: float, allowed: set[float]) -> bool:
    """Is ``value`` a correctly rounded rendering of some tool number?

    A written number is grounded when a tool number lies within half of its
    last kept digit: '0.70' accepts 0.695-0.705, '83%' accepts 0.825-0.835.
    """
    forms = [(value, step)]
    if unit == "%":
        forms.append((value / 100.0, step / 100.0))
    elif unit in SCALE:
        forms = [(value * SCALE[unit], step * SCALE[unit])]
    else:
        forms.append((value / 100.0, step / 100.0))  # "3.3 points" without the % sign
    for v, s in forms:
        # half of the last kept digit, but never more than 2% of the value: trailing
        # zeros may be rounding ("740,000" for 739,812) yet "30%" is not "25%"
        tol = min(0.5 * s, MAX_RELATIVE_ROUNDING * abs(v)) * (1 + 1e-9) + 1e-12
        for a in allowed:
            if abs(abs(v) - abs(a)) <= tol:
                return True
    return False


def check_grounding(answer: str, sources: list[Any]) -> GroundingReport:
    allowed: set[float] = set(ALWAYS_OK)
    for s in sources:
        allowed |= numbers_in(s if not isinstance(s, str) else _maybe_json(s))
    report = GroundingReport()
    text = ID_LIKE.sub(" ", answer)
    text = re.sub(r"^\s*\d+[.)]\s", " ", text, flags=re.MULTILINE)  # list numbering
    for m in NUM.finditer(text):
        raw = m.group(1)
        unit = (m.group(2) or "").lower()
        value = float(raw.replace(",", ""))
        report.checked += 1
        if _matches(value, unit, _rounding_step(raw), allowed):
            report.grounded += 1
        else:
            report.ungrounded.append(m.group(0).strip())
    return report


def _maybe_json(text: str) -> Any:
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return text
