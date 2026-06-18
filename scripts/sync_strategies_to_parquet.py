"""
Export strategies from PostgreSQL into Parquet files.

Layout:
  data/strategies_parquet/strategies.parquet
  data/strategies_parquet/algo_bull_strategies.parquet
  data/strategies_parquet/finstock_strategies.parquet
  ... (one file per strategies-related table)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import json

import pandas as pd

from common import DATABASE_URL, PARQUET_DIR

STRATEGY_TABLES = [
    "strategies",
    "algo_bull_strategies",
    "finstock_strategies",
    "live_backtesting",
    "streak_trading_strategies",
    "streak_indicator_suggestions",
]

JSON_COLUMNS = {
    "strategies": ["entry_rules", "exit_rules", "risk_params", "backtest_results", "metadata"],
}


def normalize_frame(table: str, frame: pd.DataFrame) -> pd.DataFrame:
    for column in JSON_COLUMNS.get(table, []):
        if column in frame.columns:
            frame[column] = frame[column].map(
                lambda value: json.dumps(value) if isinstance(value, (dict, list)) else value
            )
    return frame


def export_table(table: str) -> int:
    frame = pd.read_sql(f"SELECT * FROM public.{table} ORDER BY 1", DATABASE_URL)
    if frame.empty:
        return 0

    frame = normalize_frame(table, frame)
    out_path = PARQUET_DIR / f"{table}.parquet"
    frame.to_parquet(out_path, index=False, compression="zstd")
    print(f"  {out_path.name}  ({len(frame)} rows)")
    return len(frame)


def export_all() -> None:
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)

    # Remove legacy OHLCV parquet tree if it still exists
    legacy_ohlcv_dir = PARQUET_DIR.parent / "ohlcv_parquet"
    if legacy_ohlcv_dir.exists():
        import shutil

        shutil.rmtree(legacy_ohlcv_dir)
        print(f"Removed legacy folder: {legacy_ohlcv_dir}")

    print(f"Exporting strategy tables to {PARQUET_DIR} ...")
    total = 0
    for table in STRATEGY_TABLES:
        total += export_table(table)
    print(f"Parquet export complete ({total} total rows).")


if __name__ == "__main__":
    try:
        export_all()
    except Exception as exc:
        print(f"Parquet export failed: {exc}", file=sys.stderr)
        raise
