"""
Import project data files into PostgreSQL.

- streak_ai_backup_full.sql  -> ohlcv (TimescaleDB), options_chain, strategies
- company_profiles.csv       -> company_profiles
"""

from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = ROOT / "Raw Data"
SQL_DUMP = RAW_DATA_DIR / "streak_ai_backup_full.sql"
CSV_FILE = RAW_DATA_DIR / "company_profiles.csv"
COMPANY_SCHEMA = ROOT / "db" / "002_company_profiles.sql"
PREAMBLE_SQL = ROOT / "db" / "001_preamble.sql"

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
    if not SQL_DUMP.exists():
        raise FileNotFoundError(f"Missing SQL dump: {SQL_DUMP}")

    print(f"Copying {SQL_DUMP.name} into container ...")
    subprocess.run(
        ["docker", "cp", str(SQL_DUMP), f"{CONTAINER}:/tmp/streak_ai_backup_full.sql"],
        check=True,
    )

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

    print("Preparing dump inside container (binary-safe) ...")
    prep = docker_exec(
        [
            "bash",
            "-lc",
            "iconv -f UTF-16LE -t UTF-8 /tmp/streak_ai_backup_full.sql "
            "| sed '/^\\\\restrict/d;/^\\\\unrestrict/d' > /tmp/streak_ai_import.sql",
        ]
    )
    if prep.returncode != 0:
        print(prep.stdout)
        print(prep.stderr, file=sys.stderr)
        raise RuntimeError("Failed to preprocess SQL dump in container")

    print("Importing SQL dump (this may take several minutes) ...")
    run_psql_file_in_container("/tmp/001_preamble.sql")
    run_psql_file_in_container("/tmp/streak_ai_import.sql")
    print("SQL dump import complete.")


def import_company_profiles() -> None:
    if not CSV_FILE.exists():
        print("No company_profiles.csv found, skipping.")
        return

    subprocess.run(
        ["docker", "cp", str(COMPANY_SCHEMA), f"{CONTAINER}:/tmp/002_company_profiles.sql"],
        check=True,
    )
    print("Creating company_profiles table ...")
    run_psql_file_in_container("/tmp/002_company_profiles.sql")

    rows: list[tuple[str, str | None, str | None, str | None, str | None, str | None]] = []
    with CSV_FILE.open("r", encoding="utf-8", newline="") as handle:
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

    staging = ROOT / "db" / "_company_profiles_staging.csv"
    with staging.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        for row in rows:
            writer.writerow(row)

    subprocess.run(
        ["docker", "cp", str(staging), f"{CONTAINER}:/tmp/company_profiles_staging.csv"],
        check=True,
    )

    print(f"Loading {len(rows)} company profiles ...")
    copy_sql = (
        "TRUNCATE TABLE public.company_profiles;\n"
        "\\copy public.company_profiles (ticker, name, sector, industry, description, source) "
        "FROM '/tmp/company_profiles_staging.csv' WITH (FORMAT csv);\n"
    )
    result = docker_exec(["psql", "-v", "ON_ERROR_STOP=1", "-U", DB_USER, "-d", DB_NAME], input_text=copy_sql)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError("company_profiles import failed")

    staging.unlink(missing_ok=True)
    print("company_profiles import complete.")


def verify() -> None:
    checks = [
        "SELECT COUNT(*) AS strategies FROM public.strategies;",
        "SELECT COUNT(*) AS company_profiles FROM public.company_profiles;",
        "SELECT COUNT(*) AS ohlcv_rows FROM public.ohlcv;",
        "SELECT COUNT(*) AS options_chain_rows FROM public.options_chain;",
        "SELECT extname FROM pg_extension WHERE extname = 'timescaledb';",
        "SELECT hypertable_name FROM timescaledb_information.hypertables;",
    ]
    for query in checks:
        print(run_psql_sql(query))


def main() -> None:
    import_sql_dump()
    import_company_profiles()
    print("\nVerification:")
    verify()


if __name__ == "__main__":
    main()
