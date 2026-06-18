"""
Import all files from raw_data/ into PostgreSQL.

- Excel files -> dedicated import tables + normalized strategies table
- company_profiles.csv -> upsert
"""

from __future__ import annotations

import csv
import json
import re
import sys
import uuid
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import DATABASE_URL, ROOT

RAW_DATA_DIR = ROOT / "raw_data"
SCHEMA_SQL = ROOT / "db" / "migrations" / "003_excel_tables.sql"


def slugify(text: str, prefix: str = "") -> str:
    base = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    slug = f"{prefix}-{base}" if prefix else base
    return slug[:120].strip("-")


def clean(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def run_sql_file(path: Path) -> None:
    with psycopg2.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute(path.read_text(encoding="utf-8"))
        conn.commit()


def truncate_excel_tables() -> None:
    tables = [
        "algo_bull_strategies",
        "finstock_strategies",
        "live_backtesting",
        "live_scanners",
        "streak_trading_strategies",
        "streak_indicator_suggestions",
    ]
    with psycopg2.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        for table in tables:
            cur.execute(f"TRUNCATE TABLE public.{table} RESTART IDENTITY")
        conn.commit()


def insert_rows(table: str, columns: list[str], rows: list[tuple]) -> int:
    if not rows:
        return 0
    cols = ", ".join(columns)
    sql = f"INSERT INTO public.{table} ({cols}) VALUES %s"
    with psycopg2.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        execute_values(cur, sql, rows)
        conn.commit()
    return len(rows)


def upsert_strategies(rows: list[tuple]) -> int:
    rows = dedupe_strategy_rows(rows)
    if not rows:
        return 0

    sql = """
        INSERT INTO public.strategies
            (id, name, slug, category, hypothesis, entry_rules, exit_rules, risk_params, metadata)
        VALUES %s
        ON CONFLICT (slug) DO UPDATE SET
            name = EXCLUDED.name,
            category = EXCLUDED.category,
            hypothesis = EXCLUDED.hypothesis,
            entry_rules = EXCLUDED.entry_rules,
            exit_rules = EXCLUDED.exit_rules,
            risk_params = EXCLUDED.risk_params,
            metadata = EXCLUDED.metadata
    """
    with psycopg2.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        execute_values(cur, sql, rows)
        conn.commit()
    return len(rows)


def strategy_row(
    name: str,
    source: str,
    *,
    category: str = "Imported",
    hypothesis: str | None = None,
    entry: str | None = None,
    exit_: str | None = None,
    risk: str | None = None,
    extra: dict | None = None,
    unique_key: str | None = None,
) -> tuple:
    prefix = slugify(Path(source).stem)
    slug_parts = [prefix, name]
    if unique_key:
        slug_parts.append(unique_key)
    slug = slugify("-".join(slug_parts))
    entry_rules = {"condition": entry} if entry else None
    exit_rules = {"condition": exit_} if exit_ else None
    risk_params = {"settings": risk} if risk else None
    metadata = {"source_file": source, **(extra or {})}
    return (
        str(uuid.uuid4()),
        name,
        slug,
        category,
        hypothesis,
        json.dumps(entry_rules) if entry_rules else None,
        json.dumps(exit_rules) if exit_rules else None,
        json.dumps(risk_params) if risk_params else None,
        json.dumps(metadata),
    )


def dedupe_strategy_rows(rows: list[tuple]) -> list[tuple]:
    deduped: dict[str, tuple] = {}
    for row in rows:
        deduped[row[2]] = row
    return list(deduped.values())


def import_algo_bull() -> tuple[int, int]:
    path = RAW_DATA_DIR / "Algo bull.xlsx"
    df = pd.read_excel(path)
    raw_rows = []
    strategy_rows = []

    for _, row in df.iterrows():
        name = clean(row["Strategy"]) or "Unknown Strategy"
        raw_rows.append(
            (
                clean(row["Strategy ID"]),
                name,
                clean(row["Type"]),
                clean(row["Underlying Asset"]),
                clean(row["Entry Time"]),
                clean(row["Exit Time"]),
                clean(row["Capital"]),
                clean(row["Description"]),
                path.name,
            )
        )
        strategy_rows.append(
            strategy_row(
                name,
                path.name,
                category=clean(row["Type"]) or "Options",
                hypothesis=clean(row["Description"]),
                entry=f"Entry at {clean(row['Entry Time'])} on {clean(row['Underlying Asset'])}",
                exit_=f"Exit at {clean(row['Exit Time'])}",
                risk=clean(row["Capital"]),
                extra={"strategy_id": clean(row["Strategy ID"])},
                unique_key=clean(row["Strategy ID"]),
            )
        )

    raw_count = insert_rows(
        "algo_bull_strategies",
        [
            "strategy_id",
            "strategy_name",
            "strategy_type",
            "underlying_asset",
            "entry_time",
            "exit_time",
            "capital",
            "description",
            "source_file",
        ],
        raw_rows,
    )
    return raw_count, upsert_strategies(strategy_rows)


def import_finstock() -> tuple[int, int]:
    path = RAW_DATA_DIR / "Finstock Pre Built Strategies.xlsx"
    df = pd.read_excel(path)
    raw_rows = []
    strategy_rows = []

    for idx, row in df.iterrows():
        name = clean(row["Strategy Name"]) or "Unknown Strategy"
        raw_rows.append(
            (
                int(row["Unnamed: 0"]) if pd.notna(row["Unnamed: 0"]) else None,
                name,
                clean(row["Description"]),
                clean(row["Entry Conditions"]),
                clean(row["Exit Conditions"]),
                clean(row["Risk Management"]),
                clean(row["Classification"]),
                path.name,
            )
        )
        strategy_rows.append(
            strategy_row(
                name,
                path.name,
                category=clean(row["Classification"]) or "Imported",
                hypothesis=clean(row["Description"]),
                entry=clean(row["Entry Conditions"]),
                exit_=clean(row["Exit Conditions"]),
                risk=clean(row["Risk Management"]),
                unique_key=str(idx + 1),
            )
        )

    raw_count = insert_rows(
        "finstock_strategies",
        [
            "row_num",
            "strategy_name",
            "description",
            "entry_conditions",
            "exit_conditions",
            "risk_management",
            "classification",
            "source_file",
        ],
        raw_rows,
    )
    return raw_count, upsert_strategies(strategy_rows)


def import_live_backtesting() -> tuple[int, int]:
    path = RAW_DATA_DIR / "live backtesting.xlsx"
    df = pd.read_excel(path)
    raw_rows = []
    strategy_rows = []

    for idx, row in df.iterrows():
        name = clean(row["Strategy Name"]) or "Unknown Strategy"
        category = clean(row["Category"]) or "Imported"
        direction = clean(row["Direction"])
        raw_rows.append((name, category, direction, path.name))
        strategy_rows.append(
            strategy_row(
                name,
                path.name,
                category=category,
                hypothesis=f"{direction} setup from live backtesting catalog",
                extra={"direction": direction},
                unique_key=str(idx + 1),
            )
        )

    raw_count = insert_rows(
        "live_backtesting",
        ["strategy_name", "category", "direction", "source_file"],
        raw_rows,
    )
    return raw_count, upsert_strategies(strategy_rows)


def import_live_scanners() -> int:
    path = RAW_DATA_DIR / "Live scanner.xlsx"
    df = pd.read_excel(path)
    rows = [
        (
            clean(row["Scanner Name"]) or "Unknown Scanner",
            clean(row["Category"]),
            clean(row["Direction"]),
            path.name,
        )
        for _, row in df.iterrows()
    ]
    return insert_rows(
        "live_scanners",
        ["scanner_name", "category", "direction", "source_file"],
        rows,
    )


def import_streak_trading() -> tuple[int, int]:
    path = RAW_DATA_DIR / "streak_trading_strategies.xlsx"
    df = pd.read_excel(path, sheet_name="Trading Strategies")
    raw_rows = []
    strategy_rows = []

    for idx, row in df.iterrows():
        name = clean(row["Strategy Name"]) or "Unknown Strategy"
        raw_rows.append(
            (
                name,
                clean(row["Description"]),
                clean(row["Entry Conditions"]),
                clean(row["Exit Conditions"]),
                clean(row["Risk Management Settings"]),
                clean(row["Strategy Tags/Classification"]),
                path.name,
            )
        )
        strategy_rows.append(
            strategy_row(
                name,
                path.name,
                category=clean(row["Strategy Tags/Classification"]) or "Imported",
                hypothesis=clean(row["Description"]),
                entry=clean(row["Entry Conditions"]),
                exit_=clean(row["Exit Conditions"]),
                risk=clean(row["Risk Management Settings"]),
                unique_key=str(idx + 1),
            )
        )

    raw_count = insert_rows(
        "streak_trading_strategies",
        [
            "strategy_name",
            "description",
            "entry_conditions",
            "exit_conditions",
            "risk_management",
            "classification",
            "source_file",
        ],
        raw_rows,
    )
    return raw_count, upsert_strategies(strategy_rows)


def import_streak_indicators() -> int:
    path = RAW_DATA_DIR / "Streak_Indicators_Final_Bullish_Bearish.xlsx"
    rows: list[tuple] = []

    lists_df = pd.read_excel(path, sheet_name="Lists")
    for _, row in lists_df.iterrows():
        indicator = clean(row["Indicator"])
        for bias, suggestion_col, tag_col in [
            ("Bearish", "Bearish Suggestion", "Tag"),
            ("Bullish", "Bullish Suggestion", "Tag.1"),
        ]:
            suggestion = clean(row.get(suggestion_col))
            if suggestion:
                rows.append(
                    (
                        "Lists",
                        indicator,
                        bias,
                        suggestion,
                        clean(row.get(tag_col)),
                        clean(row.get("Categories")),
                        None,
                        path.name,
                    )
                )

    indicators_df = pd.read_excel(path, sheet_name="Indicators")
    for _, row in indicators_df.iterrows():
        indicator = clean(row["Indicator Name"])
        operators = clean(row["Supported Condition Operators"])
        for bias, suggestion_col, tag_col in [
            ("Bearish", "Bearish Suggestion", "Tag"),
            ("Bullish", "Bullish Suggestion", "Tag.1"),
        ]:
            suggestion = clean(row.get(suggestion_col))
            if suggestion:
                rows.append(
                    (
                        "Indicators",
                        indicator,
                        bias,
                        suggestion,
                        clean(row.get(tag_col)),
                        None,
                        operators,
                        path.name,
                    )
                )

    return insert_rows(
        "streak_indicator_suggestions",
        [
            "sheet_name",
            "indicator",
            "bias",
            "suggestion",
            "tag",
            "category",
            "supported_operators",
            "source_file",
        ],
        rows,
    )


def import_company_profiles() -> int:
    path = RAW_DATA_DIR / "company_profiles.csv"
    if not path.exists():
        return 0

    rows: list[tuple[str, str | None, str | None, str | None, str | None, str | None]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                (
                    row.get("ticker", "").strip(),
                    row.get("name") or None,
                    row.get("sector") or None,
                    row.get("industry") or None,
                    row.get("description") or None,
                    row.get("source") or None,
                )
            )

    sql = """
        INSERT INTO public.company_profiles (ticker, name, sector, industry, description, source)
        VALUES %s
        ON CONFLICT (ticker) DO UPDATE SET
            name = EXCLUDED.name,
            sector = EXCLUDED.sector,
            industry = EXCLUDED.industry,
            description = EXCLUDED.description,
            source = EXCLUDED.source
    """
    with psycopg2.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        execute_values(cur, sql, rows)
        conn.commit()
    return len(rows)


def verify() -> None:
    queries = [
        "SELECT COUNT(*) AS strategies FROM public.strategies",
        "SELECT COUNT(*) AS company_profiles FROM public.company_profiles",
        "SELECT COUNT(*) AS algo_bull FROM public.algo_bull_strategies",
        "SELECT COUNT(*) AS finstock FROM public.finstock_strategies",
        "SELECT COUNT(*) AS live_backtesting FROM public.live_backtesting",
        "SELECT COUNT(*) AS live_scanners FROM public.live_scanners",
        "SELECT COUNT(*) AS streak_trading FROM public.streak_trading_strategies",
        "SELECT COUNT(*) AS indicator_suggestions FROM public.streak_indicator_suggestions",
    ]
    with psycopg2.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        for query in queries:
            cur.execute(query)
            print(f"{query.split('AS')[1].strip()}: {cur.fetchone()[0]}")


def main() -> None:
    print("Creating raw Excel tables ...")
    run_sql_file(SCHEMA_SQL)
    print("Truncating Excel import tables for fresh import ...")
    truncate_excel_tables()

    print("Importing Algo bull.xlsx ...")
    raw, merged = import_algo_bull()
    print(f"  raw={raw}, strategies upserted={merged}")

    print("Importing Finstock Pre Built Strategies.xlsx ...")
    raw, merged = import_finstock()
    print(f"  raw={raw}, strategies upserted={merged}")

    print("Importing live backtesting.xlsx ...")
    raw, merged = import_live_backtesting()
    print(f"  raw={raw}, strategies upserted={merged}")

    print("Importing Live scanner.xlsx ...")
    print(f"  raw={import_live_scanners()}")

    print("Importing streak_trading_strategies.xlsx ...")
    raw, merged = import_streak_trading()
    print(f"  raw={raw}, strategies upserted={merged}")

    print("Importing Streak_Indicators_Final_Bullish_Bearish.xlsx ...")
    print(f"  raw={import_streak_indicators()}")

    print("Upserting company_profiles.csv ...")
    print(f"  rows={import_company_profiles()}")

    print("\nVerification:")
    verify()


if __name__ == "__main__":
    main()
