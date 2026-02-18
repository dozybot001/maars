"""
OpenAI-compatible LLM client for planner.
"""

import asyncio
import json
from typing import Any, Callable, Optional

import httpx

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o"


async def chat_completion(
    messages: list[dict],
    api_config: dict,
    on_chunk: Optional[Callable[[str], None]] = None,
    abort_event: Optional[Any] = None,
    stream: bool = True,
) -> str:
    """Call OpenAI-compatible chat completions API."""
    base_url = (api_config.get("baseUrl") or DEFAULT_BASE_URL).rstrip("/")
    api_key = api_config.get("apiKey") or ""
    model = api_config.get("model") or DEFAULT_MODEL

    url = f"{base_url}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {"model": model, "messages": messages, "stream": stream}

    async with httpx.AsyncClient(timeout=120.0) as client:
        if stream:
            full_content = []
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if abort_event and abort_event.is_set():
                        raise asyncio.CancelledError("Aborted")
                    if not line or not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    delta = obj.get("choices", [{}])[0].get("delta", {})
                    chunk = delta.get("content") or ""
                    if chunk and on_chunk:
                        on_chunk(chunk)
                    full_content.append(chunk)
            return "".join(full_content)
        else:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
