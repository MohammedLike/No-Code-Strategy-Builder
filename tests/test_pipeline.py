"""Tests for the search -> LLM -> validation pipeline."""

from __future__ import annotations

from backend.pipeline import StrategyPipeline
from backend.llm.client import OllamaClient
from backend.llm.prompts import (
    build_normalize_prompt,
    build_refine_prompt,
    format_qdrant_results,
)


def test_pipeline_degraded_when_llm_offline() -> None:
    """Pipeline should degrade gracefully when Ollama is unreachable."""
    client = OllamaClient(host="http://localhost:1", model="test")
    pipeline = StrategyPipeline(llm_client=client)
    result = pipeline.run("test query")
    assert result["status"] == "degraded"
    assert "LLM unavailable" in result["message"]


def test_normalize_prompt_contains_input() -> None:
    prompt = build_normalize_prompt("RSI below 30")
    assert "RSI below 30" in prompt


def test_refine_prompt_contains_query_and_strategies() -> None:
    results = [
        {
            "score": 0.95,
            "payload": {
                "name": "RSI Mean Rev",
                "category": "Mean Reversion",
                "document": "Buy when RSI < 30",
            },
        }
    ]
    prompt = build_refine_prompt("test query", results)
    assert "test query" in prompt
    assert "RSI Mean Rev" in prompt


def test_format_qdrant_results() -> None:
    results = [
        {"score": 0.9, "payload": {"name": "Strat A", "category": "EQ"}},
        {"score": 0.8, "payload": {"name": "Strat B"}},
    ]
    formatted = format_qdrant_results(results)
    assert "Strat A" in formatted
    assert "Strat B" in formatted
    assert "0.900" in formatted


def test_pipeline_normalize_offline_returns_none() -> None:
    client = OllamaClient(host="http://localhost:1", model="test")
    pipeline = StrategyPipeline(llm_client=client)
    result = pipeline.normalize("RSI below 30")
    assert result is None  # No LLM available


def test_batch_normalize_no_llm() -> None:
    client = OllamaClient(host="http://localhost:1", model="test")
    pipeline = StrategyPipeline(llm_client=client)
    items = [{"name": "Test", "text": "RSI < 30"}]
    results = pipeline.batch_normalize(items)
    assert len(results) == 1
    assert results[0]["status"] == "error"
