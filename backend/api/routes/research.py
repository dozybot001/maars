"""Research API - Product-level unit (Research) that runs the full pipeline.

Research is the primary unit of work. It links to the latest ideaId and planId
created during the pipeline runs.

Pipeline stages: refine -> plan -> execute -> paper
"""

import asyncio
import time
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from loguru import logger

from db import (
    create_research,
    get_effective_config,
    get_execution,
    get_idea,
    get_paper,
    get_plan,
    get_research,
    list_plan_outputs,
    list_researches,
    save_execution,
    save_idea,
    update_research_stage,
)
from plan_agent.execution_builder import build_execution_from_plan
from visualization import build_layout_from_execution

from .. import state as api_state
from ..schemas import PlanRunRequest, ResearchCreateRequest, ResearchRunRequest

# Reuse existing stage runners
from .idea import _run_collect_inner
from .plan import _run_plan_inner
from .paper import _run_paper_inner

router = APIRouter()


_RUNNING: dict[tuple[str, str], asyncio.Task] = {}


def _stage_rank(stage: str) -> int:
    order = {"refine": 0, "plan": 1, "execute": 2, "paper": 3}
    return order.get((stage or "").strip().lower(), 0)


def _normalize_stage(stage: str) -> str:
    s = (stage or "").strip().lower()
    return s if s in ("refine", "plan", "execute", "paper") else "refine"


def _make_research_id() -> str:
    return f"research_{int(time.time() * 1000)}"


def _make_title(prompt: str) -> str:
    s = (prompt or "").strip().replace("\n", " ")
    s = " ".join(s.split())
    if not s:
        return "Untitled"
    return s[:64]


@router.get("")
async def list_researches_route(request: Request):
    await api_state.require_session(request)
    items = await list_researches()
    return {"items": items}


@router.post("")
async def create_research_route(body: ResearchCreateRequest, request: Request):
    await api_state.require_session(request)
    prompt = (body.prompt or "").strip()
    if not prompt:
        return JSONResponse(status_code=400, content={"error": "prompt is required"})

    research_id = _make_research_id()
    await create_research(research_id, prompt, _make_title(prompt))
    return {"researchId": research_id}


@router.get("/{research_id}")
async def get_research_route(research_id: str, request: Request):
    await api_state.require_session(request)
    research = await get_research(research_id)
    if not research:
        return JSONResponse(status_code=404, content={"error": "Research not found"})

    idea_id = research.get("currentIdeaId")
    plan_id = research.get("currentPlanId")

    idea = await get_idea(idea_id) if idea_id else None
    plan = await get_plan(idea_id, plan_id) if (idea_id and plan_id) else None
    execution = await get_execution(idea_id, plan_id) if (idea_id and plan_id) else None
    outputs = await list_plan_outputs(idea_id, plan_id) if (idea_id and plan_id) else {}
    paper = await get_paper(idea_id, plan_id) if (idea_id and plan_id) else None

    return {
        "research": research,
        "idea": idea,
        "plan": plan,
        "execution": execution,
        "outputs": outputs,
        "paper": paper,
    }


@router.post("/{research_id}/run")
async def run_research_route(research_id: str, body: ResearchRunRequest, request: Request):
    session_id, session = await api_state.require_session(request)

    research = await get_research(research_id)
    if not research:
        return JSONResponse(status_code=404, content={"error": "Research not found"})

    # Avoid re-running completed researches on page revisit.
    try:
        stage = _normalize_stage(research.get("stage") or "refine")
        stage_status = (research.get("stageStatus") or "").strip().lower()
        if stage == "paper" and stage_status == "completed":
            return {"success": True, "message": "Research already completed"}
    except Exception:
        pass

    # Single pipeline per session (shared runner/run-states)
    for (sid, _rid), t in list(_RUNNING.items()):
        if sid == session_id and t and not t.done():
            return JSONResponse(status_code=409, content={"error": "Another research pipeline is already running in this session"})

    key = (session_id, research_id)

    paper_format = (body.format or "markdown").lower().strip()
    if paper_format not in ("markdown", "latex"):
        paper_format = "markdown"

    async def _pipeline():
        try:
            # Re-fetch to ensure we use latest prompt/title.
            research_live = await get_research(research_id)
            if not research_live:
                raise ValueError("Research not found")

            logger.info(
                "Research pipeline start session_id={} research_id={} stage={} prompt_chars={} format={}",
                session_id,
                research_id,
                research_live.get("stage") or "refine",
                len((research_live.get("prompt") or "").strip()),
                paper_format,
            )

            await api_state.emit_safe(session_id, "research-stage", {"researchId": research_id, "stage": "refine", "status": "running"})
            await update_research_stage(research_id, stage="refine", stage_status="running", error=None)

            prompt = (research_live.get("prompt") or "").strip()
            idea_id = f"idea_{int(time.time() * 1000)}"
            logger.info("Research pipeline refine start research_id={} idea_id={}", research_id, idea_id)
            await update_research_stage(research_id, current_idea_id=idea_id, current_plan_id=None)
            await save_idea({"idea": prompt, "keywords": [], "papers": []}, idea_id)

            # Refine
            session.idea_run_state.abort_event = asyncio.Event()
            await _run_collect_inner(
                session_id,
                session.idea_run_state,
                idea_id,
                prompt,
                limit=10,
                abort_event=session.idea_run_state.abort_event,
            )
            logger.info("Research pipeline refine complete research_id={} idea_id={}", research_id, idea_id)

            # Plan
            await api_state.emit_safe(session_id, "research-stage", {"researchId": research_id, "stage": "plan", "status": "running"})
            await update_research_stage(research_id, stage="plan", stage_status="running")
            plan_id = f"plan_{int(time.time() * 1000)}"
            logger.info("Research pipeline plan start research_id={} idea_id={} plan_id={}", research_id, idea_id, plan_id)
            await update_research_stage(research_id, current_plan_id=plan_id)
            await _run_plan_inner(PlanRunRequest(skip_quality_assessment=False), idea_id, plan_id, session_id, session.plan_run_state)

            plan = await get_plan(idea_id, plan_id)
            if not plan or not plan.get("tasks"):
                raise ValueError("Plan not found or empty after planning")
            logger.info("Research pipeline plan complete research_id={} plan_id={} tasks={}", research_id, plan_id, len(plan.get("tasks") or []))

            # Execute
            await api_state.emit_safe(session_id, "research-stage", {"researchId": research_id, "stage": "execute", "status": "running"})
            await update_research_stage(research_id, stage="execute", stage_status="running")
            execution = build_execution_from_plan(plan)
            if not execution.get("tasks"):
                raise ValueError("No atomic tasks found in current plan. Execution is blocked until Plan produces executable atomic tasks.")
            logger.info("Research pipeline execute start research_id={} plan_id={} execution_tasks={}", research_id, plan_id, len(execution.get("tasks") or []))
            await save_execution(execution, idea_id, plan_id)
            layout = build_layout_from_execution(execution)
            session.runner.set_layout(layout, idea_id=idea_id, plan_id=plan_id, execution=execution)

            config = await get_effective_config()
            await session.runner.start_execution(api_config=config)
            logger.info("Research pipeline execute complete research_id={} plan_id={}", research_id, plan_id)

            # Paper
            await api_state.emit_safe(session_id, "research-stage", {"researchId": research_id, "stage": "paper", "status": "running"})
            await update_research_stage(research_id, stage="paper", stage_status="running")
            logger.info("Research pipeline paper start research_id={} plan_id={} format={}", research_id, plan_id, paper_format)
            session.paper_run_state.abort_event = asyncio.Event()
            await _run_paper_inner(
                session_id,
                session.paper_run_state,
                idea_id,
                plan_id,
                paper_format,
                abort_event=session.paper_run_state.abort_event,
            )

            await update_research_stage(research_id, stage="paper", stage_status="completed")
            await api_state.emit_safe(session_id, "research-stage", {"researchId": research_id, "stage": "paper", "status": "completed"})
            logger.info("Research pipeline complete research_id={} idea_id={} plan_id={}", research_id, idea_id, plan_id)
        except asyncio.CancelledError:
            logger.warning("Research pipeline cancelled research_id={} session_id={}", research_id, session_id)
            await update_research_stage(research_id, stage_status="stopped", error="Research pipeline stopped by user")
            try:
                research_live = await get_research(research_id)
                stage = _normalize_stage((research_live or {}).get("stage") or "refine")
                await api_state.emit_safe(session_id, "research-stage", {"researchId": research_id, "stage": stage, "status": "stopped"})
            except Exception:
                pass
            raise
        except Exception as e:
            logger.exception("Research pipeline failed research_id={} session_id={}", research_id, session_id)
            await update_research_stage(research_id, stage_status="failed", error=str(e))
            try:
                await api_state.emit_safe(session_id, "research-stage", {"researchId": research_id, "stage": "error", "status": "failed", "error": str(e)})
            except Exception:
                pass
            try:
                await api_state.emit_safe(session_id, "research-error", {"researchId": research_id, "error": str(e)})
            except Exception:
                pass
        finally:
            logger.info("Research pipeline cleanup research_id={} session_id={}", research_id, session_id)
            _RUNNING.pop(key, None)

    task = asyncio.create_task(_pipeline())
    _RUNNING[key] = task
    return {"success": True, "researchId": research_id, "sessionId": session_id}


@router.post("/{research_id}/stop")
async def stop_research_route(research_id: str, request: Request):
    """Stop current research pipeline run in this session (pause).

    Semantics: cancel the pipeline task + set abort signals so downstream agents return quickly.
    """

    session_id, session = await api_state.require_session(request)

    research = await get_research(research_id)
    if not research:
        return JSONResponse(status_code=404, content={"error": "Research not found"})

    key = (session_id, research_id)
    task = _RUNNING.get(key)

    # Best-effort abort signals for individual stage runners.
    try:
        if getattr(session.idea_run_state, "abort_event", None):
            session.idea_run_state.abort_event.set()
    except Exception:
        pass
    try:
        if getattr(session.plan_run_state, "abort_event", None):
            session.plan_run_state.abort_event.set()
    except Exception:
        pass
    try:
        await session.runner.stop_async()
    except Exception:
        pass
    try:
        if getattr(session.paper_run_state, "abort_event", None):
            session.paper_run_state.abort_event.set()
    except Exception:
        pass

    if task and not task.done():
        task.cancel()
        await update_research_stage(research_id, stage_status="stopped", error=None)
        try:
            stage = _normalize_stage(research.get("stage") or "refine")
            await api_state.emit_safe(session_id, "research-stage", {"researchId": research_id, "stage": stage, "status": "stopped"})
        except Exception:
            pass
        return {"success": True, "researchId": research_id, "sessionId": session_id, "stopped": True}

    return {"success": True, "researchId": research_id, "sessionId": session_id, "stopped": False, "message": "No running pipeline"}


@router.post("/{research_id}/retry")
async def retry_research_route(research_id: str, body: ResearchRunRequest, request: Request):
    """Retry research pipeline starting from the current stage, using existing upstream artifacts."""

    session_id, session = await api_state.require_session(request)

    research = await get_research(research_id)
    if not research:
        return JSONResponse(status_code=404, content={"error": "Research not found"})

    # Single pipeline per session
    for (sid, _rid), t in list(_RUNNING.items()):
        if sid == session_id and t and not t.done():
            return JSONResponse(status_code=409, content={"error": "Another research pipeline is already running in this session"})

    paper_format = (body.format or "markdown").lower().strip()
    if paper_format not in ("markdown", "latex"):
        paper_format = "markdown"

    start_stage = _normalize_stage(research.get("stage") or "refine")
    key = (session_id, research_id)

    async def _pipeline_retry():
        try:
            research_live = await get_research(research_id)
            if not research_live:
                raise ValueError("Research not found")

            prompt = (research_live.get("prompt") or "").strip()
            idea_id = (research_live.get("currentIdeaId") or "").strip() or None
            plan_id = (research_live.get("currentPlanId") or "").strip() or None

            # If retry starts from refine, downstream ids must be reset.
            if _stage_rank(start_stage) <= _stage_rank("refine"):
                await api_state.emit_safe(session_id, "research-stage", {"researchId": research_id, "stage": "refine", "status": "running"})
                await update_research_stage(research_id, stage="refine", stage_status="running", error=None)
                if not idea_id:
                    idea_id = f"idea_{int(time.time() * 1000)}"
                await update_research_stage(research_id, current_idea_id=idea_id, current_plan_id=None)
                plan_id = None
                await save_idea({"idea": prompt, "keywords": [], "papers": []}, idea_id)

                session.idea_run_state.abort_event = asyncio.Event()
                await _run_collect_inner(
                    session_id,
                    session.idea_run_state,
                    idea_id,
                    prompt,
                    limit=10,
                    abort_event=session.idea_run_state.abort_event,
                )

            # Plan
            if _stage_rank(start_stage) <= _stage_rank("plan"):
                if not idea_id:
                    raise ValueError("Idea not found. Please Refine first to create an idea.")
                await api_state.emit_safe(session_id, "research-stage", {"researchId": research_id, "stage": "plan", "status": "running"})
                await update_research_stage(research_id, stage="plan", stage_status="running", error=None)
                if not plan_id:
                    plan_id = f"plan_{int(time.time() * 1000)}"
                    await update_research_stage(research_id, current_plan_id=plan_id)
                await _run_plan_inner(PlanRunRequest(skip_quality_assessment=False), idea_id, plan_id, session_id, session.plan_run_state)

            plan = await get_plan(idea_id, plan_id) if (idea_id and plan_id) else None
            if not plan or not plan.get("tasks"):
                raise ValueError("Plan not found or empty after planning")

            # Execute
            if _stage_rank(start_stage) <= _stage_rank("execute"):
                await api_state.emit_safe(session_id, "research-stage", {"researchId": research_id, "stage": "execute", "status": "running"})
                await update_research_stage(research_id, stage="execute", stage_status="running", error=None)
                execution = build_execution_from_plan(plan)
                if not execution.get("tasks"):
                    raise ValueError("No atomic tasks found in current plan. Execution is blocked until Plan produces executable atomic tasks.")
                await save_execution(execution, idea_id, plan_id)
                layout = build_layout_from_execution(execution)
                session.runner.set_layout(layout, idea_id=idea_id, plan_id=plan_id, execution=execution)
                config = await get_effective_config()
                await session.runner.start_execution(api_config=config)

            # Paper
            await api_state.emit_safe(session_id, "research-stage", {"researchId": research_id, "stage": "paper", "status": "running"})
            await update_research_stage(research_id, stage="paper", stage_status="running", error=None)
            session.paper_run_state.abort_event = asyncio.Event()
            await _run_paper_inner(
                session_id,
                session.paper_run_state,
                idea_id,
                plan_id,
                paper_format,
                abort_event=session.paper_run_state.abort_event,
            )

            await update_research_stage(research_id, stage="paper", stage_status="completed")
            await api_state.emit_safe(session_id, "research-stage", {"researchId": research_id, "stage": "paper", "status": "completed"})
        except asyncio.CancelledError:
            await update_research_stage(research_id, stage_status="stopped", error="Research pipeline stopped by user")
            raise
        except Exception as e:
            logger.exception("Research retry pipeline failed")
            await update_research_stage(research_id, stage_status="failed", error=str(e))
            try:
                await api_state.emit_safe(session_id, "research-error", {"researchId": research_id, "error": str(e)})
            except Exception:
                pass
        finally:
            _RUNNING.pop(key, None)

    task = asyncio.create_task(_pipeline_retry())
    _RUNNING[key] = task
    return {"success": True, "researchId": research_id, "sessionId": session_id, "mode": "retry", "startStage": start_stage}
