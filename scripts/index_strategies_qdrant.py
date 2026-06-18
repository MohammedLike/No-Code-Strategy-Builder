"""Index strategies from PostgreSQL into Qdrant (legacy entrypoint)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from index_all_qdrant import index_all_tables

if __name__ == "__main__":
    index_all_tables()
