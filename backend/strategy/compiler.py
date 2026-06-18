"""Compile StrategySpec into a runtime-friendly representation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import ConditionBlock, ConditionExpression, StrategySpec
from .validator import ValidationResult, validate_strategy


@dataclass
class CompiledCondition:
    raw: str
    canonical: str
    indicator: str | None
    operator: str | None
    lhs: str | None
    rhs: str | None


@dataclass
class CompiledBlock:
    logical_operator: str
    conditions: list[CompiledCondition] = field(default_factory=list)

    def to_mask_expression(self) -> str:
        if not self.conditions:
            return "False"
        parts = [f"({item.canonical})" for item in self.conditions]
        joiner = " & " if self.logical_operator == "AND" else " | "
        return joiner.join(parts)


@dataclass
class CompiledStrategy:
    name: str
    symbol: str
    timeframe: str
    instrument_type: str
    entry: CompiledBlock
    exit: CompiledBlock
    risk: dict[str, Any]
    options: dict[str, Any] | None
    indicators_used: list[str]
    metadata: dict[str, Any]
    validation: ValidationResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "instrument_type": self.instrument_type,
            "entry": {
                "logical_operator": self.entry.logical_operator,
                "conditions": [item.canonical for item in self.entry.conditions],
                "mask_expression": self.entry.to_mask_expression(),
            },
            "exit": {
                "logical_operator": self.exit.logical_operator,
                "conditions": [item.canonical for item in self.exit.conditions],
                "mask_expression": self.exit.to_mask_expression(),
            },
            "risk": self.risk,
            "options": self.options,
            "indicators_used": self.indicators_used,
            "metadata": self.metadata,
            "validation": {
                "valid": self.validation.valid,
                "errors": self.validation.errors,
                "warnings": self.validation.warnings,
            },
        }


def _compile_block(block: ConditionBlock) -> CompiledBlock:
    compiled_conditions = [
        CompiledCondition(
            raw=expr.raw,
            canonical=expr.to_canonical(),
            indicator=expr.indicator,
            operator=expr.operator,
            lhs=expr.lhs,
            rhs=expr.rhs,
        )
        for expr in block.conditions
    ]
    return CompiledBlock(
        logical_operator=block.logical_operator.value,
        conditions=compiled_conditions,
    )


def compile_strategy(
    spec: StrategySpec,
    *,
    allowed_symbols: set[str] | None = None,
    strict: bool = False,
) -> CompiledStrategy:
    validation = validate_strategy(spec, allowed_symbols=allowed_symbols)
    if strict:
        validation.raise_if_invalid()

    return CompiledStrategy(
        name=spec.name,
        symbol=spec.symbol,
        timeframe=spec.timeframe,
        instrument_type=spec.instrument_type.value,
        entry=_compile_block(spec.entry),
        exit=_compile_block(spec.exit),
        risk=spec.risk.model_dump(mode="json", exclude_none=True),
        options=spec.options.model_dump(mode="json", exclude_none=True) if spec.options else None,
        indicators_used=spec.metadata.indicators_used,
        metadata=spec.metadata.model_dump(mode="json", exclude_none=True),
        validation=validation,
    )
