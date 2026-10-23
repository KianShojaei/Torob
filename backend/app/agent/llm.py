"""Provider-agnostic LLM client with tool calling (master prompt §2, §7).

* ``none``      → no network at all; the orchestrator uses the deterministic planner
* ``anthropic`` → Messages API with tool use
* ``openai``    → any OpenAI-compatible gateway (Iranian providers included)

The client never sees raw SQL or the database; it only receives tool results.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from app.config import settings

log = logging.getLogger("llm")


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResult:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"
    usage: dict = field(default_factory=dict)


class LLMClient(Protocol):
    async def chat(self, system: str, messages: list[dict],
                   tools: list[dict] | None = None) -> LLMResult: ...


class NullClient:
    """Used when LLM_PROVIDER=none — the agent falls back to the rule planner."""

    name = "none"

    async def chat(self, system, messages, tools=None) -> LLMResult:
        return LLMResult(text="", stop_reason="degraded")


class AnthropicClient:
    name = "anthropic"

    def __init__(self, api_key: str, model: str, base_url: str = "",
                 timeout: float = 30.0) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = (base_url or "https://api.anthropic.com").rstrip("/")
        self.timeout = timeout

    async def chat(self, system, messages, tools=None) -> LLMResult:
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 1024,
            "system": system,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/v1/messages",
                                     headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        text_parts, calls = [], []
        for block in data.get("content", []):
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                calls.append(ToolCall(id=block["id"], name=block["name"],
                                      arguments=block.get("input") or {}))
        return LLMResult(text="".join(text_parts), tool_calls=calls,
                         stop_reason=data.get("stop_reason", "end_turn"),
                         usage=data.get("usage", {}))


class OpenAICompatClient:
    name = "openai"

    def __init__(self, api_key: str, model: str, base_url: str,
                 timeout: float = 30.0) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.timeout = timeout

    async def chat(self, system, messages, tools=None) -> LLMResult:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "temperature": 0.2,
        }
        if tools:
            payload["tools"] = [{"type": "function", "function": t} for t in tools]
            payload["tool_choice"] = "auto"
        headers = {"Authorization": f"Bearer {self.api_key}",
                   "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/chat/completions",
                                     headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        calls = []
        for tc in msg.get("tool_calls") or []:
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            calls.append(ToolCall(id=tc.get("id", ""),
                                  name=tc["function"]["name"], arguments=args))
        return LLMResult(text=msg.get("content") or "", tool_calls=calls,
                         stop_reason=choice.get("finish_reason", "stop"),
                         usage=data.get("usage", {}))


def get_client() -> LLMClient:
    provider = (settings.llm_provider or "none").lower()
    key = settings.llm_api_key
    if provider == "anthropic" and key:
        return AnthropicClient(key, settings.llm_model, settings.llm_base_url,
                               settings.llm_timeout_seconds)
    if provider == "openai" and key:
        return OpenAICompatClient(key, settings.llm_model, settings.llm_base_url,
                                  settings.llm_timeout_seconds)
    return NullClient()
