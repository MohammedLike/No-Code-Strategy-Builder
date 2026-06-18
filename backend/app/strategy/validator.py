"""Validate StrategySpec against compiler whitelist and optional DB symbol lists."""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import ConditionExpression, StrategySpec
from .whitelist import CORE_INDICATORS, KNOWN_INDICATORS, OPERATORS, VALID_TIMEFRAMES


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def raise_if_invalid(self) -> None:
        if not self.valid:
            raise ValueError("; ".join(self.errors))


def _validate_expression(expr: ConditionExpression, label: str, result: ValidationResult) -> None:
    if not expr.raw.strip():
        result.errors.append(f"{label}: empty condition")
        return

    if expr.operator and expr.operator not in OPERATORS:
        result.warnings.append(f"{label}: unknown operator '{expr.operator}'")

    if expr.indicator:
        indicator = expr.indicator.upper()
        if indicator not in KNOWN_INDICATORS:
            result.warnings.append(f"{label}: unrecognized indicator '{expr.indicator}'")
        elif indicator not in CORE_INDICATORS:
            result.warnings.append(f"{label}: indicator '{expr.indicator}' is not in core compiler set")


def validate_strategy(
    spec: StrategySpec,
    *,
    allowed_symbols: set[str] | None = None,
) -> ValidationResult:
    result = ValidationResult(valid=True)

    if not spec.name.strip():
        result.errors.append("name is required")

    if spec.timeframe not in VALID_TIMEFRAMES:
        result.errors.append(f"unsupported timeframe '{spec.timeframe}'")

    if allowed_symbols is not None and spec.symbol.upper() not in {s.upper() for s in allowed_symbols}:
        result.errors.append(f"symbol '{spec.symbol}' not found in OHLCV universe")

    if spec.instrument_type.value == "OPTIONS" and spec.options is None:
        result.warnings.append("OPTIONS strategy has no options block")

    if not spec.entry.conditions and spec.options is None:
        result.errors.append("entry conditions are required for non-options strategies")

    for index, expr in enumerate(spec.entry.conditions, start=1):
        _validate_expression(expr, f"entry[{index}]", result)

    for index, expr in enumerate(spec.exit.conditions, start=1):
        _validate_expression(expr, f"exit[{index}]", result)

    if spec.risk.stop_loss_pct is not None and spec.risk.take_profit_pct is not None:
        if spec.risk.stop_loss_pct >= spec.risk.take_profit_pct:
            result.warnings.append("stop_loss_pct is greater than or equal to take_profit_pct")

    result.valid = not result.errors
    return result
