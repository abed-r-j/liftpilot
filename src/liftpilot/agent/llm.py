"""Minimal client for a local Ollama server (no cloud, no API key, no cost)."""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_MODEL = os.environ.get("LIFTPILOT_MODEL", "qwen3:8b")
DEFAULT_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
if not DEFAULT_HOST.startswith("http"):
    DEFAULT_HOST = "http://" + DEFAULT_HOST


class LLMUnavailable(RuntimeError):
    pass


class OllamaClient:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        host: str = DEFAULT_HOST,
        seed: int = 7,
        temperature: float = 0.0,
        num_ctx: int = 8192,
        timeout: float = 180.0,
    ) -> None:
        self.model = model
        self.host = host.rstrip("/")
        self.options = {"seed": seed, "temperature": temperature, "num_ctx": num_ctx}
        self.timeout = timeout

    def available(self) -> bool:
        try:
            r = httpx.get(f"{self.host}/api/tags", timeout=3.0)
            r.raise_for_status()
            names = {m["name"] for m in r.json().get("models", [])}
            return self.model in names or f"{self.model}:latest" in names
        except (httpx.HTTPError, KeyError, ValueError):
            return False

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 900,
    ) -> dict[str, Any]:
        """One model turn. Returns the assistant message
        (``content`` and optionally ``tool_calls``)."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": False,
            "keep_alive": "30m",
            "options": {**self.options, "num_predict": max_tokens},
        }
        if tools:
            payload["tools"] = tools
        try:
            r = httpx.post(f"{self.host}/api/chat", json=payload, timeout=self.timeout)
            r.raise_for_status()
            return dict(r.json()["message"])
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise LLMUnavailable(f"local model call failed: {exc}") from exc

    def complete(self, system: str, user: str, max_tokens: int = 200) -> str:
        msg = self.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=max_tokens,
        )
        return str(msg.get("content", "")).strip()
