"""
OpenAI-compatible LLM client for planner.
Uses openai SDK with tenacity retry.
"""

import asyncio
from typing import Any, Callable, Optional

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


def _create_client(api_config: dict) -> AsyncOpenAI:
    base_url = (api_config.get("baseUrl") or DEFAULT_BASE_URL).rstrip("/")
    api_key = api_config.get("apiKey") or "not-needed"
    return AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=120.0)


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
) -> str:
    """Inner implementation with retry."""
    if stream:
        full_content = []
        stream_obj = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
        )
        async for chunk in stream_obj:
            if abort_event and abort_event.is_set():
                raise asyncio.CancelledError("Aborted")
            delta = chunk.choices[0].delta if chunk.choices else None
            content = (delta.content or "") if delta else ""
            if content and on_chunk:
                on_chunk(content)
            full_content.append(content)
        return "".join(full_content)
    else:
        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=False,
        )
        return resp.choices[0].message.content or ""


async def chat_completion(
    messages: list[dict],
    api_config: dict,
    on_chunk: Optional[Callable[[str], None]] = None,
    abort_event: Optional[Any] = None,
    stream: bool = True,
) -> str:
    """Call OpenAI-compatible chat completions API."""
    model = api_config.get("model") or DEFAULT_MODEL
    client = _create_client(api_config)
    return await _chat_completion_impl(
        client, model, messages, on_chunk, abort_event, stream
    )
