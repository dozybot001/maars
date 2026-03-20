"""Shared helpers for per-agent run state lifecycle."""

import asyncio
from typing import Any, Awaitable, Callable, Optional

from loguru import logger


def clear_run_state(state: Any) -> None:
    """Clear run task + abort event for idea/plan/paper states."""
    if not state:
        return
    state.run_task = None
    state.abort_event = None


async def stop_run_state(
    session_id: str,
    state: Any,
    *,
    emit_safe: Callable[..., Awaitable[None]],
    error_event: str,
    error_message: str,
    emit_when_idle: bool = False,
) -> bool:
    """Stop one agent run state and optionally emit stop error event."""
    if not state:
        return False
    if state.abort_event:
        state.abort_event.set()

    is_running = bool(state.run_task and not state.run_task.done())
    if is_running:
        state.run_task.cancel()

    if is_running or emit_when_idle:
        await emit_safe(
            session_id,
            error_event,
            {"error": error_message},
            warning_label=f"{error_event} emit (stop)",
        )
    return is_running


async def guarded_agent_run(
    state: Any,
    session_id: str,
    agent_name: str,
    run_coro: Callable[..., Awaitable[Any]],
    *,
    emit_fn: Callable[..., Awaitable[None]],
    emit_safe_fn: Callable[..., Awaitable[None]],
    start_event: str,
    error_event: str,
    complete_callback: Optional[Callable[[Any], Awaitable[None]]] = None,
) -> None:
    """
    Common wrapper for idea/plan/paper agent background tasks.

    Handles: lock acquisition, abort_event lifecycle, start/error/cancel emit,
    and finally cleanup. The caller provides the actual agent logic as `run_coro`.

    Args:
        state: AgentRunState instance
        session_id: session for emit
        agent_name: for logging ("Idea", "Plan", "Paper")
        run_coro: async callable that runs the agent and returns result
        emit_fn: emit(session_id, event, payload)
        emit_safe_fn: emit_safe(session_id, event, payload, warning_label=...)
        start_event: event name to emit on start (e.g. "idea-start")
        error_event: event name to emit on error (e.g. "idea-error")
        complete_callback: async fn(result) called on success to emit completion
    """
    async with state.lock:
        if state.abort_event:
            state.abort_event.set()
        state.abort_event = asyncio.Event()
        abort_event = state.abort_event

    try:
        await emit_fn(session_id, start_event, {})
        result = await run_coro(abort_event)
        if complete_callback:
            await complete_callback(result)
    except asyncio.CancelledError:
        logger.warning("%s run cancelled session_id=%s", agent_name, session_id)
        await emit_safe_fn(
            session_id,
            error_event,
            {"error": f"{agent_name} Agent stopped by user"},
            warning_label=f"{error_event} emit (cancel)",
        )
        raise
    except Exception as e:
        err_msg = str(e)
        logger.warning("%s run error session_id=%s: %s", agent_name, session_id, err_msg)
        display_msg = f"{agent_name} Agent stopped by user" if "Aborted" in err_msg else err_msg
        await emit_safe_fn(
            session_id,
            error_event,
            {"error": display_msg},
            warning_label=f"{error_event} emit",
        )
        raise
    finally:
        async with state.lock:
            if state.abort_event is abort_event:
                state.abort_event = None
        state.run_task = None


def start_agent_task(state: Any, coro) -> bool:
    """Start a background agent task if not already running. Returns False if busy."""
    if state.run_task and not state.run_task.done():
        return False
    state.run_task = asyncio.create_task(coro)
    return True
