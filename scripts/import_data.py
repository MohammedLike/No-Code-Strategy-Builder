"""
Import project data files into PostgreSQL.

- data.gz  -> import all tables (strategies, independent_strategies, pine_scripts, pine_indicators, backtests, ingest_jobs, ohlcv, options_chain, ticks)
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
import psycopg2
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
SQL_DUMP_GZ = ROOT / "data.gz"
PREAMBLE_SQL = ROOT / "db" / "migrations" / "001_preamble.sql"

CONTAINER = os.environ.get("POSTGRES_CONTAINER", "ai-builder-postgres")
DB_USER = os.environ.get("POSTGRES_USER", "postgres")
DB_NAME = os.environ.get("POSTGRES_DB", "ai_strategy_builder")
DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "ai_builder_dev")


def docker_exec(args: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PGPASSWORD"] = DB_PASSWORD
    return subprocess.run(
        ["docker", "exec", "-i", CONTAINER, *args],
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )


def run_psql_file_in_container(container_path: str) -> None:
    result = docker_exec(
        ["psql", "-v", "ON_ERROR_STOP=1", "-U", DB_USER, "-d", DB_NAME, "-f", container_path]
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"psql failed for {container_path}")


def run_psql_sql(sql: str) -> str:
    result = docker_exec(["psql", "-v", "ON_ERROR_STOP=1", "-U", DB_USER, "-d", DB_NAME, "-c", sql])
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError("psql command failed")
    return result.stdout.strip()


def import_sql_dump() -> None:
    if not SQL_DUMP_GZ.exists():
        raise FileNotFoundError(f"Missing SQL dump: {SQL_DUMP_GZ}")

    print(f"Copying {SQL_DUMP_GZ.name} into container ...")
    subprocess.run(
        ["docker", "cp", str(SQL_DUMP_GZ), f"{CONTAINER}:/tmp/data.gz"],
        check=True,
    )

    if PREAMBLE_SQL.exists():
        subprocess.run(
            ["docker", "cp", str(PREAMBLE_SQL), f"{CONTAINER}:/tmp/001_preamble.sql"],
            check=True,
        )
    else:
        # Create a preamble role creation helper
        PREAMBLE_SQL.parent.mkdir(parents=True, exist_ok=True)
        PREAMBLE_SQL.write_text(
            "DO $$ BEGIN\n"
            "  CREATE ROLE quant_user WITH LOGIN SUPERUSER PASSWORD 'quant_user';\n"
            "EXCEPTION WHEN duplicate_object THEN NULL;\n"
            "END $$;\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["docker", "cp", str(PREAMBLE_SQL), f"{CONTAINER}:/tmp/001_preamble.sql"],
            check=True,
        )

    print("Extracting and preparing dump inside container ...")
    unzip_res = docker_exec(["bash", "-lc", "gunzip -f /tmp/data.gz"])
    if unzip_res.returncode != 0:
        print(unzip_res.stdout)
        print(unzip_res.stderr, file=sys.stderr)
        raise RuntimeError("Failed to gunzip SQL dump in container")

    prep = docker_exec(
        [
            "bash",
            "-lc",
            "sed '/^\\\\restrict/d;/^\\\\unrestrict/d' /tmp/data > /tmp/data_import.sql",
        ]
    )
    if prep.returncode != 0:
        print(prep.stdout)
        print(prep.stderr, file=sys.stderr)
        raise RuntimeError("Failed to preprocess SQL dump in container")

    print("Importing SQL dump (this may take several minutes) ...")
    run_psql_file_in_container("/tmp/001_preamble.sql")
    run_psql_file_in_container("/tmp/data_import.sql")

    # Clean up temporary files inside container
    docker_exec(["bash", "-lc", "rm -f /tmp/001_preamble.sql /tmp/data /tmp/data_import.sql"])
    print("SQL dump import complete.")


def verify() -> None:
    checks = [
        "SELECT COUNT(*) AS strategies FROM public.strategies;",
        "SELECT COUNT(*) AS independent_strategies FROM public.independent_strategies;",
        "SELECT COUNT(*) AS pine_scripts FROM public.pine_scripts;",
        "SELECT COUNT(*) AS pine_indicators FROM public.pine_indicators;",
        "SELECT COUNT(*) AS backtests FROM public.backtests;",
        "SELECT COUNT(*) AS ingest_jobs FROM public.ingest_jobs;",
        "SELECT COUNT(*) AS ohlcv_rows FROM public.ohlcv;",
        "SELECT COUNT(*) AS options_chain_rows FROM public.options_chain;",
        "SELECT COUNT(*) AS ticks_rows FROM public.ticks;",
        "SELECT extname FROM pg_extension WHERE extname = 'timescaledb';",
        "SELECT hypertable_name FROM timescaledb_information.hypertables;",
    ]
    for query in checks:
        print(f"\nQuery: {query}")
        try:
            print(run_psql_sql(query))
        except Exception as exc:
            print(f"Failed to verify: {exc}")


def main() -> None:
    import_sql_dump()

    # Run the 005_indicator_not_null.sql migration steps and python backfill
    print("\nApplying indicator column migrations and backfill...")
    load_dotenv(ROOT / ".env")
    db_url = os.environ.get("DATABASE_URL") or f"postgresql://{DB_USER}:{DB_PASSWORD}@localhost:5430/{DB_NAME}"

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            # 1. Ensure the column exists (nullable initially)
            print("  Ensuring indicator column exists...")
            cur.execute("ALTER TABLE public.strategies ADD COLUMN IF NOT EXISTS indicator TEXT;")
            cur.execute("ALTER TABLE public.independent_strategies ADD COLUMN IF NOT EXISTS indicator TEXT;")
            conn.commit()

    # 2. Run indicator backfill using update_indicator_column.py
    print("  Running indicator backfill script...")
    res = subprocess.run([sys.executable, str(ROOT / "scripts" / "update_indicator_column.py")], capture_output=True, text=True)
    if res.returncode != 0:
        print("Backfill error output:")
        print(res.stderr)
        raise RuntimeError("Indicator backfill failed during import")
    print(res.stdout)

    # 3. Alter columns to set DEFAULT and NOT NULL
    print("  Enforcing NOT NULL and DEFAULT on indicator column...")
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE public.strategies SET indicator = 'UNKNOWN' WHERE indicator IS NULL OR TRIM(indicator) = '';")
            cur.execute("ALTER TABLE public.strategies ALTER COLUMN indicator SET DEFAULT 'UNKNOWN';")
            cur.execute("ALTER TABLE public.strategies ALTER COLUMN indicator SET NOT NULL;")

            cur.execute("UPDATE public.independent_strategies SET indicator = 'UNKNOWN' WHERE indicator IS NULL OR TRIM(indicator) = '';")
            cur.execute("ALTER TABLE public.independent_strategies ALTER COLUMN indicator SET DEFAULT 'UNKNOWN';")
            cur.execute("ALTER TABLE public.independent_strategies ALTER COLUMN indicator SET NOT NULL;")
            conn.commit()
    print("Migration and backfill applied successfully.")

    print("\nVerification:")
    verify()


if __name__ == "__main__":
    main()
