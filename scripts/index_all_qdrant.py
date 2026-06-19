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
            f"Indicator: {row.get('indicator')}" if row.get("indicator") else None,
            f"Entry rules: {json.dumps(row.get('entry_rules'), ensure_ascii=False)}" if row.get("entry_rules") else None,
            f"Exit rules: {json.dumps(row.get('exit_rules'), ensure_ascii=False)}" if row.get("exit_rules") else None,
            f"Risk params: {json.dumps(row.get('risk_params'), ensure_ascii=False)}" if row.get("risk_params") else None,
        ]
    )

def _independent_strategy_document(row: dict[str, Any]) -> str:
    return _join_parts(
        [
            f"Name: {row.get('name')}",
            f"Slug: {row.get('slug')}",
            f"Category: {row.get('category')}",
            f"Hypothesis: {row.get('hypothesis')}",
            f"Indicator: {row.get('indicator')}" if row.get("indicator") else None,
            f"Entry rules: {json.dumps(row.get('entry_rules'), ensure_ascii=False)}" if row.get("entry_rules") else None,
            f"Exit rules: {json.dumps(row.get('exit_rules'), ensure_ascii=False)}" if row.get("exit_rules") else None,
            f"Risk params: {json.dumps(row.get('risk_params'), ensure_ascii=False)}" if row.get("risk_params") else None,
        ]
    )


def _pine_script_document(row: dict[str, Any]) -> str:
    return _join_parts(
        [
            f"Name: {row.get('name')}",
            f"Slug: {row.get('slug')}",
            f"Symbol: {row.get('symbol')}",
            f"Period: {row.get('period')}",
            f"Resolution: {row.get('resolution')}",
            f"Prompt: {row.get('prompt')}",
            f"Pine Script Source: {row.get('pine_script')}",
        ]
    )


def _pine_indicator_document(row: dict[str, Any]) -> str:
    return _join_parts(
        [
            f"Name: {row.get('display_name')} ({row.get('pine_name')})",
            f"Category: {row.get('category')}",
            f"Description: {row.get('description')}",
            f"Example Usage: {row.get('example_usage')}",
            f"Returns Type: {row.get('returns_type')}",
        ]
    )


TABLE_CONFIGS: list[TableIndexConfig] = [
    TableIndexConfig(
        collection="strategies",
        sql="""
            SELECT id::text AS id, name, slug, category, hypothesis, indicator,
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
            "indicator": row.get("indicator"),
        },
    ),
    TableIndexConfig(
        collection="independent_strategies",
        sql="""
            SELECT id::text AS id, name, slug, category, hypothesis, indicator,
                   entry_rules, exit_rules, risk_params, strategy_metadata, created_at
            FROM public.independent_strategies
            ORDER BY created_at
        """,
        point_id=lambda row: str(row["id"]),
        document=_independent_strategy_document,
        payload=lambda row: {
            "source_table": "independent_strategies",
            "record_id": str(row["id"]),
            "name": row.get("name"),
            "slug": row.get("slug"),
            "category": row.get("category"),
            "hypothesis": row.get("hypothesis"),
            "indicator": row.get("indicator"),
        },
    ),
    TableIndexConfig(
        collection="pine_scripts",
        sql="""
            SELECT id::text AS id, name, slug, symbol, period, resolution, prompt, pine_script, created_at
            FROM public.pine_scripts
            ORDER BY created_at
        """,
        point_id=lambda row: str(row["id"]),
        document=_pine_script_document,
        payload=lambda row: {
            "source_table": "pine_scripts",
            "record_id": str(row["id"]),
            "name": row.get("name"),
            "slug": row.get("slug"),
            "symbol": row.get("symbol"),
            "period": row.get("period"),
            "resolution": row.get("resolution"),
            "prompt": row.get("prompt"),
        },
    ),
    TableIndexConfig(
        collection="pine_indicators",
        sql="""
            SELECT id::text AS id, pine_name, display_name, category, description, example_usage, returns_type, created_at
            FROM public.pine_indicators
            ORDER BY created_at
        """,
        point_id=lambda row: str(row["id"]),
        document=_pine_indicator_document,
        payload=lambda row: {
            "source_table": "pine_indicators",
            "record_id": str(row["id"]),
            "pine_name": row.get("pine_name"),
            "display_name": row.get("display_name"),
            "category": row.get("category"),
            "description": row.get("description"),
            "returns_type": row.get("returns_type"),
        },
    ),
    TableIndexConfig(
        collection="streak_indicator_suggestions",
        sql="""
            SELECT id, sheet_name, indicator, bias, suggestion, tag, category, supported_operators
            FROM public.streak_indicator_suggestions
            ORDER BY id
        """,
        point_id=lambda row: int(row["id"]),
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
        payload=lambda row: {
            "source_table": "streak_indicator_suggestions",
            "record_id": str(row["id"]),
            "sheet_name": row.get("sheet_name"),
            "indicator": row.get("indicator"),
            "bias": row.get("bias"),
            "suggestion": row.get("suggestion"),
            "tag": row.get("tag"),
            "category": row.get("category"),
            "supported_operators": row.get("supported_operators"),
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
