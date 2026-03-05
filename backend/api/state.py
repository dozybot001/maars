"""
Shared API state - sio, runner, Plan/Idea Agent run state.
Initialized by main.py after creating app and services.
"""

import asyncio
import hashlib
import hmac
import os
import re
import secrets
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from fastapi import HTTPException
from loguru import logger


@dataclass
class PlanRunState:
    """Plan Agent 运行状态：abort 信号、run_task。供 /api/plan/stop 使用。"""
    abort_event: Optional[Any] = None
    run_task: Optional[Any] = None
    lock: Optional[Any] = None


@dataclass
class IdeaRunState:
    """Idea Agent 运行状态：run_task、abort_event。供 /api/idea/stop 使用。"""
    run_task: Optional[Any] = None
    abort_event: Optional[Any] = None


@dataclass
class PaperRunState:
    """Paper Agent 运行状态：run_task、abort_event。供 /api/paper/stop 使用。"""
    run_task: Optional[Any] = None
    abort_event: Optional[Any] = None


@dataclass
class SessionState:
    """Per-session runtime state: runner + per-agent run states."""
    session_id: str
    runner: Any
    plan_run_state: PlanRunState
    idea_run_state: IdeaRunState
    paper_run_state: PaperRunState
    last_seen: float = 0.0


# Set by main.py
sio: Any = None
sessions: Dict[str, SessionState] = {}
_sessions_lock: Optional[asyncio.Lock] = None
_socket_session_map: Dict[str, str] = {}
_session_secret = os.getenv("MAARS_SESSION_SECRET") or secrets.token_hex(32)
_session_id_re = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
SESSION_IDLE_TTL_SECONDS = int(os.getenv("MAARS_SESSION_IDLE_TTL_SECONDS", "7200"))
_session_sweep_interval_seconds = int(os.getenv("MAARS_SESSION_SWEEP_INTERVAL_SECONDS", "120"))
_last_session_sweep_ts = 0.0


def init_api_state(
    sio_instance,
):
    global sio, _sessions_lock
    sio = sio_instance
    if _sessions_lock is None:
        _sessions_lock = asyncio.Lock()


def normalize_session_id(raw_session_id: Optional[str]) -> str:
    """Normalize and validate session id."""
    sid = str(raw_session_id or "").strip()
    if not sid:
        raise ValueError("sessionId is required")
    sid = sid.replace("/", "_").replace("\\", "_")
    sid = sid[:128]
    if not _session_id_re.match(sid):
        raise ValueError("Invalid sessionId format")
    return sid


def _sign_session_id(session_id: str) -> str:
    return hmac.new(
        _session_secret.encode("utf-8"),
        session_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_session_token(session_id: str, session_token: Optional[str]) -> bool:
    token = str(session_token or "").strip()
    if not token:
        return False
    expected = _sign_session_id(session_id)
    return hmac.compare_digest(expected, token)


def issue_session_credentials() -> Dict[str, str]:
    """Create a new signed session credential pair."""
    session_id = normalize_session_id(f"sess_{secrets.token_urlsafe(18)}")
    session_token = _sign_session_id(session_id)
    return {"sessionId": session_id, "sessionToken": session_token}


def resolve_session_id(request: Any) -> str:
    """Resolve and verify session id/token from HTTP request."""
    header_sid = request.headers.get("X-MAARS-SESSION-ID")
    header_token = request.headers.get("X-MAARS-SESSION-TOKEN")
    query_sid = request.query_params.get("sessionId")
    query_token = request.query_params.get("sessionToken")
    raw_sid = header_sid or query_sid
    raw_token = header_token or query_token
    if not raw_sid or not raw_token:
        raise HTTPException(status_code=401, detail="Missing session credentials")
    try:
        session_id = normalize_session_id(raw_sid)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    if not verify_session_token(session_id, raw_token):
        raise HTTPException(status_code=401, detail="Invalid session credentials")
    return session_id


async def require_session(request: Any) -> tuple[str, SessionState]:
    """
    Resolve + verify HTTP session credentials, then return session state.
    Used by API routes to avoid duplicated boilerplate.
    """
    session_id = resolve_session_id(request)
    session = await get_or_create_session_state(session_id)
    return session_id, session


def resolve_socket_session_id(auth: Any) -> str:
    """Resolve and verify session id/token from websocket auth payload."""
    if not isinstance(auth, dict):
        raise ValueError("Missing socket auth")
    raw_sid = auth.get("sessionId")
    raw_token = auth.get("sessionToken")
    session_id = normalize_session_id(raw_sid)
    if not verify_session_token(session_id, raw_token):
        raise ValueError("Invalid session credentials")
    return session_id


def _is_session_busy(state: SessionState) -> bool:
    if state.runner and getattr(state.runner, "is_running", False):
        return True
    if state.plan_run_state and state.plan_run_state.run_task and not state.plan_run_state.run_task.done():
        return True
    if state.idea_run_state and state.idea_run_state.run_task and not state.idea_run_state.run_task.done():
        return True
    if state.paper_run_state and state.paper_run_state.run_task and not state.paper_run_state.run_task.done():
        return True
    return False


async def _cleanup_stale_sessions_locked(now_ts: float) -> None:
    stale_ids = []
    bound_session_ids = set(_socket_session_map.values())
    for sid, state in sessions.items():
        if sid in bound_session_ids:
            continue
        if _is_session_busy(state):
            continue
        if now_ts - state.last_seen < SESSION_IDLE_TTL_SECONDS:
            continue
        stale_ids.append(sid)
    for sid in stale_ids:
        sessions.pop(sid, None)


async def cleanup_stale_sessions(force: bool = False) -> None:
    """Sweep stale session states that are idle and unbound."""
    global _sessions_lock, _last_session_sweep_ts
    if _sessions_lock is None:
        _sessions_lock = asyncio.Lock()
    now_ts = time.time()
    if (not force) and (now_ts - _last_session_sweep_ts < _session_sweep_interval_seconds):
        return
    async with _sessions_lock:
        now_ts = time.time()
        if (not force) and (now_ts - _last_session_sweep_ts < _session_sweep_interval_seconds):
            return
        _last_session_sweep_ts = now_ts
        await _cleanup_stale_sessions_locked(now_ts)


async def get_or_create_session_state(session_id: str) -> SessionState:
    """Get session state, creating isolated runner and run states if absent."""
    global _sessions_lock, _last_session_sweep_ts
    if _sessions_lock is None:
        _sessions_lock = asyncio.Lock()
    normalized = normalize_session_id(session_id)
    async with _sessions_lock:
        existing = sessions.get(normalized)
        if existing:
            existing.last_seen = time.time()
            now_ts = existing.last_seen
            if now_ts - _last_session_sweep_ts >= _session_sweep_interval_seconds:
                _last_session_sweep_ts = now_ts
                await _cleanup_stale_sessions_locked(now_ts)
            return existing

        from task_agent import ExecutionRunner

        plan_state = PlanRunState(lock=asyncio.Lock())
        idea_state = IdeaRunState()
        paper_state = PaperRunState()
        runner = ExecutionRunner(sio, session_id=normalized)
        created = SessionState(
            session_id=normalized,
            runner=runner,
            plan_run_state=plan_state,
            idea_run_state=idea_state,
            paper_run_state=paper_state,
            last_seen=time.time(),
        )
        sessions[normalized] = created
        now_ts = created.last_seen
        if now_ts - _last_session_sweep_ts >= _session_sweep_interval_seconds:
            _last_session_sweep_ts = now_ts
            await _cleanup_stale_sessions_locked(now_ts)
        return created


def bind_socket_to_session(socket_id: str, session_id: str) -> str:
    """Track socket -> session mapping and return normalized session id."""
    normalized = normalize_session_id(session_id)
    _socket_session_map[socket_id] = normalized
    return normalized


async def unbind_socket(socket_id: str) -> None:
    """Unbind disconnected socket and cleanup idle session state when safe."""
    global _sessions_lock
    session_id = _socket_session_map.pop(socket_id, None)
    if not session_id:
        return
    if _sessions_lock is None:
        _sessions_lock = asyncio.Lock()
    async with _sessions_lock:
        if any(v == session_id for v in _socket_session_map.values()):
            return
        state = sessions.get(session_id)
        if state and not _is_session_busy(state):
            sessions.pop(session_id, None)
    await cleanup_stale_sessions(force=True)


async def emit(session_id: str, event: str, payload: dict) -> None:
    """Emit websocket event to one session room."""
    if not sio:
        return
    await sio.emit(event, payload, to=normalize_session_id(session_id))


def emit_background(session_id: str, event: str, payload: dict) -> None:
    """Fire-and-forget emit to one session room."""
    if not sio:
        return
    try:
        asyncio.create_task(emit(session_id, event, payload))
    except RuntimeError:
        pass


async def emit_safe(
    session_id: str,
    event: str,
    payload: dict,
    *,
    warning_label: Optional[str] = None,
) -> None:
    """Emit event with local error swallow + warning log."""
    try:
        await emit(session_id, event, payload)
    except Exception as e:
        logger.warning("{} failed: {}", warning_label or f"{event} emit", e)


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
    error_event: str,
    error_message: str,
    emit_when_idle: bool = False,
) -> bool:
    """
    Stop one agent run state and optionally emit stop error event.
    Returns whether there was an active running task.
    """
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
