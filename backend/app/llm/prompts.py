"""Prompt templates for strategy normalization and refinement."""

from __future__ import annotations

import json
from typing import Any

NORMALIZE_SYSTEM = """You are a financial strategy analyst. Your job is to convert raw strategy descriptions into a canonical JSON format.

The target JSON schema follows this Pydantic model:

{
  "name": "strategy name",
  "instrument_type": "EQUITY" | "FUTURES" | "OPTIONS" | "INDEX",
  "symbol": "NIFTY" | "BANKNIFTY" | "FINNIFLY" | "SENSEX" | etc.,
  "timeframe": "1m" | "5m" | "15m" | "30m" | "1h" | "4h" | "1d" | "1w",
  "entry": {
    "conditions": [
      {
        "raw": "human-readable condition",
        "indicator": "indicator name in UPPERCASE",
        "operator": "<" | ">" | "<=" | ">=" | "==" | "crosses_above" | "crosses_below",
        "lhs": "left side of expression",
        "rhs": "right side of expression"
      }
    ],
    "logical_operator": "AND" | "OR"
  },
  "exit": {
    "conditions": [...],
    "logical_operator": "AND" | "OR"
  },
  "risk": {
    "stop_loss_pct": float or null,
    "take_profit_pct": float or null,
    "position_size": "percent_equity" | "fixed_qty" | "fixed_capital",
    "size_value": float
  },
  "options": null or { ... },
  "metadata": {
    "nl_description": "free-text strategy summary",
    "category": "Trend Following" | "Mean Reversion" | "Breakout" | "Options" | "Momentum" | "Scalping"
  }
}

RULES:
- instrument_type defaults to EQUITY unless options or futures are mentioned.
- timeframe defaults to 1d if not specified.
- symbol defaults to NIFTY if not specified.
- Extract stop_loss_pct and take_profit_pct as percentages (e.g., 2 for 2%, not 0.02).
- Use logical_operator AND when multiple conditions must all be met, OR when any suffices.
- If a condition is unclear, put it in raw and leave other fields null.
- Output ONLY valid JSON. No commentary."""

REFINE_SYSTEM = """You are a financial strategy analyst. Your job is to adapt existing strategies to match a user query.

Given a list of similar strategies from the database and a user request, produce a modified strategy JSON.
- You may change symbol, timeframe, entry/exit conditions, or risk parameters.
- Do NOT invent indicators — only use ones present in the retrieved strategies or commonly known ones.
- Keep the overall logic structure from the best-matching strategy.
- Output ONLY valid JSON. No commentary."""


def build_normalize_prompt(raw_text: str) -> str:
    """Build a prompt to normalize a single raw strategy text."""
    return f"""Convert the following strategy description into a JSON object matching the schema.

Example:
User: Buy Nifty when RSI(14) goes below 30 on daily chart. SL 2%, Target 5%.
Assistant:
{{
  "name": "Nifty RSI Mean Reversion",
  "instrument_type": "EQUITY",
  "symbol": "NIFTY",
  "timeframe": "1d",
  "entry": {{
    "conditions": [
      {{"raw": "RSI(14) < 30", "indicator": "RSI", "operator": "<", "lhs": "RSI(14)", "rhs": "30"}}
    ],
    "logical_operator": "AND"
  }},
  "exit": {{
    "conditions": [
      {{"raw": "RSI(14) > 70", "indicator": "RSI", "operator": ">", "lhs": "RSI(14)", "rhs": "70"}}
    ],
    "logical_operator": "AND"
  }},
  "risk": {{"stop_loss_pct": 2.0, "take_profit_pct": 5.0}},
  "options": null,
  "metadata": {{"nl_description": "Buy Nifty when RSI(14) drops below 30 on daily chart.", "category": "Mean Reversion"}}
}}

Raw strategy:
```
{raw_text}
```"""


def build_refine_prompt(user_query: str, results: list[dict[str, Any]]) -> str:
    """Build a prompt to refine/adapt a strategy based on Qdrant results."""
    context = format_qdrant_results(results)
    return f"""Given the following similar strategies from the database and the user request, produce a modified strategy JSON.

Similar strategies:
{context}

User request: {user_query}

Adapt the best-matching strategy to fulfil the user request. You may change symbol, timeframe,
entry/exit conditions, or risk parameters. Do NOT invent indicators — only use ones present
in the retrieved strategies or commonly known ones. Output valid JSON only."""


def format_qdrant_results(results: list[dict[str, Any]]) -> str:
    """Format Qdrant search results for inclusion in a prompt."""
    lines: list[str] = []
    for i, hit in enumerate(results, 1):
        score = hit.get("score", 0)
        payload = hit.get("payload", {})
        name = payload.get("name", "Unnamed")
        doc = payload.get("document", payload.get("nl_description", ""))
        lines.append(f"{i}. [Score: {score:.3f}] {name}")
        if doc:
            lines.append(f"   Description: {doc[:300]}")
        lines.append("")
    return "\n".join(lines)
