"""
OpenAI-compatible LLM client for planner.
Uses openai SDK with tenacity retry.
Supports tools (function calling) for Agent mode.
"""

import asyncio
from typing import Any, Callable, List, Optional, Union

from openai import AsyncOpenAI
from openai import APIConnectionError, APITimeoutError, RateLimitError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o"


def merge_phase_config(api_config: dict, phase: str) -> dict:
    """
    Merge global api_config with phase-specific overrides.
    phase: atomicity | decompose | format | execute | validate
    Returns dict with baseUrl, apiKey, model (camelCase for compatibility).
    """
    cfg = dict(api_config or {})
    phases = cfg.get("phases") or {}
    phase_cfg = phases.get(phase) or {}
    if isinstance(phase_cfg, dict):
        base = {
            "baseUrl": cfg.get("baseUrl") or cfg.get("base_url"),
            "apiKey": cfg.get("apiKey") or cfg.get("api_key"),
            "model": cfg.get("model"),
        }
        for k, v in phase_cfg.items():
            key = k if k in ("baseUrl", "apiKey", "model") else {"base_url": "baseUrl", "api_key": "apiKey"}.get(k, k)
            if v is not None and v != "":
                base[key] = v
        if not base.get("model"):
            base["model"] = DEFAULT_MODEL
        return base
    return cfg


def _create_client(api_config: dict) -> AsyncOpenAI:
    base_url = (api_config.get("baseUrl") or DEFAULT_BASE_URL).rstrip("/")
    api_key = api_config.get("apiKey") or "not-needed"
    return AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=120.0)


def _message_to_result(message, finish_reason: str) -> Union[str, dict]:
    """Convert API message to result. Returns dict with tool_calls when finish_reason is tool_calls."""
    if finish_reason == "tool_calls" and message.tool_calls:
        tool_calls = [
            {
                "id": tc.id,
                "type": getattr(tc, "type", "function"),
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments or "",
                },
            }
            for tc in message.tool_calls
        ]
        return {
            "content": message.content or "",
            "tool_calls": tool_calls,
            "finish_reason": "tool_calls",
        }
    return message.content or ""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((APIConnectionError, APITimeoutError, RateLimitError)),
)
async def _chat_completion_impl(
    client: AsyncOpenAI,
    model: str,
    messages: list[dict],
    on_chunk: Optional[Callable[[str], None]],
    abort_event: Optional[Any],
    stream: bool,
    temperature: Optional[float] = None,
    response_format: Optional[dict] = None,
    tools: Optional[List[dict]] = None,
) -> Union[str, dict]:
    """Inner implementation with retry.
    When tools is provided: uses stream=False, no response_format; may return dict with tool_calls.
    """
    extra = {"temperature": temperature} if temperature is not None else {}
    if response_format:
        extra["response_format"] = response_format
    if tools:
        extra["tools"] = tools
        # Agent mode: tools incompatible with response_format; streaming with tool_calls is complex
        extra.pop("response_format", None)
        stream = False

    if stream:
        full_content = []
        stream_obj = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            **extra,
        )
        try:
            async for chunk in stream_obj:
                if abort_event and abort_event.is_set():
                    raise asyncio.CancelledError("Aborted")
                delta = chunk.choices[0].delta if chunk.choices else None
                content = (delta.content or "") if delta else ""
                if content and on_chunk:
                    r = on_chunk(content)
                    if asyncio.iscoroutine(r):
                        await r
                full_content.append(content)
        except (asyncio.CancelledError, GeneratorExit):
            await stream_obj.close()
            raise
        return "".join(full_content)
    else:
        if abort_event and abort_event.is_set():
            raise asyncio.CancelledError("Aborted")
        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=False,
            **extra,
        )
        choice = resp.choices[0]
        message = choice.message
        finish_reason = getattr(choice, "finish_reason", None) or ""
        return _message_to_result(message, finish_reason)


async def chat_completion(
    messages: list[dict],
    api_config: dict,
    on_chunk: Optional[Callable[[str], None]] = None,
    abort_event: Optional[Any] = None,
    stream: bool = True,
    temperature: Optional[float] = None,
    response_format: Optional[dict] = None,
    tools: Optional[List[dict]] = None,
) -> Union[str, dict]:
    """Call OpenAI-compatible chat completions API.
    When tools is provided: uses stream=False, omits response_format; may return dict with
    content, tool_calls, finish_reason when model requests tool calls.
    """
    model = api_config.get("model") or DEFAULT_MODEL
    temp = temperature if temperature is not None else api_config.get("temperature")
    client = _create_client(api_config)
    return await _chat_completion_impl(
        client, model, messages, on_chunk, abort_event, stream, temp, response_format, tools
    )
