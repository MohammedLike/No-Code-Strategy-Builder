from __future__ import annotations

import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DATABASE_URL = os.environ["DATABASE_URL"]
QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "strategies")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

logger = logging.getLogger(__name__)


class PipelineRequest(BaseModel):
    query: str


class SearchRequest(BaseModel):
    query: str
    limit: int = 5


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="AI Strategy Builder API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# /api/health
# ---------------------------------------------------------------------------


@app.get("/api/health")
def health():
    pg_ok = False
    qd_ok = False
    llm_ok = False

    try:
        with psycopg2.connect(DATABASE_URL, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                pg_ok = True
    except Exception as exc:
        logger.warning("PostgreSQL health check failed: %s", exc)

    try:
        from qdrant_client import QdrantClient

        QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=3).get_collections()
        qd_ok = True
    except Exception as exc:
        logger.warning("Qdrant health check failed: %s", exc)

    try:
        from backend.llm import OllamaClient

        llm_ok = OllamaClient().is_available()
    except Exception as exc:
        logger.warning("LLM health check failed: %s", exc)

    status = "ok" if pg_ok else "degraded"
    return {
        "status": status,
        "checks": {
            "postgresql": pg_ok,
            "qdrant": qd_ok,
            "llm_ollama": llm_ok,
        },
    }


# ---------------------------------------------------------------------------
# /api/strategies
# ---------------------------------------------------------------------------


@app.get("/api/strategies")
def list_strategies(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, name, slug, category, hypothesis, created_at "
                "FROM public.strategies ORDER BY created_at DESC LIMIT %s OFFSET %s",
                (limit, offset),
            )
            rows = cur.fetchall()
            cur.execute("SELECT COUNT(*) AS total FROM public.strategies")
            total = cur.fetchone()["total"]
    return {"total": total, "limit": limit, "offset": offset, "data": rows}


@app.get("/api/strategies/{strategy_id}")
def get_strategy(strategy_id: str):
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM public.strategies WHERE id = %s::uuid OR slug = %s",
                (strategy_id, strategy_id),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"data": row}


@app.get("/api/strategies/table/{table_name}")
def list_raw_strategies(table_name: str, limit: int = Query(50, ge=1, le=500)):
    allowed = {
        "algo_bull_strategies",
        "finstock_strategies",
        "live_backtesting",
        "live_scanners",
        "streak_trading_strategies",
        "streak_indicator_suggestions",
    }
    if table_name not in allowed:
        raise HTTPException(status_code=400, detail=f"Unknown table: {table_name}")

    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT * FROM public.{table_name} ORDER BY id DESC LIMIT %s",
                (limit,),
            )
            rows = cur.fetchall()
    return {"table": table_name, "count": len(rows), "data": rows}


@app.get("/api/db/tables")
def list_db_tables():
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT schemaname, tablename, tableowner "
                "FROM pg_catalog.pg_tables "
                "WHERE schemaname = 'public' "
                "ORDER BY tablename"
            )
            rows = cur.fetchall()
    return {"data": rows}


@app.get("/api/db/stats")
def db_stats():
    queries = {
        "strategies": "SELECT COUNT(*) AS c FROM public.strategies",
        "algo_bull_strategies": "SELECT COUNT(*) AS c FROM public.algo_bull_strategies",
        "finstock_strategies": "SELECT COUNT(*) AS c FROM public.finstock_strategies",
        "live_backtesting": "SELECT COUNT(*) AS c FROM public.live_backtesting",
        "live_scanners": "SELECT COUNT(*) AS c FROM public.live_scanners",
        "streak_trading_strategies": "SELECT COUNT(*) AS c FROM public.streak_trading_strategies",
        "streak_indicator_suggestions": "SELECT COUNT(*) AS c FROM public.streak_indicator_suggestions",
        "company_profiles": "SELECT COUNT(*) AS c FROM public.company_profiles",
    }
    stats = {}
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            for name, sql in queries.items():
                try:
                    cur.execute(sql)
                    stats[name] = cur.fetchone()[0]
                except Exception as exc:
                    stats[name] = str(exc)
    return {"data": stats}


# ---------------------------------------------------------------------------
# /api/search  (Qdrant semantic search)
# ---------------------------------------------------------------------------


@app.post("/api/search")
def search_qdrant(body: SearchRequest):
    try:
        from qdrant_client import QdrantClient
        from fastembed import TextEmbedding

        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        embedder = TextEmbedding(model_name=EMBEDDING_MODEL)
        vector = list(embedder.embed([body.query]))[0].tolist()

        from scripts.index_all_qdrant import TABLE_CONFIGS

        all_collections = [c.collection for c in TABLE_CONFIGS]
        hits: list[dict[str, Any]] = []

        for collection in all_collections:
            try:
                results = client.query_points(
                    collection_name=collection,
                    query=vector,
                    limit=body.limit,
                ).points
            except Exception:
                continue
            for item in results:
                hits.append({
                    "collection": collection,
                    "score": round(item.score, 4),
                    "payload": item.payload,
                })

        hits.sort(key=lambda x: x["score"], reverse=True)
        return {"query": body.query, "total": len(hits), "results": hits[: body.limit]}
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=f"Search dependencies not installed: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Search failed: {exc}")


# ---------------------------------------------------------------------------
# /api/pipeline/run
# ---------------------------------------------------------------------------


@app.post("/api/pipeline/run")
def run_pipeline(body: PipelineRequest):
    try:
        from backend.pipeline import StrategyPipeline
    except ImportError:
        raise HTTPException(status_code=503, detail="Pipeline module not available")

    pipeline = StrategyPipeline()
    result = pipeline.run(body.query)
    return {"query": body.query, "result": result}


@app.post("/api/pipeline/run-with-search")
def run_pipeline_with_search(body: PipelineRequest):
    try:
        from backend.pipeline import StrategyPipeline
        from qdrant_client import QdrantClient
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=f"Dependency not available: {exc}")

    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    embedder = TextEmbedding(model_name=EMBEDDING_MODEL)
    vector = list(embedder.embed([body.query]))[0].tolist()

    from scripts.index_all_qdrant import TABLE_CONFIGS

    all_collections = [c.collection for c in TABLE_CONFIGS]
    hits: list[dict[str, Any]] = []

    for collection in all_collections:
        try:
            results = client.query_points(
                collection_name=collection,
                query=vector,
                limit=5,
            ).points
        except Exception:
            continue
        for item in results:
            hits.append({
                "collection": collection,
                "score": item.score,
                "payload": item.payload,
            })

    hits.sort(key=lambda x: x["score"], reverse=True)
    top_hits = hits[:5]

    pipeline = StrategyPipeline()
    result = pipeline.run(body.query, qdrant_results=top_hits)
    return {"query": body.query, "qdrant_hits": len(top_hits), "result": result}


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
