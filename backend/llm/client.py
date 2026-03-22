"""
LLM client for all MAARS agents. Uses Google GenAI SDK (Gemini API only).

Two high-level entry points:
  llm_call            — simple single-round call
  llm_call_structured — with parse / validate / repair loop

Both accept an optional `mock` parameter: if provided, skip the real API
and stream/return the mock content directly.
"""

import asyncio
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence

from google import genai
from google.genai import types

from mock.stream import stream_mock
from shared.constants import DEFAULT_MODEL, LLM_REQUEST_TIMEOUT

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_prompt_cache: Dict[str, str] = {}


def load_prompt(name: str) -> str:
    """Load a prompt from llm/prompts/{name}."""
    if name not in _prompt_cache:
        _prompt_cache[name] = (_PROMPTS_DIR / name).read_text(encoding="utf-8").strip()
    return _prompt_cache[name]


# ── Content helpers ──────────────────────────────────────────────────

def user_msg(text: str) -> types.Content:
    """Create a user Content from plain text."""
    return types.Content(role="user", parts=[types.Part.from_text(text=text)])


def model_msg(text: str) -> types.Content:
    """Create a model Content from plain text."""
    return types.Content(role="model", parts=[types.Part.from_text(text=text)])


# ── High-level API ───────────────────────────────────────────────────

async def llm_call(
    *,
    user: str,
    api_config: dict,
    system: str = "",
    temperature: Optional[float] = None,
    json_output: bool = False,
    on_chunk: Optional[Callable[[str], None]] = None,
    abort_event: Optional[Any] = None,
    mock: Optional[str] = None,
) -> str:
    """Single-round LLM call. stream is inferred from on_chunk.
    If mock is provided, skip API and return mock content."""
    if mock is not None:
        return await stream_mock(mock, on_chunk, abort_event)
    return await _chat_completion(
        contents=[user_msg(user)],
        api_config=api_config,
        system_instruction=system,
        temperature=temperature,
        response_mime_type="application/json" if json_output else None,
        on_chunk=on_chunk,
        stream=on_chunk is not None,
        abort_event=abort_event,
    )


async def llm_call_structured(
    *,
    user: str,
    api_config: dict,
    parse_fn: Callable[[str], Any],
    temperatures: Sequence[float],
    system: str = "",
    validate_fn: Optional[Callable[[Any], tuple[bool, str]]] = None,
    json_output: bool = False,
    on_chunk: Optional[Callable[[str], None]] = None,
    abort_event: Optional[Any] = None,
    mock: Optional[str] = None,
) -> tuple[Any, str]:
    """LLM call with parse → validate → repair retry loop.
    If mock is provided, skip API, stream mock, parse once (no retry)."""
    if mock is not None:
        await stream_mock(mock, on_chunk, abort_event)
        parsed = parse_fn(mock)
        if validate_fn is not None:
            ok, msg = validate_fn(parsed)
            if not ok:
                raise ValueError(msg or "Mock response validation failed")
        return parsed, mock

    base = [user_msg(user)]
    conversation = list(base)
    attempts = list(temperatures) or [0.0]
    last_error = "Structured output generation failed"

    for i, temp in enumerate(attempts):
        raw = await _chat_completion(
            contents=conversation,
            api_config=api_config,
            system_instruction=system,
            temperature=temp,
            response_mime_type="application/json" if json_output else None,
            on_chunk=on_chunk if i == 0 else None,
            stream=bool(on_chunk) and i == 0,
            abort_event=abort_event,
        )
        try:
            parsed = parse_fn(raw)
            if validate_fn is not None:
                ok, msg = validate_fn(parsed)
                if not ok:
                    raise ValueError(msg or "Structured output validation failed")
            return parsed, raw
        except Exception as exc:
            last_error = str(exc) or last_error
            if i >= len(attempts) - 1:
                raise ValueError(last_error) from exc
            conversation = list(base)
            if (raw or "").strip():
                conversation.append(model_msg(raw))
            conversation.append(user_msg(_repair_prompt(last_error)))

    raise ValueError(last_error)


def _repair_prompt(error_message: str) -> str:
    detail = (error_message or "Structured output validation failed.").strip()
    return (
        "Your previous response did not satisfy the required output format.\n"
        f"Error: {detail}\n\n"
        "Return a corrected response only.\n"
        "Do not explain the mistake.\n"
        "Do not repeat the task description.\n"
        "Preserve the intended semantics, but fix the output so it matches the required structure exactly."
    )


# ── Low-level Gemini call ────────────────────────────────────────────

async def _chat_completion(
    *,
    contents: list[types.Content],
    api_config: dict,
    system_instruction: str = "",
    on_chunk: Optional[Callable[[str], None]] = None,
    abort_event: Optional[Any] = None,
    stream: bool = False,
    temperature: Optional[float] = None,
    response_mime_type: Optional[str] = None,
) -> str:
    """Low-level Gemini API call. Prefer llm_call / llm_call_structured."""
    cfg = dict(api_config or {})
    model = cfg.get("model") or DEFAULT_MODEL
    temp = temperature if temperature is not None else cfg.get("temperature")
    api_key = cfg.get("apiKey") or cfg.get("api_key") or ""

    client = genai.Client(api_key=api_key)

    config_kw: dict = {}
    if system_instruction:
        config_kw["system_instruction"] = system_instruction
    if temp is not None:
        config_kw["temperature"] = temp
    if response_mime_type:
        config_kw["response_mime_type"] = response_mime_type

    config = types.GenerateContentConfig(**config_kw) if config_kw else None

    _ABORT_SENTINEL = object()

    async def _abort_waiter():
        while True:
            await asyncio.sleep(0.5)
            if abort_event and abort_event.is_set():
                return _ABORT_SENTINEL

    try:
        aclient = client.aio
        try:
            if abort_event and abort_event.is_set():
                raise asyncio.CancelledError("Aborted")

            if stream:
                full_content = []
                stream_iter = await asyncio.wait_for(
                    aclient.models.generate_content_stream(
                        model=model, contents=contents, config=config,
                    ),
                    timeout=LLM_REQUEST_TIMEOUT,
                )
                async for chunk in stream_iter:
                    if abort_event and abort_event.is_set():
                        raise asyncio.CancelledError("Aborted")
                    text = chunk.text or ""
                    if text and on_chunk:
                        r = on_chunk(text)
                        if asyncio.iscoroutine(r):
                            await r
                    full_content.append(text)
                return "".join(full_content)

            api_coro = aclient.models.generate_content(
                model=model, contents=contents, config=config,
            )
            if abort_event:
                api_task = asyncio.ensure_future(api_coro)
                abort_task = asyncio.ensure_future(_abort_waiter())
                done, pending = await asyncio.wait(
                    [api_task, abort_task],
                    timeout=LLM_REQUEST_TIMEOUT,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for t in pending:
                    t.cancel()
                if not done:
                    raise TimeoutError(f"LLM request timed out after {LLM_REQUEST_TIMEOUT}s")
                if abort_task in done:
                    api_task.cancel()
                    raise asyncio.CancelledError("Aborted")
                resp = api_task.result()
            else:
                resp = await asyncio.wait_for(api_coro, timeout=LLM_REQUEST_TIMEOUT)
        finally:
            try:
                await aclient.aclose()
            except Exception:
                pass
    except asyncio.CancelledError:
        raise
    except TimeoutError:
        raise RuntimeError(f"LLM request timed out after {LLM_REQUEST_TIMEOUT}s")
    except asyncio.TimeoutError:
        raise RuntimeError(f"LLM request timed out after {LLM_REQUEST_TIMEOUT}s")
    except Exception as e:
        raise RuntimeError(f"Gemini API error: {e}") from e

    if abort_event and abort_event.is_set():
        raise asyncio.CancelledError("Aborted")

    return resp.text or ""
