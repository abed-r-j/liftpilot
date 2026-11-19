"""Guardrails for the marketing copy the agent drafts.

The language model may write the words. It may not decide what is true. Every
draft is checked by ordinary code against the approved offer sheet:

* length fits the channel,
* an opt-out instruction is present,
* no number, percentage, price or date that is not on the offer sheet,
* no pressure tactics the offer sheet does not back up (fake urgency,
  fake scarcity, guilt, health or financial promises),
* no reference to sensitive personal attributes.

A draft that fails is sent back once with the reasons; if it fails again the
pre-approved template for that segment is used instead.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

SMS_LIMIT = 160

PRESSURE_PATTERNS: dict[str, str] = {
    r"\b(last chance|final chance|final warning|now or never)\b": "false urgency",
    r"\b(only|just) \d+ (left|remaining)\b": "false scarcity",
    r"\b(hurry|act now|don'?t miss out|before it'?s too late|expires? (soon|tonight|today))\b": "pressure wording",
    r"\b(you (will|'ll) regret|don'?t let (us|your family) down|everyone else)\b": "guilt or social pressure",
    r"\b(guarantee[ds]?|risk[- ]free|cure[sd]?|lose weight|get rich|100 ?%)\b": "unsupported promise",
    r"\b(we know (you|your)|we noticed you|we saw (you|that you)|because you are (a|an) )\b": "surveillance wording",
    r"\b(your (age|gender|health|income|religion|debt)|as a (woman|man|senior|pensioner))\b": "sensitive attribute",
}

NUMBER = re.compile(r"\d+(?:[.,]\d+)?\s?%?")


class Offer(BaseModel):
    """The approved offer sheet: the only source of facts for the copy."""

    brand: str = "FreshMart"
    channel: str = "sms"
    offer_text: str = "a reminder of this week's fresh picks in your nearest store"
    allowed_numbers: list[str] = Field(default_factory=list)
    deadline: str | None = None
    opt_out: str = "Reply STOP to opt out"
    tone: str = "warm, plain, respectful; no hype"
    max_chars: int = SMS_LIMIT


@dataclass
class Verdict:
    ok: bool
    problems: list[str] = field(default_factory=list)
    chars: int = 0


def check_copy(text: str, offer: Offer) -> Verdict:
    problems: list[str] = []
    body = text.strip()
    low = body.lower()
    if not body:
        return Verdict(False, ["empty message"], 0)
    if len(body) > offer.max_chars:
        problems.append(f"too long: {len(body)} characters, limit {offer.max_chars}")
    if "stop" not in low and "opt out" not in low and "unsubscribe" not in low:
        problems.append("no opt-out instruction")
    if offer.brand.lower() not in low:
        problems.append("sender brand is not named")
    allowed = {n.replace(" ", "").lower() for n in offer.allowed_numbers}
    if offer.deadline:
        allowed |= {m.group().replace(" ", "") for m in NUMBER.finditer(offer.deadline)}
    for match in NUMBER.finditer(body):
        token = match.group().replace(" ", "").lower()
        if token not in allowed:
            problems.append(f"number '{match.group().strip()}' is not on the offer sheet")
    for pattern, label in PRESSURE_PATTERNS.items():
        if re.search(pattern, low):
            if label in ("false urgency", "pressure wording") and offer.deadline:
                continue  # a real, stated deadline may be mentioned
            problems.append(f"{label}: matches '{pattern}'")
    if re.search(r"https?://|www\.", low):
        problems.append("links are not allowed in agent-drafted copy")
    return Verdict(not problems, problems, len(body))


SEGMENT_ANGLE: dict[str, str] = {
    "Champions": "thank them for being regulars; no incentive needed",
    "Loyal": "appreciation and a look at what is new",
    "Potential loyalists": "invite them to make the store a habit",
    "New customers": "welcome them and help them find their way",
    "Need attention": "a friendly reminder of what they liked",
    "At risk": "we would be glad to see you again",
    "Cannot lose them": "we would be glad to see you again; ask for feedback",
    "Hibernating": "a gentle, no-pressure invitation back",
}


def fallback_template(segment: str, offer: Offer) -> str:
    """Pre-approved wording used when the model's draft cannot pass the checks."""
    openers = {
        "Champions": "Thank you for shopping with us so often.",
        "Loyal": "Thanks for being a regular.",
        "Potential loyalists": "Good to see you lately.",
        "New customers": "Welcome!",
        "Need attention": "It has been a little while.",
        "At risk": "We would be glad to see you again.",
        "Cannot lose them": "We would be glad to see you again.",
        "Hibernating": "It has been a while.",
    }
    text = f"{offer.brand}: {openers.get(segment, 'Hello.')} Here is {offer.offer_text}."
    if offer.deadline:
        text += f" Valid until {offer.deadline}."
    text += f" {offer.opt_out}."
    if len(text) > offer.max_chars:
        text = f"{offer.brand}: {offer.offer_text}. {offer.opt_out}."
    return text[: offer.max_chars]
