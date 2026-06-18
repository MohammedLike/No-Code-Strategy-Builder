"""Pipeline: Qdrant search -> LLM refinement -> DSL validation."""

from __future__ import annotations

import logging
from typing import Any

from .llm.client import DEFAULT_MODEL, OllamaClient
from .llm.prompts import (
    NORMALIZE_SYSTEM,
    REFINE_SYSTEM,
    build_normalize_prompt,
    build_refine_prompt,
)
from .strategy.compiler import compile_strategy
from .strategy.models import StrategySpec

logger = logging.getLogger(__name__)


class StrategyPipeline:
    """Orchestrates search -> LLM -> DSL validation with graceful fallback.

    Usage:
        pipeline = StrategyPipeline()
        result = pipeline.run("RSI mean reversion on Nifty with 2% SL")
        # or pass pre-fetched Qdrant results:
        result = pipeline.run(user_query, qdrant_results=hits)
    """

    def __init__(
        self,
        llm_client: OllamaClient | None = None,
        model: str = DEFAULT_MODEL,
        min_llm_score: float = 0.5,
    ):
        self.llm = llm_client or OllamaClient(model=model)
        self.model = model
        self.min_llm_score = min_llm_score

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        user_query: str,
        qdrant_results: list[dict[str, Any]] | None = None,
        *,
        force_llm: bool = False,
    ) -> dict[str, Any]:
        """Run the full pipeline.

        Args:
            user_query: Natural language strategy request.
            qdrant_results: Optional pre-fetched Qdrant hits.
            force_llm: Always use LLM even with high-scoring results.

        Returns:
            Dict with keys: status, strategy (if ok), or message, results.
        """
        if not self.llm.is_available():
            return {
                "status": "degraded",
                "message": "LLM unavailable — returning raw search results",
                "results": qdrant_results or [],
            }

        similar = qdrant_results or []

        if not similar:
            return self._generate_from_scratch(user_query)

        top_score = similar[0].get("score", 0)

        if top_score >= self.min_llm_score and not force_llm:
            result = self._try_direct_normalization(similar[0])
            if result:
                adapted = self._try_adaptation(result, user_query, similar)
                if adapted:
                    return {"status": "ok", "source": "adapted", "strategy": adapted}
                return {"status": "ok", "source": "direct", "strategy": result}

        adapted = self._synthesize(user_query, similar)
        if adapted:
            return {"status": "ok", "source": "synthesized", "strategy": adapted}

        return {"status": "error", "message": "LLM produced invalid strategy"}

    def normalize(self, raw_text: str) -> dict[str, Any] | None:
        """Offline: normalize a single raw strategy text -> compiled spec."""
        if not self.llm.is_available():
            logger.warning("LLM unavailable, cannot normalize")
            return None
        raw = self.llm.extract_json(
            build_normalize_prompt(raw_text),
            model=self.model,
            system=NORMALIZE_SYSTEM,
        )
        if raw:
            return self._validate(raw)
        return None

    def batch_normalize(
        self, items: list[dict[str, str]], *, batch_size: int = 5
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for item in items:
            raw_text = item.get("text") or item.get("raw") or ""
            name_hint = item.get("name", "")
            if name_hint and raw_text:
                raw_text = f"Name: {name_hint}\n{raw_text}"
            compiled = self.normalize(raw_text)
            if compiled:
                result.append(compiled)
            else:
                result.append({"status": "error", "raw_preview": raw_text[:200]})
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate(self, data: dict[str, Any]) -> dict[str, Any] | None:
        try:
            spec = StrategySpec.model_validate(data)
            compiled = compile_strategy(spec)
            if compiled.validation.valid:
                return compiled.to_dict()
            logger.warning("Validation errors: %s", compiled.validation.errors)
            return None
        except Exception as exc:
            logger.error("Validation failed: %s", exc)
            return None

    def _generate_from_scratch(self, query: str) -> dict[str, Any]:
        raw = self.llm.extract_json(
            build_normalize_prompt(query),
            model=self.model,
            system=NORMALIZE_SYSTEM,
        )
        if raw:
            compiled = self._validate(raw)
            if compiled:
                return {"status": "ok", "source": "generated", "strategy": compiled}
        return {"status": "error", "message": "Could not generate strategy from query"}

    def _try_direct_normalization(
        self, top_result: dict[str, Any]
    ) -> dict[str, Any] | None:
        doc = top_result.get("payload", {}).get("document", "")
        if not doc:
            return None
        raw = self.llm.extract_json(
            build_normalize_prompt(doc),
            model=self.model,
            system=NORMALIZE_SYSTEM,
            temperature=0.05,
        )
        return self._validate(raw) if raw else None

    def _try_adaptation(
        self,
        base: dict[str, Any],
        query: str,
        similar: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        prompt = build_refine_prompt(query, similar)
        raw = self.llm.extract_json(
            prompt, model=self.model, system=REFINE_SYSTEM
        )
        return self._validate(raw) if raw else None

    def _synthesize(
        self, query: str, similar: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        prompt = build_refine_prompt(query, similar)
        raw = self.llm.extract_json(
            prompt, model=self.model, system=REFINE_SYSTEM, temperature=0.3
        )
        return self._validate(raw) if raw else None
