import psycopg2
from pathlib import Path
import os
import re
from dotenv import load_dotenv

# load .env
dotenv_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path)

db_url = os.environ.get("DATABASE_URL")
print(f"Connecting to: {db_url}")
conn = psycopg2.connect(db_url)
cur = conn.cursor()

# 1. Alter tables to add column
print("Adding 'indicator' column if not exists...")
cur.execute("ALTER TABLE public.strategies ADD COLUMN IF NOT EXISTS indicator TEXT;")
cur.execute("ALTER TABLE public.independent_strategies ADD COLUMN IF NOT EXISTS indicator TEXT;")
conn.commit()

# 2. Setup indicator list and extraction logic
INDICATORS = [
    "Aroon Oscillator", "Aroon Down", "Aroon Up", "Aroon",
    "ATR Bands", "ATR", "ADX Moving Average", "ADX MA", "ADX",
    "Alligator", "Bollinger Bands", "BBands", "CCI", "DEMA", "EMA",
    "MACD", "Momentum", "MOM", "ROC", "RSI MA", "Stochastic RSI",
    "Stochastic", "STOCH", "Supertrend", "TEMA", "VWAP MA", "VWAP",
    "Williams %R", "WillR", "Pivot Point", "Choppiness Index",
    "Ehler Fisher", "SMA", "Moving Average", "MA", "RSI"
]

# Sort by length descending to match longest first
INDICATORS_SORTED = sorted(INDICATORS, key=len, reverse=True)

def extract_indicators(name: str, hypothesis: str | None) -> str | None:
    # Use hypothesis primarily, fallback to name
    text = hypothesis or ""
    if not text:
        text = name

    found = []
    # Clean up punctuation/slashes
    cleaned = re.sub(r'[^a-zA-Z0-9%\s]', ' ', text)
    
    for ind in INDICATORS_SORTED:
        pattern = r'\b' + re.escape(ind) + r'\b'
        if re.search(pattern, cleaned, re.IGNORECASE):
            found.append(ind)
            # Remove matched text to prevent matching sub-parts
            cleaned = re.sub(pattern, ' ', cleaned, flags=re.IGNORECASE)
            
    # If still not found, try searching the name column
    if not found and hypothesis and name:
        cleaned_name = re.sub(r'[^a-zA-Z0-9%\s]', ' ', name)
        for ind in INDICATORS_SORTED:
            pattern = r'\b' + re.escape(ind) + r'\b'
            if re.search(pattern, cleaned_name, re.IGNORECASE):
                found.append(ind)
                cleaned_name = re.sub(pattern, ' ', cleaned_name, flags=re.IGNORECASE)

    if found:
        return ", ".join(found)
    return None

# 3. Process strategies table
print("Updating public.strategies table...")
cur.execute("SELECT id, name, hypothesis FROM public.strategies;")
rows = cur.fetchall()
updated_count = 0
for row_id, name, hypothesis in rows:
    indicator = extract_indicators(name, hypothesis)
    cur.execute(
        "UPDATE public.strategies SET indicator = %s WHERE id = %s;",
        (indicator, row_id)
    )
    updated_count += 1

print(f"Updated {updated_count} rows in public.strategies.")

# 4. Process independent_strategies table
print("Updating public.independent_strategies table...")
cur.execute("SELECT id, name, hypothesis FROM public.independent_strategies;")
rows = cur.fetchall()
updated_ind_count = 0
for row_id, name, hypothesis in rows:
    indicator = extract_indicators(name, hypothesis)
    cur.execute(
        "UPDATE public.independent_strategies SET indicator = %s WHERE id = %s;",
        (indicator, row_id)
    )
    updated_ind_count += 1

print(f"Updated {updated_ind_count} rows in public.independent_strategies.")
conn.commit()

# 5. Verify results
print("\nVerification (Sample output from strategies):")
cur.execute("SELECT name, hypothesis, indicator FROM public.strategies WHERE indicator IS NOT NULL LIMIT 10;")
samples = cur.fetchall()
for name, hyp, ind in samples:
    print(f"Name: {name}")
    print(f"Hypothesis: {hyp}")
    print(f"Extracted Indicator: {ind}")
    print("-" * 50)

conn.close()
print("Migration completed successfully.")
