"""Execution API routes."""

import asyncio

from fastapi import APIRouter, Query
from loguru import logger
from fastapi.responses import JSONResponse

from db import get_effective_api_config, get_execution, get_plan, save_execution
from planner.visualization import build_execution_from_plan

from .. import state as api_state
from ..schemas import ExecutionRequest

router = APIRouter()


@router.post("/generate-from-plan")
async def generate_from_plan(body: ExecutionRequest):
    """Extract atomic tasks from plan, resolve deps, save to execution.json."""
    plan_id = body.plan_id
    plan = await get_plan(plan_id)
    if not plan or not plan.get("tasks"):
        return JSONResponse(status_code=400, content={"error": "No plan found. Generate plan first."})
    execution = build_execution_from_plan(plan)
    await save_execution(execution, plan_id)
    return {"execution": execution}


@router.get("")
async def get_execution_route(plan_id: str = Query("test", alias="planId")):
    execution = await get_execution(plan_id)
    return {"execution": execution}


@router.post("")
async def post_execution(body: ExecutionRequest):
    plan_id = body.plan_id
    payload = body.model_dump(exclude={"plan_id"})
    result = await save_execution(payload, plan_id)
    return result


@router.post("/run")
async def run_execution():
    """Start execution. Returns immediately; errors are pushed via WebSocket execution-error."""
    api_config = await get_effective_api_config()
    runner = api_state.executor_runner
    sio = api_state.sio

    async def run():
        try:
            await runner.start_execution(api_config=api_config)
        except Exception as e:
            logger.exception("Error in execution: {}", e)
            await sio.emit("execution-error", {"error": str(e)})

    asyncio.create_task(run())
    return {"success": True, "message": "Execution started"}


@router.post("/stop")
async def stop_execution():
    await api_state.executor_runner.stop_async()
    return {"success": True, "message": "Execution stopped"}
