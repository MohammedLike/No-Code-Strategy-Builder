"""Parse Streak-style condition strings into ConditionExpression objects."""

from __future__ import annotations

from .models import ConditionExpression
from .whitelist import OPERATOR_ALIASES

# Longest phrases first so "crosses below" wins over "below"
_OPERATOR_PHRASES = sorted(OPERATOR_ALIASES.items(), key=lambda item: len(item[0]), reverse=True)


def _canonical_operator(phrase: str) -> str:
    return OPERATOR_ALIASES.get(phrase.strip().lower(), phrase.strip())


def _extract_indicator_name(text: str) -> str | None:
    text = text.strip()
    if not text:
        return None
    if "(" in text:
        name = text.split("(", 1)[0].strip()
    else:
        parts = text.split()
        name = parts[0] if parts else text
    return name.upper() or None


def parse_condition_text(text: str) -> ConditionExpression:
    """Parse a human-readable condition string into a structured expression."""
    raw = " ".join(str(text).split())
    if not raw:
        return ConditionExpression(raw="")

    lowered = raw.lower()
    for phrase, operator in _OPERATOR_PHRASES:
        token = phrase.lower()
        idx = lowered.find(token)
        if idx == -1:
            continue

        lhs = raw[:idx].strip()
        rhs = raw[idx + len(phrase) :].strip()
        indicator = _extract_indicator_name(lhs) or _extract_indicator_name(rhs)

        return ConditionExpression(
            raw=raw,
            indicator=indicator,
            operator=_canonical_operator(phrase),
            lhs=lhs,
            rhs=rhs,
        )

    # Symbolic operators: RSI(14,0) < 30
    for op in ("<=", ">=", "==", "!=", "<", ">"):
        if op in raw:
            lhs, rhs = raw.split(op, 1)
            lhs, rhs = lhs.strip(), rhs.strip()
            return ConditionExpression(
                raw=raw,
                indicator=_extract_indicator_name(lhs) or _extract_indicator_name(rhs),
                operator=op,
                lhs=lhs,
                rhs=rhs,
            )

    return ConditionExpression(raw=raw, indicator=_extract_indicator_name(raw))


def parse_condition_list(values: list[str]) -> list[ConditionExpression]:
    return [parse_condition_text(value) for value in values if value and str(value).strip()]
