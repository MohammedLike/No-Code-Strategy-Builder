"""CLI demo for Strategy DSL."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.strategy import (  # noqa: E402
    compile_strategy,
    normalize_strategy_record,
    parse_condition_text,
)
from backend.strategy.examples import RSI_MEAN_REVERSION  # noqa: E402
from scripts.common import DATABASE_URL  # noqa: E402


def demo_parser() -> None:
    samples = [
        "RSI(14,0) < 30",
        "ADX(14,0) crosses below 25",
        "SMA(close, 9, 0) crosses above SMA(close, 21, 0)",
        "DEMA(close,9,0) crosses below DEMA(close,21,0)",
    ]
    print("=== Parser ===")
    for sample in samples:
        parsed = parse_condition_text(sample)
        print(f"{sample}")
        print(f"  -> {parsed.to_canonical()} [{parsed.indicator} {parsed.operator}]\n")


def demo_example_spec() -> None:
    from backend.strategy.models import StrategySpec

    print("=== Example Spec ===")
    spec = StrategySpec.model_validate(RSI_MEAN_REVERSION)
    compiled = compile_strategy(spec)
    print(json.dumps(compiled.to_dict(), indent=2))


def demo_database_sample() -> None:
    print("=== Database Sample ===")
    with psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, slug, category, hypothesis, entry_rules, exit_rules, risk_params, metadata
                FROM public.strategies
                WHERE entry_rules ? 'condition'
                LIMIT 1
                """
            )
            row = cur.fetchone()
    if not row:
        print("No matching rows.")
        return

    spec = normalize_strategy_record(dict(row))
    compiled = compile_strategy(spec)
    print(json.dumps(compiled.to_dict(), indent=2))


def main() -> None:
    demo_parser()
    demo_example_spec()
    demo_database_sample()


if __name__ == "__main__":
    main()
