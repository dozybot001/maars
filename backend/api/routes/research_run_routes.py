"""Run/stop/retry stage routes for research pipeline."""

from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from db import get_research, update_research_stage

from .. import state as api_state
from ..schemas import ResearchRunRequest
from .research_helpers import _check_stage_prerequisites, _normalize_stage
from .research_pipeline import (
    _RUNNING,
    _abort_stage_runners,
    _emit_stage,
    _is_session_busy,
    _running_task_for,
)

router = APIRouter()


def _research_route_module():
    # Late import avoids circular import at module load time.
    from . import research as research_route

    return research_route


def _normalize_paper_format(value: Optional[str]) -> str:
    paper_format = (value or "markdown").lower().strip()
    if paper_format not in ("markdown", "latex"):
        return "markdown"
    return paper_format


def _run_response(mode: str, research_id: str, session_id: str, stage: str) -> dict:
    return {
        "success": True,
        "researchId": research_id,
        "sessionId": session_id,
        "mode": mode,
        "startStage": stage,
        "autoChain": True,
    }


async def _prepare_stage_request(research_id: str, stage: str, request: Request):
    session_id, session = await api_state.require_session(request)
    normalized_stage = _normalize_stage(stage)
    research = await get_research(research_id)
    if not research:
        return None, JSONResponse(status_code=404, content={"error": "Research not found"})
    prereq_err = await _check_stage_prerequisites(research, normalized_stage)
    if prereq_err:
        return None, JSONResponse(status_code=400, content={"error": prereq_err})
    if _is_session_busy(session_id):
        return None, JSONResponse(status_code=409, content={"error": "Another research pipeline is already running in this session"})
    return (session_id, session, research, normalized_stage), None


@router.post("/run")
async def run_research_route(research_id: str, body: ResearchRunRequest, request: Request):
    session_id, session = await api_state.require_session(request)
    research = await get_research(research_id)
    if not research:
        return JSONResponse(status_code=404, content={"error": "Research not found"})
    if _is_session_busy(session_id):
        return JSONResponse(status_code=409, content={"error": "Another research pipeline is already running in this session"})

    paper_format = _normalize_paper_format(body.format)

    route_module = _research_route_module()
    await route_module.clear_research_stage_data_for_retry(
        research.get("currentIdeaId"),
        research.get("currentPlanId"),
        "refine",
    )

    route_module._start_stage_pipeline_task(
        session_id=session_id,
        session=session,
        research_id=research_id,
        start_stage="refine",
        paper_format=paper_format,
        reset_start_stage=True,
    )
    return {
        "success": True,
        "researchId": research_id,
        "sessionId": session_id,
        "mode": "run",
        "startStage": "refine",
        "autoChain": True,
    }


@router.post("/stop")
async def stop_research_route(research_id: str, request: Request):
    """Stop current research pipeline run in this session (pause)."""

    session_id, session = await api_state.require_session(request)

    research = await get_research(research_id)
    if not research:
        return JSONResponse(status_code=404, content={"error": "Research not found"})

    # Stop should work even if frontend session changed after refresh.
    active_session_id = session_id
    active_session = session
    task = _running_task_for(active_session_id, research_id)
    if not task or task.done():
        for (sid, rid), entry in list(_RUNNING.items()):
            if rid != research_id:
                continue
            t = (entry or {}).get("task")
            if t and not t.done():
                active_session_id = sid
                active_session = api_state.sessions.get(sid) or session
                task = t
                break

    await _abort_stage_runners(active_session, include_execute=True)

    if task and not task.done():
        task.cancel()
        await update_research_stage(research_id, stage_status="stopped", error=None)
        try:
            stage = _normalize_stage(research.get("stage") or "refine")
            await _emit_stage(active_session_id, research_id, stage, "stopped")
            if active_session_id != session_id:
                await _emit_stage(session_id, research_id, stage, "stopped")
        except Exception:
            pass
        return {"success": True, "researchId": research_id, "sessionId": active_session_id, "stopped": True}

    current_stage = _normalize_stage(research.get("stage") or "refine")
    current_status = str(research.get("stageStatus") or "idle").strip().lower()
    if current_status == "running":
        # Recover from stale DB state when no in-memory task exists.
        await update_research_stage(research_id, stage=current_stage, stage_status="stopped", error=None)
        try:
            await _emit_stage(active_session_id, research_id, current_stage, "stopped")
            if active_session_id != session_id:
                await _emit_stage(session_id, research_id, current_stage, "stopped")
        except Exception:
            pass
        return {
            "success": True,
            "researchId": research_id,
            "sessionId": active_session_id,
            "stopped": True,
            "message": "Recovered stale running state",
        }

    return {"success": True, "researchId": research_id, "sessionId": active_session_id, "stopped": False, "message": "No running pipeline"}


@router.post("/retry")
async def retry_research_route(research_id: str, body: ResearchRunRequest, request: Request):
    """Retry research pipeline starting from the current stage, using existing upstream artifacts."""

    session_id, session = await api_state.require_session(request)

    research = await get_research(research_id)
    if not research:
        return JSONResponse(status_code=404, content={"error": "Research not found"})

    if _is_session_busy(session_id):
        return JSONResponse(status_code=409, content={"error": "Another research pipeline is already running in this session"})

    paper_format = _normalize_paper_format(body.format)

    start_stage = _normalize_stage(research.get("stage") or "refine")
    route_module = _research_route_module()
    await route_module.clear_research_stage_data_for_retry(
        research.get("currentIdeaId"),
        research.get("currentPlanId"),
        start_stage,
    )
    route_module._start_stage_pipeline_task(
        session_id=session_id,
        session=session,
        research_id=research_id,
        start_stage=start_stage,
        paper_format=paper_format,
        reset_start_stage=True,
    )
    return {
        "success": True,
        "researchId": research_id,
        "sessionId": session_id,
        "mode": "retry",
        "startStage": start_stage,
        "autoChain": True,
    }


@router.post("/stage/{stage}/run")
async def run_research_stage_route(research_id: str, stage: str, body: ResearchRunRequest, request: Request):
    prepared, error = await _prepare_stage_request(research_id, stage, request)
    if error:
        return error
    session_id, session, _research, stage = prepared
    paper_format = _normalize_paper_format(body.format)
    route_module = _research_route_module()
    route_module._start_stage_pipeline_task(
        session_id=session_id,
        session=session,
        research_id=research_id,
        start_stage=stage,
        paper_format=paper_format,
        reset_start_stage=True,
    )
    return _run_response("run-stage", research_id, session_id, stage)


@router.post("/stage/{stage}/resume")
async def resume_research_stage_route(research_id: str, stage: str, body: ResearchRunRequest, request: Request):
    prepared, error = await _prepare_stage_request(research_id, stage, request)
    if error:
        return error
    session_id, session, research, stage = prepared
    current_stage = _normalize_stage(research.get("stage") or "refine")
    current_status = str(research.get("stageStatus") or "idle").strip().lower()
    if current_stage != stage or current_status not in ("stopped", "failed"):
        return JSONResponse(
            status_code=409,
            content={
                "error": (
                    f"Resume only applies to the same stage in stopped/failed state "
                    f"(current: {current_stage} · {current_status})."
                )
            },
        )
    paper_format = _normalize_paper_format(body.format)
    route_module = _research_route_module()
    route_module._start_stage_pipeline_task(
        session_id=session_id,
        session=session,
        research_id=research_id,
        start_stage=stage,
        paper_format=paper_format,
        reset_start_stage=False,
    )
    return _run_response("resume-stage", research_id, session_id, stage)


@router.post("/stage/{stage}/retry")
async def retry_research_stage_route(research_id: str, stage: str, body: ResearchRunRequest, request: Request):
    prepared, error = await _prepare_stage_request(research_id, stage, request)
    if error:
        return error
    session_id, session, research, stage = prepared
    paper_format = _normalize_paper_format(body.format)
    route_module = _research_route_module()
    await route_module.clear_research_stage_data_for_retry(
        research.get("currentIdeaId"),
        research.get("currentPlanId"),
        stage,
    )
    route_module._start_stage_pipeline_task(
        session_id=session_id,
        session=session,
        research_id=research_id,
        start_stage=stage,
        paper_format=paper_format,
        reset_start_stage=True,
    )
    return _run_response("retry-stage", research_id, session_id, stage)


@router.post("/stage/{stage}/stop")
async def stop_research_stage_route(research_id: str, stage: str, request: Request):
    session_id, session = await api_state.require_session(request)
    stage = _normalize_stage(stage)
    research = await get_research(research_id)
    if not research:
        return JSONResponse(status_code=404, content={"error": "Research not found"})

    # Resolve active running session by research id first; UI session may differ after refresh.
    active_session_id = session_id
    active_session = session
    entry = _RUNNING.get((active_session_id, research_id)) or {}
    if not entry:
        for (sid, rid), candidate in list(_RUNNING.items()):
            if rid != research_id:
                continue
            task_candidate = (candidate or {}).get("task")
            if task_candidate and not task_candidate.done():
                active_session_id = sid
                active_session = api_state.sessions.get(sid) or session
                entry = candidate or {}
                break

    running_stage = _normalize_stage(entry.get("stage") or (research.get("stage") or "refine"))
    task = entry.get("task")
    runner_was_running = (
        stage == "execute"
        and getattr(active_session, "runner", None) is not None
        and bool(getattr(active_session.runner, "is_running", False))
    )
    await _abort_stage_runners(active_session, include_execute=True)
    pipeline_task_active = task and not task.done() and running_stage == stage
    if pipeline_task_active or runner_was_running:
        if pipeline_task_active:
            task.cancel()
        await update_research_stage(research_id, stage=stage, stage_status="stopped", error=None)
        await _emit_stage(active_session_id, research_id, stage, "stopped")
        if active_session_id != session_id:
            await _emit_stage(session_id, research_id, stage, "stopped")
        return {"success": True, "researchId": research_id, "sessionId": active_session_id, "stage": stage, "stopped": True}

    current_stage = _normalize_stage(research.get("stage") or "refine")
    current_status = str(research.get("stageStatus") or "idle").strip().lower()
    if current_stage == stage and current_status == "running":
        # Stale status recovery: DB says running but runtime has no active task.
        await update_research_stage(research_id, stage=stage, stage_status="stopped", error=None)
        await _emit_stage(active_session_id, research_id, stage, "stopped")
        if active_session_id != session_id:
            await _emit_stage(session_id, research_id, stage, "stopped")
        return {
            "success": True,
            "researchId": research_id,
            "sessionId": active_session_id,
            "stage": stage,
            "stopped": True,
            "message": "Recovered stale running state",
        }

    return {"success": True, "researchId": research_id, "sessionId": active_session_id, "stage": stage, "stopped": False, "message": "No running stage task"}
