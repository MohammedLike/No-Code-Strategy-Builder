"""Pipeline: Qdrant search results provider (LLM components disabled)."""

from __future__ import annotations

from typing import Any
import logging

logger = logging.getLogger(__name__)


class StrategyPipeline:
    """Orchestrates search results with graceful degradation (LLM disabled)."""

    def __init__(
        self,
        llm_client: Any = None,
        model: str = "",
        min_llm_score: float = 0.5,
    ):
        pass

    def run(
        self,
        user_query: str,
        qdrant_results: list[dict[str, Any]] | None = None,
        *,
        force_llm: bool = False,
    ) -> dict[str, Any]:
        """Run the pipeline. Since LLM is disabled, it returns raw search results."""
        return {
            "status": "degraded",
            "message": "LLM module disabled in Phase 1 — returning raw search results",
            "results": qdrant_results or [],
        }

    def normalize(self, raw_text: str) -> dict[str, Any] | None:
        """Offline normalizer (disabled)."""
        logger.warning("LLM disabled, cannot normalize text")
        return None

    def batch_normalize(
        self, items: list[dict[str, str]], *, batch_size: int = 5
    ) -> list[dict[str, Any]]:
        """Batch normalizer (disabled)."""
        result: list[dict[str, Any]] = []
        for item in items:
            raw_text = item.get("text") or item.get("raw") or ""
            result.append({"status": "error", "message": "LLM disabled", "raw_preview": raw_text[:200]})
        return result

