"""Pydantic models for the canonical Strategy DSL."""

from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class InstrumentType(str, Enum):
    EQUITY = "EQUITY"
    FUTURES = "FUTURES"
    OPTIONS = "OPTIONS"
    INDEX = "INDEX"


class LogicalOperator(str, Enum):
    AND = "AND"
    OR = "OR"


class PositionSizeType(str, Enum):
    PERCENT_EQUITY = "percent_equity"
    FIXED_QTY = "fixed_qty"
    FIXED_CAPITAL = "fixed_capital"


class ConditionExpression(BaseModel):
    """A single rule, either parsed or preserved as raw Streak text."""

    raw: str
    indicator: str | None = None
    operator: str | None = None
    lhs: str | None = None
    rhs: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)

    def to_canonical(self) -> str:
        if self.lhs and self.operator and self.rhs is not None:
            op = self.operator.replace("_", " ")
            return f"{self.lhs} {op} {self.rhs}"
        return self.raw


class ConditionBlock(BaseModel):
    conditions: list[ConditionExpression] = Field(default_factory=list)
    logical_operator: LogicalOperator = LogicalOperator.AND

    @field_validator("conditions", mode="before")
    @classmethod
    def coerce_string_conditions(cls, value: Any) -> Any:
        if value is None:
            return []
        if isinstance(value, list) and value and isinstance(value[0], str):
            return [{"raw": item} for item in value]
        return value


class RiskConfig(BaseModel):
    stop_loss_pct: float | None = Field(default=None, ge=0, le=100)
    take_profit_pct: float | None = Field(default=None, ge=0, le=100)
    position_size: PositionSizeType = PositionSizeType.PERCENT_EQUITY
    size_value: float = Field(default=10.0, gt=0)
    trailing_stop_pct: float | None = Field(default=None, ge=0, le=100)

    @field_validator("stop_loss_pct", "take_profit_pct", "trailing_stop_pct", mode="before")
    @classmethod
    def normalize_percent(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip().replace("%", "")
            if not cleaned:
                return None
            return float(cleaned)
        if isinstance(value, (int, float)) and 0 < float(value) <= 1:
            return float(value) * 100
        return value


class OptionsLeg(BaseModel):
    option_type: str
    strike: str | float | None = None
    side: str | None = None


class OptionsSpec(BaseModel):
    legs: list[OptionsLeg] = Field(default_factory=list)
    entry_time: str | None = None
    exit_time: str | None = None
    option_type: str | None = None
    strikes: list[str] = Field(default_factory=list)
    side: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class StrategyMetadata(BaseModel):
    source_slug: str | None = None
    source_id: str | None = None
    source_file: str | None = None
    nl_description: str | None = None
    category: str | None = None
    indicators_used: list[str] = Field(default_factory=list)
    distilled_at: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class StrategySpec(BaseModel):
    """Canonical strategy contract — compiler input."""

    name: str
    instrument_type: InstrumentType = InstrumentType.EQUITY
    symbol: str = "NIFTY"
    timeframe: str = "1d"
    entry: ConditionBlock = Field(default_factory=ConditionBlock)
    exit: ConditionBlock = Field(default_factory=ConditionBlock)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    options: OptionsSpec | None = None
    metadata: StrategyMetadata = Field(default_factory=StrategyMetadata)

    def model_dump_canonical(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


class StrategyRecord(BaseModel):
    """Database row shape used by the normalizer."""

    id: UUID | str | None = None
    name: str
    slug: str | None = None
    category: str | None = None
    hypothesis: str | None = None
    indicator: str | None = None
    entry_rules: dict[str, Any] | None = None
    exit_rules: dict[str, Any] | None = None
    risk_params: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
