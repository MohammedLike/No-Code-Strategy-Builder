import os
import re
import sys
from pathlib import Path
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# load .env
dotenv_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path)

db_url = os.environ.get("DATABASE_URL")
raw_data_dir = Path(__file__).resolve().parents[1] / "raw_data"
path = raw_data_dir / "Streak_Indicators_Final_Bullish_Bearish.xlsx"

print(f"Excel file exists: {path.exists()}")
if not path.exists():
    sys.exit(1)

def clean(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None

conn = psycopg2.connect(db_url)
cur = conn.cursor()

# 1. Create table
print("Re-creating public.streak_indicator_suggestions table...")
cur.execute("""
    CREATE TABLE IF NOT EXISTS public.streak_indicator_suggestions (
        id SERIAL PRIMARY KEY,
        sheet_name TEXT NOT NULL,
        indicator TEXT,
        bias TEXT,
        suggestion TEXT,
        tag TEXT,
        category TEXT,
        supported_operators TEXT,
        source_file TEXT NOT NULL DEFAULT 'Streak_Indicators_Final_Bullish_Bearish.xlsx',
        imported_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
""")
cur.execute("TRUNCATE TABLE public.streak_indicator_suggestions RESTART IDENTITY;")
conn.commit()

# 2. Extract and parse excel sheets
rows = []

print("Parsing sheet 'Lists'...")
lists_df = pd.read_excel(path, sheet_name="Lists")
# Forward-fill Indicator column in case of merged cells
lists_df["Indicator"] = lists_df["Indicator"].ffill()

for _, row in lists_df.iterrows():
    indicator = clean(row.get("Indicator"))
    if not indicator:
        continue
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

print("Parsing sheet 'Indicators'...")
indicators_df = pd.read_excel(path, sheet_name="Indicators")
indicators_df["Indicator Name"] = indicators_df["Indicator Name"].ffill()

for _, row in indicators_df.iterrows():
    indicator = clean(row.get("Indicator Name"))
    if not indicator:
        continue
    operators = clean(row.get("Supported Condition Operators"))
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

# 3. Insert rows
if rows:
    print(f"Inserting {len(rows)} rows into public.streak_indicator_suggestions...")
    sql = """
        INSERT INTO public.streak_indicator_suggestions
            (sheet_name, indicator, bias, suggestion, tag, category, supported_operators, source_file)
        VALUES %s
    """
    execute_values(cur, sql, rows)
    conn.commit()
    print("Insertion complete.")

# 4. Verify count
cur.execute("SELECT COUNT(*) FROM public.streak_indicator_suggestions;")
count = cur.fetchone()[0]
print(f"Verification: {count} rows in public.streak_indicator_suggestions.")

conn.close()
