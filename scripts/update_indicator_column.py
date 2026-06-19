import psycopg2
import sys
import re
from pathlib import Path
import os
from dotenv import load_dotenv

# load .env
dotenv_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path)

sys.path.insert(0, str(dotenv_path.parent))

from backend.strategy.normalizer import normalize_strategy_record

db_url = os.environ.get("DATABASE_URL")
print(f"Connecting to: {db_url}")
conn = psycopg2.connect(db_url)
cur = conn.cursor()

clean_suffix_pat = re.compile(r'\s+(strategy|setup|bearish\s+setup|bullish\s+setup)\b', re.IGNORECASE)

def extract_indicator(row_dict: dict) -> str:
    # 1. Try normalizer indicators
    try:
        # map strategy_metadata to metadata if present (for independent_strategies)
        if "strategy_metadata" in row_dict and "metadata" not in row_dict:
            row_dict["metadata"] = row_dict["strategy_metadata"]
            
        spec = normalize_strategy_record(row_dict)
        if spec.metadata.indicators_used:
            return ", ".join(spec.metadata.indicators_used)
    except Exception as exc:
        pass
        
    # 2. Fallback to name-based clean up
    name_clean = clean_suffix_pat.sub('', row_dict['name']).strip()
    name_clean = re.sub(r'\s+', ' ', name_clean)
    return name_clean or 'UNKNOWN'


# Update public.strategies
print("Updating public.strategies table...")
cur.execute("SELECT id, name, category, hypothesis, entry_rules, exit_rules, risk_params, metadata FROM public.strategies;")
rows = cur.fetchall()
columns = ["id", "name", "category", "hypothesis", "entry_rules", "exit_rules", "risk_params", "metadata"]

updated = 0
for r in rows:
    row_dict = dict(zip(columns, r))
    indicator = extract_indicator(row_dict)
    cur.execute(
        "UPDATE public.strategies SET indicator = %s WHERE id = %s;",
        (indicator, row_dict["id"])
    )
    updated += 1
print(f"Successfully updated {updated} rows in public.strategies.")

# Update public.independent_strategies
print("Updating public.independent_strategies table...")
cur.execute("SELECT id, name, category, hypothesis, entry_rules, exit_rules, risk_params, strategy_metadata FROM public.independent_strategies;")
rows_ind = cur.fetchall()
columns_ind = ["id", "name", "category", "hypothesis", "entry_rules", "exit_rules", "risk_params", "strategy_metadata"]

updated_ind = 0
for r in rows_ind:
    row_dict = dict(zip(columns_ind, r))
    indicator = extract_indicator(row_dict)
    cur.execute(
        "UPDATE public.independent_strategies SET indicator = %s WHERE id = %s;",
        (indicator, row_dict["id"])
    )
    updated_ind += 1
print(f"Successfully updated {updated_ind} rows in public.independent_strategies.")

conn.commit()

# Verification check for nulls
cur.execute("SELECT COUNT(*) FROM public.strategies WHERE indicator IS NULL;")
nulls = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM public.independent_strategies WHERE indicator IS NULL;")
nulls_ind = cur.fetchone()[0]

print(f"\nVerification Results:")
print(f"  strategies table null count: {nulls}")
print(f"  independent_strategies table null count: {nulls_ind}")

conn.close()
print("Backfill update completed successfully.")
