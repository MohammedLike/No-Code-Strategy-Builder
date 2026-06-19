"""Load strategies from the local Parquet cache."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from common import PARQUET_DIR

JSON_COLUMNS = {
    "strategies": ["entry_rules", "exit_rules", "risk_params", "backtest_results", "metadata"],
    "independent_strategies": ["entry_rules", "exit_rules", "risk_params", "strategy_metadata"],
    "pine_scripts": ["strategy_spec", "metadata"],
    "pine_indicators": ["params", "default_params", "inputs"],
}


def load_strategies(table: str = "strategies") -> pd.DataFrame:
    path = PARQUET_DIR / f"{table}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Parquet file not found: {path}")
    frame = pd.read_parquet(path)
    for column in JSON_COLUMNS.get(table, []):
        if column in frame.columns:
            frame[column] = frame[column].map(
                lambda value: json.loads(value) if isinstance(value, str) and value else value
            )
    return frame


def parquet_available(table: str = "strategies") -> bool:
    return (PARQUET_DIR / f"{table}.parquet").exists()
