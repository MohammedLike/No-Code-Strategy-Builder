"""
Bootstrap the speed layer:
1. PostgreSQL strategies -> Parquet files
2. PostgreSQL strategies -> Qdrant vectors
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sync_strategies_to_parquet import export_all
from index_all_qdrant import index_all_tables


def main() -> None:
    print("=== Step 1: Strategies -> Parquet ===")
    export_all()
    print("\n=== Step 2: All tables -> Qdrant ===")
    index_all_tables()
    print("\nSpeed layer ready.")


if __name__ == "__main__":
    main()
