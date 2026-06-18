from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
REQUEST_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "120"))


class OllamaClient:
    """Lightweight HTTP wrapper around the Ollama generation API."""

    def __init__(
        self,
        host: str | None = None,
        model: str = DEFAULT_MODEL,
        timeout: int = REQUEST_TIMEOUT,
    ) -> None:
        self.base_url = (host or DEFAULT_OLLAMA_HOST).rstrip("/")
        self.model = model
        self.timeout = timeout
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def is_available(self) -> bool:
        """Check if Ollama server is reachable."""
        try:
            resp = self._client.get("/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        format: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "temperature": temperature,
            "options": {"num_predict": max_tokens},
        }
        if system:
            body["system"] = system
        if format:
            body["format"] = format

        resp = self._client.post("/api/generate", json=body)
        resp.raise_for_status()
        return resp.json()["response"]

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        format: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
            "options": {"num_predict": max_tokens},
        }
        if format:
            body["format"] = format

        resp = self._client.post("/api/chat", json=body)
        resp.raise_for_status()
        return resp.json()["message"]["content"]

    def extract_json(
        self,
        prompt: str | list[dict[str, str]],
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.05,
    ) -> dict[str, Any] | None:
        """Send a prompt (string or chat messages) and parse JSON from the response."""
        if model and model != self.model:
            body: dict[str, Any] = {
                "model": model,
                "stream": False,
                "temperature": temperature,
                "options": {"num_predict": 2048},
                "format": "json",
            }
            if isinstance(prompt, list):
                body["messages"] = prompt
            else:
                body["prompt"] = prompt
                if system:
                    body["system"] = system
            resp = self._client.post("/api/generate", json=body)
        elif isinstance(prompt, list):
            raw = self.chat(prompt, format="json", temperature=temperature)
            return self._parse_json(raw)
        else:
            raw = self.generate(prompt, system=system, format="json", temperature=temperature)
            return self._parse_json(raw)

        resp.raise_for_status()
        return self._parse_json(resp.json()["response"])

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any] | None:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0]
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM JSON: %.200s", raw)
            return None

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> OllamaClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
