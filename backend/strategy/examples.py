"""Example canonical Strategy DSL documents."""

RSI_MEAN_REVERSION = {
    "name": "Nifty RSI Mean Reversion",
    "instrument_type": "EQUITY",
    "symbol": "NIFTY",
    "timeframe": "1d",
    "entry": {
        "conditions": [
            {
                "raw": "RSI(14,0) < 30",
                "indicator": "RSI",
                "operator": "<",
                "lhs": "RSI(14,0)",
                "rhs": "30",
                "params": {"timeperiod": 14},
            },
            {
                "raw": "SMA(20,0) > SMA(50,0)",
                "indicator": "SMA",
                "operator": ">",
                "lhs": "SMA(20,0)",
                "rhs": "SMA(50,0)",
            },
        ],
        "logical_operator": "AND",
    },
    "exit": {
        "conditions": [
            {
                "raw": "RSI(14,0) > 70",
                "indicator": "RSI",
                "operator": ">",
                "lhs": "RSI(14,0)",
                "rhs": "70",
            }
        ],
        "logical_operator": "AND",
    },
    "risk": {
        "stop_loss_pct": 2.0,
        "take_profit_pct": 5.0,
        "position_size": "percent_equity",
        "size_value": 10,
    },
    "options": None,
    "metadata": {
        "source_slug": "rsi-oversold-bounce",
        "nl_description": "Buy when RSI drops below 30 on daily Nifty with SMA trend filter.",
        "category": "Mean Reversion",
        "indicators_used": ["RSI", "SMA"],
    },
}

OPTIONS_SHORT_STRADDLE = {
    "name": "9:20 Short Straddle",
    "instrument_type": "OPTIONS",
    "symbol": "BANKNIFTY",
    "timeframe": "5m",
    "entry": {"conditions": [], "logical_operator": "AND"},
    "exit": {"conditions": [], "logical_operator": "AND"},
    "risk": {"stop_loss_pct": 25.0, "take_profit_pct": 40.0, "position_size": "percent_equity", "size_value": 10},
    "options": {
        "option_type": "STRADDLE",
        "side": "SELL",
        "entry_time": "09:20",
        "strikes": ["ATM"],
        "legs": [{"option_type": "STRADDLE", "strike": "ATM", "side": "SELL"}],
    },
    "metadata": {
        "source_slug": "920-short-straddle",
        "category": "Options",
        "nl_description": "Sell ATM straddle at 9:20 to capture morning IV crush.",
    },
}
