"""Thin, hand-written LLM adapter supporting Anthropic Claude SDK plus free-tier Groq / Gemini.

No agent frameworks (no LangChain). Translates a single clean internal message + tool
format to either Anthropic Messages API or OpenAI-compatible Chat Completions (Groq/Gemini).
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass
class ToolCallRequest:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    text: str = ""
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    stop_reason: str = "end_turn"
    provider: str = ""
    model: str = ""


class LLMClient:
    """Unified async LLM client switched entirely through config (`LLM_PROVIDER`, `LLM_MODEL`)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    def provider(self) -> str:
        return self.settings.llm_provider.strip().lower()

    def is_configured(self) -> bool:
        if self.provider == "anthropic":
            return bool(self.settings.anthropic_api_key.strip())
        if self.provider == "groq":
            return bool(self.settings.groq_api_key.strip())
        if self.provider == "gemini":
            return bool(self.settings.gemini_api_key.strip())
        return False

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 1200,
        temperature: float = 0.3,
        json_mode: bool = False,
    ) -> LLMResponse:
        chosen_model = model or self.settings.active_llm_model
        if self.provider == "anthropic":
            return await self._call_anthropic(
                system=system,
                messages=messages,
                tools=tools,
                model=chosen_model,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        if self.provider in ("groq", "gemini"):
            return await self._call_openai_compat(
                provider=self.provider,
                system=system,
                messages=messages,
                tools=tools,
                model=chosen_model,
                max_tokens=max_tokens,
                temperature=temperature,
                json_mode=json_mode,
            )
        raise ValueError(f"Unsupported LLM_PROVIDER: {self.provider}")

    async def _call_anthropic(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=self.settings.anthropic_api_key)
        anthropic_messages = _to_anthropic_messages(messages)
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": anthropic_messages,
        }
        if tools:
            kwargs["tools"] = [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "input_schema": t["input_schema"],
                }
                for t in tools
            ]

        resp = await client.messages.create(**kwargs)
        text_parts: list[str] = []
        tool_calls: list[ToolCallRequest] = []
        for block in resp.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                text_parts.append(block.text)
            elif btype == "tool_use":
                tool_calls.append(
                    ToolCallRequest(
                        id=block.id,
                        name=block.name,
                        arguments=dict(block.input or {}),
                    )
                )

        return LLMResponse(
            text="\n".join(text_parts).strip(),
            tool_calls=tool_calls,
            stop_reason=resp.stop_reason or "end_turn",
            provider="anthropic",
            model=model,
        )

    async def _call_openai_compat(
        self,
        *,
        provider: str,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        model: str,
        max_tokens: int,
        temperature: float,
        json_mode: bool,
    ) -> LLMResponse:
        if provider == "groq":
            endpoint = "https://api.groq.com/openai/v1/chat/completions"
            api_key = self.settings.groq_api_key
        else:
            endpoint = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
            api_key = self.settings.gemini_api_key

        # Reasoning models (e.g. openai/gpt-oss-*) share max_tokens with internal CoT
        effective_max_tokens = max_tokens
        if any(tok in model.lower() for tok in ("gpt-oss", "qwen3", "r1")):
            effective_max_tokens = max(max_tokens, 1024)

        oa_messages = [{"role": "system", "content": system}] + _to_openai_messages(messages)
        payload: dict[str, Any] = {
            "model": model,
            "messages": oa_messages,
            "max_tokens": effective_max_tokens,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["input_schema"],
                    },
                }
                for t in tools
            ]
            payload["tool_choice"] = "auto"
        elif json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(45.0)) as client:
            resp = await client.post(endpoint, headers=headers, json=payload)
            if resp.status_code == 400 and json_mode and "json_validate_failed" in resp.text:
                # Fallback gracefully if provider-side JSON grammar rejected reasoning tokens
                logger.warning("Retrying %s call without strict response_format", provider)
                payload.pop("response_format", None)
                resp = await client.post(endpoint, headers=headers, json=payload)
            if resp.status_code >= 400:
                logger.error("LLM %s HTTP %s: %s", provider, resp.status_code, resp.text[:400])
                resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        msg = choice["message"]
        text = (msg.get("content") or "").strip()
        tool_calls: list[ToolCallRequest] = []

        for raw_tc in msg.get("tool_calls") or []:
            fn = raw_tc.get("function", {})
            raw_args = fn.get("arguments", "{}")
            try:
                parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
            except json.JSONDecodeError:
                parsed_args = {"_raw_malformed": raw_args}
            tool_calls.append(
                ToolCallRequest(
                    id=raw_tc.get("id") or f"call_{len(tool_calls)}",
                    name=fn.get("name", ""),
                    arguments=parsed_args if isinstance(parsed_args, dict) else {},
                )
            )

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            stop_reason=choice.get("finish_reason") or "stop",
            provider=provider,
            model=model,
        )


def _to_anthropic_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert internal neutral message list into Anthropic Messages API blocks."""
    out: list[dict[str, Any]] = []
    for msg in messages:
        role = msg["role"]
        if role == "user":
            out.append({"role": "user", "content": msg["content"]})
        elif role == "assistant":
            blocks: list[dict[str, Any]] = []
            if msg.get("content"):
                blocks.append({"type": "text", "text": msg["content"]})
            for tc in msg.get("tool_calls") or []:
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["name"],
                        "input": tc["arguments"],
                    }
                )
            out.append({"role": "assistant", "content": blocks or [{"type": "text", "text": ""}]})
        elif role == "tool":
            tool_block = {
                "type": "tool_result",
                "tool_use_id": msg["tool_call_id"],
                "content": msg["content"],
                "is_error": bool(msg.get("is_error", False)),
            }
            if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                out[-1]["content"].append(tool_block)
            else:
                out.append({"role": "user", "content": [tool_block]})
    return out


def _to_openai_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert internal neutral message list into OpenAI/Groq/Gemini chat messages."""
    out: list[dict[str, Any]] = []
    for msg in messages:
        role = msg["role"]
        if role == "user":
            out.append({"role": "user", "content": msg["content"]})
        elif role == "assistant":
            entry: dict[str, Any] = {"role": "assistant", "content": msg.get("content") or ""}
            if msg.get("tool_calls"):
                entry["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"]),
                        },
                    }
                    for tc in msg["tool_calls"]
                ]
            out.append(entry)
        elif role == "tool":
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": msg["tool_call_id"],
                    "name": msg.get("name", "tool"),
                    "content": msg["content"],
                }
            )
    return out
