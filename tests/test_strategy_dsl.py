from __future__ import annotations

import pytest

from backend.strategy.examples import RSI_MEAN_REVERSION
from backend.strategy.models import StrategySpec
from backend.strategy.normalizer import normalize_strategy_record
from backend.strategy.parser import parse_condition_text
from backend.strategy.compiler import compile_strategy


def test_parse_symbolic_condition() -> None:
    expr = parse_condition_text("RSI(14,0) < 30")
    assert expr.indicator == "RSI"
    assert expr.operator == "<"
    assert expr.lhs == "RSI(14,0)"
    assert expr.rhs == "30"


def test_parse_natural_language_condition() -> None:
    expr = parse_condition_text("ADX(14,0) crosses below 25")
    assert expr.operator == "crosses_below"
    assert "ADX" in (expr.indicator or "")


def test_parse_cross_indicator_condition() -> None:
    expr = parse_condition_text("DEMA(close,9,0) crosses below DEMA(close,21,0)")
    assert expr.operator == "crosses_below"
    assert expr.lhs is not None
    assert "DEMA" in expr.lhs


def test_normalize_structured_db_row() -> None:
    row = {
        "name": "RSI Mean Reversion",
        "slug": "rsi-mean-reversion",
        "category": "Equity",
        "hypothesis": "Buy oversold",
        "entry_rules": {
            "conditions": [
                {
                    "indicator": "RSI",
                    "operator": "<",
                    "value": 30,
                    "params": {"timeperiod": 14},
                }
            ],
            "logical_operator": "AND",
        },
        "exit_rules": {
            "conditions": [
                {
                    "indicator": "RSI",
                    "operator": ">",
                    "value": 70,
                    "params": {"timeperiod": 14},
                }
            ],
            "logical_operator": "AND",
        },
        "risk_params": {"stop_loss": 0.02, "take_profit": 0.05},
    }
    spec = normalize_strategy_record(row)
    assert spec.name == "RSI Mean Reversion"
    assert len(spec.entry.conditions) == 1
    assert spec.risk.stop_loss_pct == 2.0
    assert spec.risk.take_profit_pct == 5.0


def test_normalize_text_condition_row() -> None:
    row = {
        "name": "ADX Setup",
        "slug": "adx-setup",
        "category": "Indicator Based",
        "entry_rules": {"condition": "ADX(14,0) lower than 25", "timeframe": "15min"},
        "exit_rules": {"target": "2%", "stop_loss": "1%"},
        "risk_params": {"stop_loss": "1%", "take_profit": "2%"},
    }
    spec = normalize_strategy_record(row)
    assert spec.timeframe == "15m"
    assert spec.entry.conditions[0].operator == "<"
    compiled = compile_strategy(spec)
    assert "ADX" in compiled.entry.conditions[0].canonical


def test_compile_example_spec() -> None:
    spec = StrategySpec.model_validate(RSI_MEAN_REVERSION)
    compiled = compile_strategy(spec, allowed_symbols={"NIFTY"})
    assert compiled.validation.valid
    assert "RSI(14,0) < 30" in compiled.entry.conditions[0].canonical
    assert compiled.entry.to_mask_expression().count("&") == 1
