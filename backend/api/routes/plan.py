"""Plan Agent API - 任务分解（Plan）。HTTP 仅触发，数据由 WebSocket 回传。"""

import time

from fastapi import APIRouter, Query, Request
from loguru import logger
from fastapi.responses import JSONResponse

from db import (
    DEFAULT_IDEA_ID,
    get_effective_config,
    get_idea,
    get_plan,
    list_plan_outputs,
    save_plan,
)
from shared.utils import get_idea_text
from shared.task_title import derive_task_title, ensure_task_titles
from visualization import build_layout_from_execution, compute_decomposition_layout
from mode import run_plan
from shared.realtime import build_thinking_emitter

from ..schemas import PlanLayoutRequest, PlanRunRequest
from .. import state as api_state
from ..run_state_ops import guarded_agent_run, start_agent_task

router = APIRouter()


def _tree_update_payload(plan):
    """Build treeData + layout payload for plan-tree-update / plan-complete."""
    return {"treeData": plan["tasks"], "layout": compute_decomposition_layout(plan["tasks"])}


@router.post("/layout")
async def set_plan_layout(body: PlanLayoutRequest, request: Request):
    """设置 Task Agent Execution 阶段的可视化布局（execution graph）。"""
    _, session = await api_state.require_session(request)
    execution = body.execution
    idea_id = body.idea_id or DEFAULT_IDEA_ID
    plan_id = body.plan_id
    layout = build_layout_from_execution(execution)
    try:
        session.runner.set_layout(layout, idea_id=idea_id, plan_id=plan_id, execution=execution)
    except ValueError as e:
        return JSONResponse(status_code=409, content={"error": str(e)})
    return {"layout": layout}


@router.get("")
async def get_plan_route(idea_id: str = Query("test", alias="ideaId"), plan_id: str = Query("test", alias="planId")):
    plan = await get_plan(idea_id, plan_id)
    return {"plan": plan}


@router.get("/outputs")
async def get_plan_outputs(idea_id: str = Query("test", alias="ideaId"), plan_id: str = Query("test", alias="planId")):
    """Load all task outputs for a plan."""
    outputs = await list_plan_outputs(idea_id, plan_id)
    return {"outputs": outputs}


@router.get("/tree")
async def get_plan_tree(idea_id: str = Query("test", alias="ideaId"), plan_id: str = Query("test", alias="planId")):
    plan = await get_plan(idea_id, plan_id)
    if not plan or not plan.get("tasks") or len(plan["tasks"]) == 0:
        return {"treeData": [], "layout": None}
    return _tree_update_payload(plan)


@router.post("/stop")
async def stop_plan(request: Request):
    """停止 Plan Agent。"""
    session_id, session = await api_state.require_session(request)
    await api_state.stop_run_state(
        session_id, session.plan_run_state,
        error_event="plan-error", error_message="Plan Agent stopped by user",
        emit_when_idle=True,
    )
    return {"success": True}


async def _run_plan_inner(body: PlanRunRequest, idea_id: str, plan_id: str, session_id: str, state):
    """后台执行 plan 生成，通过 WebSocket 回传数据。"""

    idea_data = await get_idea(idea_id)
    if not idea_data or not idea_data.get("idea"):
        raise ValueError("Idea not found. Please Refine first to create an idea.")
    refined = idea_data.get("refined_idea")
    idea = get_idea_text(refined)
    if not idea:
        raise ValueError("Refine result is empty. Planning is blocked until Refine produces a non-empty refined idea.")

    config = await get_effective_config()

    plan = {
        "tasks": [{"task_id": "0", "title": derive_task_title(idea) or "Research Goal", "description": idea, "dependencies": []}],
        "idea": idea,
    }
    ensure_task_titles(plan["tasks"])
    await save_plan(plan, idea_id, plan_id)

    async def _run_agent(abort_event):
        if plan["tasks"]:
            await api_state.emit(session_id, "plan-tree-update", _tree_update_payload(plan))

        def on_tasks_batch(children, parent_task, all_tasks):
            if abort_event and abort_event.is_set():
                return
            ensure_task_titles(all_tasks)
            plan["tasks"] = all_tasks
            if plan["tasks"]:
                api_state.emit_background(session_id, "plan-tree-update", _tree_update_payload(plan))

        _on_thinking_emit = build_thinking_emitter(
            api_state.sio, event_name="plan-thinking", source="plan",
            default_operation="Decompose", room=session_id, warning_label="plan-thinking",
        )

        async def on_thinking(chunk, task_id=None, operation=None, schedule_info=None):
            if abort_event and abort_event.is_set():
                return
            await _on_thinking_emit(chunk, task_id, operation, schedule_info)

        result = await run_plan(
            plan, None, on_thinking, abort_event, on_tasks_batch,
            api_config=config,
            skip_quality_assessment=body.skip_quality_assessment,
            idea_id=idea_id, plan_id=plan_id,
        )
        plan["tasks"] = result["tasks"]
        ensure_task_titles(plan["tasks"])
        return {"tasks": plan["tasks"]}

    async def _on_complete(result):
        plan_to_save = {"tasks": plan["tasks"], "qualityScore": plan.get("qualityScore"), "qualityComment": plan.get("qualityComment")}
        await save_plan(plan_to_save, idea_id, plan_id)

        await api_state.emit(session_id, "plan-complete", {
            **_tree_update_payload(plan),
            "ideaId": idea_id, "planId": plan_id,
            "qualityScore": plan.get("qualityScore"), "qualityComment": plan.get("qualityComment"),
        })

    await guarded_agent_run(
        state, session_id, "Plan", _run_agent,
        emit_fn=api_state.emit, emit_safe_fn=api_state.emit_safe,
        start_event="plan-start", error_event="plan-error",
        complete_callback=_on_complete,
    )


@router.post("/run")
async def run_plan_route(body: PlanRunRequest, request: Request):
    """立即返回，数据由 WebSocket plan-complete 回传。"""
    session_id, session = await api_state.require_session(request)
    state = session.plan_run_state
    if state.run_task and not state.run_task.done():
        return JSONResponse(status_code=409, content={"error": "Plan run already in progress"})

    idea_id = (body.idea_id or "").strip() or None
    if not idea_id or idea_id == DEFAULT_IDEA_ID or not idea_id.startswith("idea_"):
        return JSONResponse(status_code=400, content={"error": "Please Refine first to create an idea. Idea ID is required for plan generation."})

    idea_data = await get_idea(idea_id)
    if not idea_data or not idea_data.get("idea"):
        return JSONResponse(status_code=400, content={"error": "Idea not found. Please Refine first to create an idea."})
    if not get_idea_text(idea_data.get("refined_idea")):
        return JSONResponse(status_code=400, content={"error": "Refine result is empty. Planning is blocked until Refine produces a non-empty refined idea."})

    plan_id = f"plan_{int(time.time() * 1000)}"
    start_agent_task(state, _run_plan_inner(body, idea_id, plan_id, session_id, state))

    return {"success": True, "ideaId": idea_id, "planId": plan_id, "sessionId": session_id}
