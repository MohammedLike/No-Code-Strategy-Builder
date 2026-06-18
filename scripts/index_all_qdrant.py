"""
Index all PostgreSQL tables into Qdrant collections for fast semantic retrieval.
"""

from __future__ import annotations

import json
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg2
from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from common import DATABASE_URL, EMBEDDING_MODEL, QDRANT_HOST, QDRANT_PORT

BATCH_SIZE = 64
POINT_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def stable_point_id(key: str) -> str:
    return str(uuid.uuid5(POINT_NAMESPACE, key))


def int_point_id(row_id: int | str) -> int:
    return int(row_id)


@dataclass(frozen=True)
class TableIndexConfig:
    collection: str
    sql: str
    point_id: Callable[[dict[str, Any]], str]
    document: Callable[[dict[str, Any]], str]
    payload: Callable[[dict[str, Any]], dict[str, Any]]


def _join_parts(parts: list[str | None]) -> str:
    return "\n".join(part for part in parts if part)


def _fetch_rows(sql: str) -> list[dict[str, Any]]:
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]


def _strategy_document(row: dict[str, Any]) -> str:
    return _join_parts(
        [
            f"Name: {row.get('name')}",
            f"Slug: {row.get('slug')}",
            f"Category: {row.get('category')}",
            f"Hypothesis: {row.get('hypothesis')}",
            f"Entry rules: {json.dumps(row.get('entry_rules'), ensure_ascii=False)}" if row.get("entry_rules") else None,
            f"Exit rules: {json.dumps(row.get('exit_rules'), ensure_ascii=False)}" if row.get("exit_rules") else None,
            f"Risk params: {json.dumps(row.get('risk_params'), ensure_ascii=False)}" if row.get("risk_params") else None,
        ]
    )


TABLE_CONFIGS: list[TableIndexConfig] = [
    TableIndexConfig(
        collection="strategies",
        sql="""
            SELECT id::text AS id, name, slug, category, hypothesis,
                   entry_rules, exit_rules, risk_params, metadata, created_at
            FROM public.strategies
            ORDER BY created_at
        """,
        point_id=lambda row: str(row["id"]),
        document=_strategy_document,
        payload=lambda row: {
            "source_table": "strategies",
            "record_id": str(row["id"]),
            "name": row.get("name"),
            "slug": row.get("slug"),
            "category": row.get("category"),
            "hypothesis": row.get("hypothesis"),
        },
    ),
    TableIndexConfig(
        collection="algo_bull_strategies",
        sql="""
            SELECT id, strategy_id, strategy_name, strategy_type, underlying_asset,
                   entry_time, exit_time, capital, description, source_file
            FROM public.algo_bull_strategies
            ORDER BY id
        """,
        point_id=lambda row: int_point_id(row["id"]),
        document=lambda row: _join_parts(
            [
                f"Strategy: {row.get('strategy_name')}",
                f"ID: {row.get('strategy_id')}",
                f"Type: {row.get('strategy_type')}",
                f"Underlying: {row.get('underlying_asset')}",
                f"Entry: {row.get('entry_time')}",
                f"Exit: {row.get('exit_time')}",
                f"Capital: {row.get('capital')}",
                f"Description: {row.get('description')}",
            ]
        ),
        payload=lambda row: {"source_table": "algo_bull_strategies", "record_id": row["id"], **row},
    ),
    TableIndexConfig(
        collection="finstock_strategies",
        sql="""
            SELECT id, row_num, strategy_name, description, entry_conditions,
                   exit_conditions, risk_management, classification, source_file
            FROM public.finstock_strategies
            ORDER BY id
        """,
        point_id=lambda row: int_point_id(row["id"]),
        document=lambda row: _join_parts(
            [
                f"Strategy: {row.get('strategy_name')}",
                f"Classification: {row.get('classification')}",
                f"Description: {row.get('description')}",
                f"Entry: {row.get('entry_conditions')}",
                f"Exit: {row.get('exit_conditions')}",
                f"Risk: {row.get('risk_management')}",
            ]
        ),
        payload=lambda row: {"source_table": "finstock_strategies", "record_id": row["id"], **row},
    ),
    TableIndexConfig(
        collection="live_backtesting",
        sql="""
            SELECT id, strategy_name, category, direction, source_file
            FROM public.live_backtesting
            ORDER BY id
        """,
        point_id=lambda row: int_point_id(row["id"]),
        document=lambda row: _join_parts(
            [
                f"Strategy: {row.get('strategy_name')}",
                f"Category: {row.get('category')}",
                f"Direction: {row.get('direction')}",
            ]
        ),
        payload=lambda row: {"source_table": "live_backtesting", "record_id": row["id"], **row},
    ),
    TableIndexConfig(
        collection="live_scanners",
        sql="""
            SELECT id, scanner_name, category, direction, source_file
            FROM public.live_scanners
            ORDER BY id
        """,
        point_id=lambda row: int_point_id(row["id"]),
        document=lambda row: _join_parts(
            [
                f"Scanner: {row.get('scanner_name')}",
                f"Category: {row.get('category')}",
                f"Direction: {row.get('direction')}",
            ]
        ),
        payload=lambda row: {"source_table": "live_scanners", "record_id": row["id"], **row},
    ),
    TableIndexConfig(
        collection="streak_trading_strategies",
        sql="""
            SELECT id, strategy_name, description, entry_conditions, exit_conditions,
                   risk_management, classification, source_file
            FROM public.streak_trading_strategies
            ORDER BY id
        """,
        point_id=lambda row: int_point_id(row["id"]),
        document=lambda row: _join_parts(
            [
                f"Strategy: {row.get('strategy_name')}",
                f"Classification: {row.get('classification')}",
                f"Description: {row.get('description')}",
                f"Entry: {row.get('entry_conditions')}",
                f"Exit: {row.get('exit_conditions')}",
                f"Risk: {row.get('risk_management')}",
            ]
        ),
        payload=lambda row: {"source_table": "streak_trading_strategies", "record_id": row["id"], **row},
    ),
    TableIndexConfig(
        collection="streak_indicator_suggestions",
        sql="""
            SELECT id, sheet_name, indicator, bias, suggestion, tag, category, supported_operators
            FROM public.streak_indicator_suggestions
            ORDER BY id
        """,
        point_id=lambda row: int_point_id(row["id"]),
        document=lambda row: _join_parts(
            [
                f"Indicator: {row.get('indicator')}",
                f"Bias: {row.get('bias')}",
                f"Suggestion: {row.get('suggestion')}",
                f"Tag: {row.get('tag')}",
                f"Category: {row.get('category')}",
                f"Operators: {row.get('supported_operators')}",
            ]
        ),
        payload=lambda row: {"source_table": "streak_indicator_suggestions", "record_id": row["id"], **row},
    ),
    TableIndexConfig(
        collection="company_profiles",
        sql="""
            SELECT ticker, name, sector, industry, description, source
            FROM public.company_profiles
            ORDER BY ticker
        """,
        point_id=lambda row: stable_point_id(f"company_profiles:{row['ticker']}"),
        document=lambda row: _join_parts(
            [
                f"Ticker: {row.get('ticker')}",
                f"Name: {row.get('name')}",
                f"Sector: {row.get('sector')}",
                f"Industry: {row.get('industry')}",
                f"Description: {row.get('description')}",
            ]
        ),
        payload=lambda row: {"source_table": "company_profiles", "record_id": row["ticker"], **row},
    ),
    TableIndexConfig(
        collection="ohlcv",
        sql="""
            SELECT symbol,
                   resolution,
                   COUNT(*)::bigint AS bar_count,
                   MIN(time) AS start_time,
                   MAX(time) AS end_time,
                   ROUND(AVG(close)::numeric, 2) AS avg_close,
                   ROUND(MIN(close)::numeric, 2) AS min_close,
                   ROUND(MAX(close)::numeric, 2) AS max_close
            FROM public.ohlcv
            GROUP BY symbol, resolution
            ORDER BY symbol, resolution
        """,
        point_id=lambda row: stable_point_id(f"ohlcv:{row['symbol']}:{row['resolution']}"),
        document=lambda row: _join_parts(
            [
                f"Symbol: {row.get('symbol')}",
                f"Resolution: {row.get('resolution')}",
                f"Bars: {row.get('bar_count')}",
                f"Period: {row.get('start_time')} to {row.get('end_time')}",
                f"Close range: {row.get('min_close')} - {row.get('max_close')}",
                f"Average close: {row.get('avg_close')}",
            ]
        ),
        payload=lambda row: {
            "source_table": "ohlcv",
            "record_id": f"{row['symbol']}_{row['resolution']}",
            "symbol": row.get("symbol"),
            "resolution": row.get("resolution"),
            "bar_count": int(row.get("bar_count") or 0),
            "start_time": str(row.get("start_time")),
            "end_time": str(row.get("end_time")),
            "avg_close": float(row.get("avg_close") or 0),
        },
    ),
]


def _sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in payload.items():
        if value is None:
            continue
        if hasattr(value, "isoformat"):
            clean[key] = value.isoformat()
        elif isinstance(value, (dict, list)):
            clean[key] = json.loads(json.dumps(value, default=str))
        else:
            clean[key] = value
    return clean


def index_collection(
    client: QdrantClient,
    embedder: TextEmbedding,
    vector_size: int,
    config: TableIndexConfig,
) -> int:
    rows = _fetch_rows(config.sql)
    if not rows:
        print(f"  {config.collection}: no rows, skipping")
        return 0

    client.recreate_collection(
        collection_name=config.collection,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )

    documents = [config.document(row) for row in rows]
    all_points: list[PointStruct] = []

    for start in range(0, len(rows), BATCH_SIZE):
        batch_rows = rows[start : start + BATCH_SIZE]
        batch_docs = documents[start : start + BATCH_SIZE]
        vectors = list(embedder.embed(batch_docs))

        for row, vector, document in zip(batch_rows, vectors, batch_docs):
            payload = _sanitize_payload(config.payload(row))
            payload["document"] = document
            all_points.append(
                PointStruct(
                    id=config.point_id(row),
                    vector=vector.tolist(),
                    payload=payload,
                )
            )

    client.upsert(collection_name=config.collection, points=all_points)
    print(f"  {config.collection}: indexed {len(all_points)} vectors")
    return len(all_points)


def index_all_tables() -> dict[str, int]:
    embedder = TextEmbedding(model_name=EMBEDDING_MODEL)
    vector_size = len(list(embedder.embed(["dimension probe"]))[0])
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    print(f"Indexing {len(TABLE_CONFIGS)} collections into Qdrant ...")
    totals: dict[str, int] = {}
    for config in TABLE_CONFIGS:
        totals[config.collection] = index_collection(client, embedder, vector_size, config)

    print("\nSummary:")
    for collection, count in totals.items():
        print(f"  {collection}: {count}")
    print(f"  TOTAL: {sum(totals.values())}")
    return totals


if __name__ == "__main__":
    try:
        index_all_tables()
    except Exception as exc:
        print(f"Qdrant indexing failed: {exc}", file=sys.stderr)
        raise
