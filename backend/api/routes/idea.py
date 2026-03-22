"""Idea Agent API - 文献收集（Refine）。HTTP 仅触发，数据由 WebSocket 回传。"""

import time

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from loguru import logger

from db import get_effective_config, get_idea, save_idea
from mode import run_idea
from shared.realtime import build_thinking_emitter

from .. import state as api_state
from ..run_state_ops import guarded_agent_run, start_agent_task
from ..schemas import IdeaCollectRequest

router = APIRouter()


@router.get("")
async def get_idea_route(idea_id: str = Query("test", alias="ideaId")):
    """Get idea data (idea text, keywords, papers, etc.)."""
    idea_data = await get_idea(idea_id)
    return {"idea": idea_data}


async def _run_collect_inner(session_id: str, state, idea_id: str, idea: str, limit: int):
    """后台执行文献收集，通过 WebSocket 回传数据。"""
    config = await get_effective_config()
    logger.info(
        "Idea run start session_id={} idea_id={} chars={} limit={} mode={}",
        session_id, idea_id, len((idea or "").strip()), limit,
        config.get("mode", "mock"),
    )
    on_thinking = build_thinking_emitter(
        api_state.sio, event_name="idea-thinking", source="idea",
        default_operation="Refine", room=session_id, warning_label="idea-thinking",
    )

    async def _run_agent(abort_event):
        return await run_idea(idea=idea, api_config=config, limit=limit, on_thinking=on_thinking, abort_event=abort_event)

    async def _on_complete(result):
        idea_data = {
            "idea": idea, "keywords": result.get("keywords", []),
            "papers": result.get("papers", []), "refined_idea": result.get("refined_idea"),
        }
        await save_idea(idea_data, idea_id)
        await api_state.emit(session_id, "idea-complete", {
            "ideaId": idea_id, "keywords": idea_data["keywords"],
            "papers": idea_data["papers"], "refined_idea": idea_data["refined_idea"],
        })
        logger.info("Idea run complete session_id={} idea_id={}", session_id, idea_id)

    await guarded_agent_run(
        state, session_id, "Idea", _run_agent,
        emit_fn=api_state.emit, emit_safe_fn=api_state.emit_safe,
        start_event="idea-start", error_event="idea-error",
        complete_callback=_on_complete,
    )


@router.post("/collect")
async def collect_literature_route(body: IdeaCollectRequest, request: Request):
    """Collect literature from fuzzy idea. 立即返回，数据由 WebSocket idea-complete 回传。"""
    session_id, session = await api_state.require_session(request)
    state = session.idea_run_state
    if state.run_task and not state.run_task.done():
        return JSONResponse(status_code=409, content={"error": "Idea Agent already in progress"})

    idea_id = f"idea_{int(time.time() * 1000)}"
    idea = (body.idea or "").strip()
    if not idea:
        return JSONResponse(status_code=400, content={"error": "idea is required", "ideaId": idea_id})

    await save_idea({"idea": idea, "keywords": [], "papers": []}, idea_id)
    start_agent_task(state, _run_collect_inner(session_id, state, idea_id, idea, body.limit or 10))

    return {"success": True, "ideaId": idea_id, "sessionId": session_id}


@router.post("/stop")
async def stop_idea(request: Request):
    """停止 Idea Agent。"""
    session_id, session = await api_state.require_session(request)
    await api_state.stop_run_state(
        session_id, session.idea_run_state,
        error_event="idea-error", error_message="Idea Agent stopped by user",
    )
    return {"success": True}
