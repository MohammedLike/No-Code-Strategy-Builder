from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = ROOT / "Raw Data"
load_dotenv(ROOT / ".env")

DATABASE_URL = os.environ["DATABASE_URL"]
PARQUET_DIR = Path(os.environ.get("PARQUET_DIR", "data/strategies_parquet"))
if not PARQUET_DIR.is_absolute():
    PARQUET_DIR = ROOT / PARQUET_DIR
QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "strategies")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

PARQUET_DIR.mkdir(parents=True, exist_ok=True)
