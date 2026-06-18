"""Compiler whitelist: supported indicators, operators, timeframes."""

from __future__ import annotations

# Core indicators the compiler must support in v1 (plan: 15)
CORE_INDICATORS: frozenset[str] = frozenset(
    {
        "RSI",
        "SMA",
        "EMA",
        "MACD",
        "ADX",
        "CCI",
        "SUPERTREND",
        "ATR",
        "BBANDS",
        "STOCH",
        "MOM",
        "ROC",
        "WILLR",
        "VWAP",
        "DEMA",
    }
)

# Additional indicators seen in imported Streak data (parsed + stored, may warn at compile)
EXTENDED_INDICATORS: frozenset[str] = frozenset(
    {
        "ALLIGATOR",
        "AROON",
        "AROON_OSCILLATOR",
        "AROON DOWN",
        "AROON UP",
        "ADX MA",
        "RSI MA",
        "STOCHASTIC RSI",
        "PROC",
        "DEMA",
        "TEMA",
        "VWAP MA",
        "PIVOT POINT",
        "PIVOT POINT",
        "CHOPPINESS INDEX",
        "EHLER FISHER",
        "MINUS DI",
        "PLUS DI",
        "HIGH",
        "LOW",
        "CLOSE",
        "OPEN",
        "VOLUME",
        "UBB",
        "LBB",
        "WILLIAMS %R",
    }
)

KNOWN_INDICATORS = CORE_INDICATORS | EXTENDED_INDICATORS

# Canonical operators (plan: 8)
OPERATORS: frozenset[str] = frozenset(
    {
        "<",
        ">",
        "<=",
        ">=",
        "==",
        "!=",
        "crosses_above",
        "crosses_below",
    }
)

OPERATOR_ALIASES: dict[str, str] = {
    "lower than": "<",
    "higher than": ">",
    "lower than equal to": "<=",
    "higher than equal to": ">=",
    "equal to": "==",
    "not equal to": "!=",
    "crosses above": "crosses_above",
    "crosses below": "crosses_below",
    "crosses_above": "crosses_above",
    "crosses_below": "crosses_below",
}

VALID_TIMEFRAMES: frozenset[str] = frozenset(
    {"1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"}
)

TIMEFRAME_ALIASES: dict[str, str] = {
    "1min": "1m",
    "5min": "5m",
    "15min": "15m",
    "30min": "30m",
    "60min": "1h",
    "1day": "1d",
    "daily": "1d",
}

VALID_INSTRUMENT_TYPES: frozenset[str] = frozenset({"EQUITY", "FUTURES", "OPTIONS", "INDEX"})
