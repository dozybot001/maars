"""
Shared Google ADK runtime utilities.
Centralizes runner lifecycle, event loop, abort handling, and finish payload parsing.
"""

import asyncio
import json
import uuid
from typing import Any, Callable, Dict, Optional

import orjson
from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from loguru import logger

ToolCallHook = Callable[[str, Dict[str, Any], int], Any]
ToolResponseHook = Callable[[str, Any, int], Any]
TextHook = Callable[[str, int], Any]


async def _maybe_await(value: Any) -> None:
    if asyncio.iscoroutine(value):
        await value


def build_tool_args_preview(args: Dict[str, Any], max_len: int = 200) -> str:
    preview = json.dumps(args or {}, ensure_ascii=False)
    if len(preview) > max_len:
        return preview[:max_len] + "..."
    return preview


def parse_function_response_payload(response: Any) -> Dict[str, Any]:
    """
    Parse function response payload into dict.
    ADK response shape can vary across tool implementations.
    """
    if not response:
        return {}
    raw = response.get("result", response) if isinstance(response, dict) else response
    if isinstance(raw, dict):
        return raw
    try:
        return orjson.loads(str(raw))
    except Exception:
        return {}


async def run_adk_agent_loop(
    *,
    app_name: str,
    agent_name: str,
    model: str,
    instruction: str,
    tools: list[Any],
    user_message: str,
    max_turns: int,
    abort_event: Optional[Any] = None,
    abort_message: str = "Agent aborted",
    on_tool_call: Optional[ToolCallHook] = None,
    on_tool_response: Optional[ToolResponseHook] = None,
    on_text: Optional[TextHook] = None,
    user_id: str = "maars_user",
    session_id: Optional[str] = None,
) -> int:
    """
    Run one ADK agent session and invoke hooks for tool calls/responses and model text.
    Returns observed turn count.
    """
    agent = Agent(
        model=model,
        name=agent_name,
        instruction=instruction,
        tools=tools,
    )
    runner = Runner(
        agent=agent,
        app_name=app_name,
        session_service=InMemorySessionService(),
        auto_create_session=True,
    )
    new_message = types.Content(
        role="user",
        parts=[types.Part.from_text(text=user_message)],
    )
    effective_session_id = session_id or str(uuid.uuid4())
    turn_count = 0

    async def _run() -> None:
        nonlocal turn_count
        try:
            async for event in runner.run_async(
                user_id=user_id,
                session_id=effective_session_id,
                new_message=new_message,
            ):
                if abort_event and abort_event.is_set():
                    raise asyncio.CancelledError(abort_message)

                turn_count += 1
                if turn_count > max_turns:
                    break

                if not event.content or not event.content.parts:
                    continue

                get_calls = getattr(event, "get_function_calls", None)
                get_responses = getattr(event, "get_function_responses", None)
                calls = get_calls() if callable(get_calls) else []
                responses = get_responses() if callable(get_responses) else []

                if calls:
                    for call in calls:
                        name = getattr(call, "name", None) or ""
                        args = getattr(call, "args", None) or {}
                        if on_tool_call:
                            await _maybe_await(on_tool_call(name, args, turn_count))
                    continue

                if responses:
                    for response in responses:
                        name = getattr(response, "name", None) or ""
                        payload = getattr(response, "response", None)
                        if on_tool_response:
                            await _maybe_await(on_tool_response(name, payload, turn_count))
                    continue

                if on_text:
                    for part in event.content.parts:
                        text = getattr(part, "text", None) or ""
                        if text:
                            await _maybe_await(on_text(text, turn_count))
        finally:
            try:
                await runner.close()
            except Exception as e:
                logger.debug("Runner close: %s", e)

    run_task = asyncio.create_task(_run())
    if abort_event:
        while not run_task.done():
            await asyncio.sleep(0.3)
            if abort_event.is_set():
                run_task.cancel()
                try:
                    await run_task
                except asyncio.CancelledError:
                    pass
                raise asyncio.CancelledError(abort_message)
        await run_task
    else:
        await run_task

    return turn_count
