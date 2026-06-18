"""Bridge between LLM output and the existing Strategy DSL normalizer."""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.app.strategy.models import StrategySpec
from backend.app.strategy.normalizer import normalize_strategy_record

from .client import OllamaClient
from .prompts import NORMALIZE_SYSTEM, build_normalize_prompt

logger = logging.getLogger(__name__)


class LLMNormalizer:
    """Use a local LLM (via Ollama) to normalize raw strategy text into StrategySpec."""

    def __init__(self, client: OllamaClient | None = None) -> None:
        self._client = client or OllamaClient()

    def normalize_text(self, raw_text: str) -> StrategySpec:
        prompt = build_normalize_prompt(raw_text)
        result = self._client.extract_json(prompt, system=NORMALIZE_SYSTEM)
        if result is None:
            raise ValueError("LLM returned unparseable JSON")
        return self._to_spec(result)

    def normalize_dict(self, raw: dict[str, Any]) -> StrategySpec:
        raw_text = json.dumps(raw, indent=2)
        return self.normalize_text(raw_text)

    def normalize_with_fallback(self, record: dict[str, Any]) -> StrategySpec:
        try:
            return self.normalize_dict(record)
        except Exception as exc:
            logger.warning("LLM normalization failed, falling back to rule-based: %s", exc)
            return normalize_strategy_record(record)

    def _to_spec(self, data: dict[str, Any]) -> StrategySpec:
        return StrategySpec.model_validate(data)

    def close(self) -> None:
        self._client.close()
