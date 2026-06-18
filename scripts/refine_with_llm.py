"""
CLI entrypoint for the search -> LLM -> DSL pipeline.

Usage:
    # Normalize raw strategy text offline
    python scripts/refine_with_llm.py normalize "Buy Nifty when RSI(14) below 30, exit above 70, SL 2%, TP 5%"

    # Search Qdrant + refine with LLM
    python scripts/refine_with_llm.py search "RSI oversold mean reversion on Bank Nifty"

    # Batch normalize from a JSON file
    python scripts/refine_with_llm.py batch --file raw_strategies.json

    # Check if Ollama is running
    python scripts/refine_with_llm.py status
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))           # scripts/
sys.path.insert(0, str(ROOT.parent))     # project root (for backend/)

from search_qdrant import search

from backend.llm.client import OllamaClient
from backend.pipeline import StrategyPipeline


def cmd_status(client: OllamaClient) -> None:
    ok = client.is_available()
    print(f"Ollama ({client.host}): {'RUNNING' if ok else 'NOT REACHABLE'}")
    print(f"Default model: {client.model}")
    sys.exit(0 if ok else 1)


def cmd_normalize(client: OllamaClient, raw_text: str) -> None:
    pipeline = StrategyPipeline(llm_client=client)
    result = pipeline.normalize(raw_text)
    if result:
        print(json.dumps(result, indent=2, default=str))
    else:
        print("Failed to normalize strategy", file=sys.stderr)
        sys.exit(1)


def cmd_search(client: OllamaClient, query: str) -> None:
    pipeline = StrategyPipeline(llm_client=client)
    print(f"Searching Qdrant for: {query}")
    hits = search(query, limit=5)
    if not hits:
        print("No results found in Qdrant, trying LLM from scratch ...")
        result = pipeline.run(query)
    else:
        print(f"Found {len(hits)} results (top score: {hits[0]['score']:.3f})")
        result = pipeline.run(query, qdrant_results=hits)

    print(json.dumps(result, indent=2, default=str))


def cmd_batch(client: OllamaClient, file_path: str) -> None:
    with open(file_path, encoding="utf-8") as f:
        items = json.load(f)
    pipeline = StrategyPipeline(llm_client=client)
    results = pipeline.batch_normalize(items)
    print(json.dumps(results, indent=2, default=str))
    ok = sum(1 for r in results if r.get("status") != "error")
    print(f"\nBatch done: {ok}/{len(results)} succeeded")


def main() -> None:
    client = OllamaClient()

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "status":
        cmd_status(client)
    elif command == "normalize":
        if len(sys.argv) < 3:
            print("Usage: python scripts/refine_with_llm.py normalize <raw_text>")
            sys.exit(1)
        cmd_normalize(client, " ".join(sys.argv[2:]))
    elif command == "search":
        if len(sys.argv) < 3:
            print("Usage: python scripts/refine_with_llm.py search <query>")
            sys.exit(1)
        cmd_search(client, " ".join(sys.argv[2:]))
    elif command == "batch":
        if not any(a.startswith("--file=") for a in sys.argv[2:]):
            print("Usage: python scripts/refine_with_llm.py batch --file=<path>")
            sys.exit(1)
        file_arg = next(a for a in sys.argv[2:] if a.startswith("--file="))
        file_path = file_arg.split("=", 1)[1]
        cmd_batch(client, file_path)
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
