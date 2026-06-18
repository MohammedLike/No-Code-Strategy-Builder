"""Normalize legacy database strategy rows into canonical StrategySpec."""

from __future__ import annotations

import json
import re
from typing import Any

from .models import (
    ConditionBlock,
    ConditionExpression,
    InstrumentType,
    LogicalOperator,
    OptionsLeg,
    OptionsSpec,
    RiskConfig,
    StrategyMetadata,
    StrategyRecord,
    StrategySpec,
)
from .parser import parse_condition_text
from .whitelist import TIMEFRAME_ALIASES, VALID_INSTRUMENT_TYPES


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {"condition": value}
    return {}


def _normalize_timeframe(value: str | None) -> str:
    if not value:
        return "1d"
    cleaned = value.strip().lower()
    return TIMEFRAME_ALIASES.get(cleaned, cleaned)


def _infer_instrument_type(category: str | None, entry: dict[str, Any]) -> InstrumentType:
    blob = json.dumps(entry).upper()
    if entry.get("instrument_type") == "OPTION" or "OPTION" in blob:
        return InstrumentType.OPTIONS
    if category and "option" in category.lower():
        return InstrumentType.OPTIONS
    if category and "futures" in category.lower():
        return InstrumentType.FUTURES
    if category and "index" in category.lower():
        return InstrumentType.INDEX
    return InstrumentType.EQUITY


def _structured_condition_to_expression(item: dict[str, Any]) -> ConditionExpression:
    indicator = str(item.get("indicator", "UNKNOWN")).upper()
    operator = str(item.get("operator", "=="))
    params = item.get("params") or {}
    value = item.get("value")

    param_text = ", ".join(f"{key}={val}" for key, val in params.items())
    lhs = f"{indicator}({param_text})" if param_text else indicator

    if isinstance(value, dict) and "indicator" in value:
        rhs_params = value.get("params") or {}
        rhs_param_text = ", ".join(f"{key}={val}" for key, val in rhs_params.items())
        rhs = f"{value['indicator']}({rhs_param_text})" if rhs_param_text else str(value["indicator"])
    else:
        rhs = str(value)

    raw = f"{lhs} {operator} {rhs}"
    return ConditionExpression(
        raw=raw,
        indicator=indicator,
        operator=operator.replace("crosses_above", "crosses_above").replace("crosses_below", "crosses_below"),
        lhs=lhs,
        rhs=rhs,
        params=params,
    )


def _block_from_rules(rules: dict[str, Any]) -> ConditionBlock:
    if not rules:
        return ConditionBlock()

    if "condition" in rules:
        expr = parse_condition_text(str(rules["condition"]))
        return ConditionBlock(
            conditions=[expr],
            logical_operator=LogicalOperator.AND,
        )

    if "conditions" in rules and isinstance(rules["conditions"], list):
        expressions: list[ConditionExpression] = []
        for item in rules["conditions"]:
            if isinstance(item, str):
                expressions.append(parse_condition_text(item))
            elif isinstance(item, dict) and "indicator" in item:
                expressions.append(_structured_condition_to_expression(item))
            elif isinstance(item, dict) and "condition" in item:
                expressions.append(parse_condition_text(str(item["condition"])))
            else:
                expressions.append(ConditionExpression(raw=json.dumps(item)))
        op = str(rules.get("logical_operator", "AND")).upper()
        return ConditionBlock(
            conditions=expressions,
            logical_operator=LogicalOperator(op if op in LogicalOperator.__members__ else "AND"),
        )

    if rules.get("option_type") or rules.get("instrument_type") == "OPTION":
        return ConditionBlock()

    if "side" in rules or "time" in rules:
        return ConditionBlock()

    return ConditionBlock(conditions=[ConditionExpression(raw=json.dumps(rules))])


def _options_from_rules(entry: dict[str, Any], exit_rules: dict[str, Any]) -> OptionsSpec | None:
    if not entry.get("option_type") and entry.get("instrument_type") != "OPTION":
        return None

    legs: list[OptionsLeg] = []
    if entry.get("option_type"):
        legs.append(
            OptionsLeg(
                option_type=str(entry.get("option_type")),
                strike=entry.get("strike"),
                side=entry.get("side"),
            )
        )

    return OptionsSpec(
        legs=legs,
        entry_time=entry.get("time"),
        option_type=entry.get("option_type"),
        strikes=[str(item) for item in entry.get("strikes", [])],
        side=entry.get("side"),
        raw={"entry": entry, "exit": exit_rules},
    )


def _risk_from_params(params: dict[str, Any], entry: dict[str, Any]) -> RiskConfig:
    risk = RiskConfig()

    stop = params.get("stop_loss") or params.get("stop_loss_pct")
    target = params.get("take_profit") or params.get("take_profit_pct")
    if isinstance(stop, str):
        match = re.search(r"([\d.]+)", stop)
        stop = float(match.group(1)) if match else None
    if isinstance(target, str):
        match = re.search(r"([\d.]+)", target)
        target = float(match.group(1)) if match else None

    risk.stop_loss_pct = float(stop) * 100 if isinstance(stop, (int, float)) and stop <= 1 else stop
    risk.take_profit_pct = float(target) * 100 if isinstance(target, (int, float)) and target <= 1 else target

    if "settings" in params and isinstance(params["settings"], str):
        settings = params["settings"]
        sl = re.search(r"stop\s*loss[:\s]*([\d.]+)\s*%?", settings, re.I)
        tp = re.search(r"(?:target|take\s*profit)[:\s]*([\d.]+)\s*%?", settings, re.I)
        if sl:
            risk.stop_loss_pct = float(sl.group(1))
        if tp:
            risk.take_profit_pct = float(tp.group(1))

    if entry.get("timeframe"):
        # timeframe lives on spec, not risk
        pass

    return risk


def _collect_indicators(spec: StrategySpec) -> list[str]:
    found: set[str] = set()
    for block in (spec.entry, spec.exit):
        for expr in block.conditions:
            if expr.indicator:
                found.add(expr.indicator.upper())
    return sorted(found)


def normalize_strategy_record(record: StrategyRecord | dict[str, Any]) -> StrategySpec:
    """Convert a `strategies` table row into canonical StrategySpec."""
    row = record if isinstance(record, StrategyRecord) else StrategyRecord.model_validate(record)

    entry_rules = _as_dict(row.entry_rules)
    exit_rules = _as_dict(row.exit_rules)
    risk_params = _as_dict(row.risk_params)
    metadata_blob = _as_dict(row.metadata)

    timeframe = _normalize_timeframe(
        entry_rules.get("timeframe")
        or risk_params.get("timeframe")
        or metadata_blob.get("timeframe")
    )

    instrument_type = _infer_instrument_type(row.category, entry_rules)
    options = _options_from_rules(entry_rules, exit_rules)

    spec = StrategySpec(
        name=row.name,
        instrument_type=instrument_type,
        symbol=str(metadata_blob.get("symbol") or "NIFTY"),
        timeframe=timeframe,
        entry=_block_from_rules(entry_rules),
        exit=_block_from_rules(exit_rules),
        risk=_risk_from_params(risk_params, entry_rules),
        options=options,
        metadata=StrategyMetadata(
            source_slug=row.slug,
            source_id=str(row.id) if row.id else None,
            nl_description=row.hypothesis,
            category=row.category,
            extra=metadata_blob,
        ),
    )
    spec.metadata.indicators_used = _collect_indicators(spec)
    return spec
