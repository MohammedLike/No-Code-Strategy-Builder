"""Semantic search across all Qdrant collections."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastembed import TextEmbedding
from qdrant_client import QdrantClient

from common import EMBEDDING_MODEL, QDRANT_HOST, QDRANT_PORT
from index_all_qdrant import TABLE_CONFIGS

ALL_COLLECTIONS = [config.collection for config in TABLE_CONFIGS]


def search(
    query: str,
    *,
    collections: list[str] | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    embedder = TextEmbedding(model_name=EMBEDDING_MODEL)
    vector = list(embedder.embed([query]))[0].tolist()

    targets = collections or ALL_COLLECTIONS
    hits: list[dict[str, Any]] = []

    for collection in targets:
        try:
            results = client.query_points(
                collection_name=collection,
                query=vector,
                limit=limit,
            ).points
        except Exception:
            continue
        for item in results:
            hits.append(
                {
                    "collection": collection,
                    "score": item.score,
                    "payload": item.payload,
                }
            )

    hits.sort(key=lambda item: item["score"], reverse=True)
    return hits[:limit]


if __name__ == "__main__":
    import json

    prompt = " ".join(sys.argv[1:]) or "RSI oversold mean reversion on Nifty"
    print(json.dumps(search(prompt), indent=2, default=str))
