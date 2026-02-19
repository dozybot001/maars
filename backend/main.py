"""
MAARS Backend - FastAPI + Socket.io entry point.
Python implementation of the planner backend.
"""

import asyncio
from pathlib import Path
from typing import Optional

import socketio
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Body, FastAPI, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from db import (
    get_api_config,
    get_execution,
    get_idea,
    get_plan,
    get_validation,
    list_plan_ids,
    save_api_config,
    save_execution,
    save_plan,
    save_validation,
)
from monitor import build_execution_from_plan, build_layout_from_execution
from planner.index import run_plan
from tasks import task_cache
from workers import ExecutorRunner, executor_manager, validator_manager

# Socket.io
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = FastAPI(title="MAARS Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Plan run abort: per-run isolation (new run aborts previous)
_plan_run_abort_event: Optional[asyncio.Event] = None
_plan_run_lock = asyncio.Lock()

# Executor runner instance
executor_runner = ExecutorRunner(sio)


# Disable cache for static files (dev: always fetch latest)
NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}


class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path == "/" or path.endswith((".html", ".css", ".js")):
            for k, v in NO_CACHE_HEADERS.items():
                response.headers[k] = v
        return response


app.add_middleware(NoCacheMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Centralized exception handler for unhandled errors."""
    logger.exception("Unhandled exception: {}", exc)
    return JSONResponse(
        status_code=500,
        content={"error": str(exc) or "Internal server error"},
    )


# Pydantic request models
class ApiConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    base_url: Optional[str] = Field(None, alias="baseUrl")
    api_key: Optional[str] = Field(None, alias="apiKey")
    model: Optional[str] = None
    use_mock: Optional[bool] = Field(None, alias="useMock")
    phases: Optional[dict] = None  # { atomicity, decompose, format, execute, validate } -> { baseUrl?, apiKey?, model? }


class PlanRunRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    idea: Optional[str] = None
    plan_id: str = Field(default="test", alias="planId")
    skip_quality_assessment: bool = Field(default=False, alias="skipQualityAssessment")


class MonitorTimetableRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    execution: dict = Field(..., description="Execution data with tasks")
    plan_id: str = Field(default="test", alias="planId")


class TaskIdRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    task_id: str = Field(..., alias="taskId")


class ExecutionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    plan_id: str = Field(default="test", alias="planId")


class ValidationRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    plan_id: str = Field(default="test", alias="planId")


# Frontend static files
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


# ========== API ROUTES (must come before static file serving) ==========


@app.post("/api/plan/stop")
async def api_plan_stop():
    global _plan_run_abort_event
    if _plan_run_abort_event:
        _plan_run_abort_event.set()
    return {"success": True}


@app.post("/api/plan/run")
async def api_plan_run(body: PlanRunRequest):
    global _plan_run_abort_event
    async with _plan_run_lock:
        if _plan_run_abort_event:
            _plan_run_abort_event.set()
        _plan_run_abort_event = asyncio.Event()
        _plan_run_abort_event.clear()
        abort_event = _plan_run_abort_event

    try:
        idea = body.idea
        api_config = await get_api_config()
        use_mock = api_config.get("useMock", api_config.get("use_mock", True))

        # New idea => create new plan_id folder; decompose => use existing
        if idea is not None and isinstance(idea, str) and idea.strip():
            import time as _time
            plan_id = f"plan_{int(_time.time() * 1000)}"
        else:
            plan_id = body.plan_id

        plan = await get_plan(plan_id) or {}
        if idea is not None and isinstance(idea, str) and idea.strip():
            task0 = {"task_id": "0", "description": idea.strip(), "dependencies": []}
            plan["tasks"] = [task0]
            plan["idea"] = idea.strip()
            await save_plan(plan, plan_id)

        if not plan.get("tasks") or len(plan["tasks"]) == 0:
            return JSONResponse(
                status_code=400,
                content={"error": "No plan found. Provide idea or generate plan first."},
            )

        await sio.emit("plan-start")

        plan["tasks"] = task_cache.build_tree_data(plan["tasks"])
        if plan["tasks"]:
            await sio.emit("plan-tree-update", {"treeData": plan["tasks"]})

        def on_tasks_batch(children, parent_task, all_tasks):
            plan["tasks"] = task_cache.build_tree_data(all_tasks)
            if plan["tasks"]:
                asyncio.create_task(sio.emit("plan-tree-update", {"treeData": plan["tasks"]}))

        def on_thinking(chunk, task_id=None, operation=None):
            payload = {"chunk": chunk}
            if task_id is not None:
                payload["taskId"] = task_id
            if operation is not None:
                payload["operation"] = operation
            asyncio.create_task(sio.emit("plan-thinking", payload))

        result = await run_plan(
            plan, None, on_thinking, abort_event, on_tasks_batch,
            use_mock=use_mock, api_config=api_config,
            skip_quality_assessment=body.skip_quality_assessment,
        )
        plan["tasks"] = task_cache.build_tree_data(result["tasks"])
        await save_plan(plan, plan_id)
        await sio.emit("plan-complete", {
            "treeData": plan["tasks"],
            "planId": plan_id,
            "qualityScore": plan.get("qualityScore"),
            "qualityComment": plan.get("qualityComment"),
        })

        return {"success": True, "planId": plan_id}

    except asyncio.CancelledError:
        await sio.emit("plan-error", {"error": "Plan generation stopped by user"})
        return JSONResponse(status_code=499, content={"error": "Plan generation stopped by user"})
    except Exception as e:
        is_aborted = "Aborted" in str(e) or (e.__class__.__name__ == "CancelledError")
        err_msg = str(e)
        logger.warning("Plan run error: %s", err_msg)
        await sio.emit("plan-error", {"error": "Plan generation stopped by user" if is_aborted else err_msg})
        if "No decomposable task" in err_msg or "Provide idea" in err_msg:
            return JSONResponse(status_code=400, content={"error": err_msg})
        return JSONResponse(status_code=500, content={"error": err_msg or "Failed to run plan"})
    finally:
        async with _plan_run_lock:
            if _plan_run_abort_event is abort_event:
                _plan_run_abort_event = None


@app.post("/api/monitor/timetable")
async def api_monitor_timetable(body: MonitorTimetableRequest):
    execution = body.execution
    plan_id = body.plan_id
    layout = build_layout_from_execution(execution)
    executor_runner.set_layout(layout, plan_id=plan_id, execution=execution)
    return {"layout": layout}


@app.get("/api/plans")
async def api_list_plans():
    """List plan IDs (newest first). Used when localStorage has no plan to restore latest."""
    ids = await list_plan_ids()
    return {"planIds": ids}


@app.get("/api/plan")
async def api_get_plan(plan_id: str = Query("test", alias="planId")):
    plan = await get_plan(plan_id)
    return {"plan": plan}


@app.get("/api/plan/tree")
async def api_get_plan_tree(plan_id: str = Query("test", alias="planId")):
    plan = await get_plan(plan_id)
    if not plan or not plan.get("tasks") or len(plan["tasks"]) == 0:
        return {"treeData": []}
    tasks = task_cache.build_tree_data(plan["tasks"])
    return {"treeData": tasks}


DEFAULT_EXAMPLE_IDEA = "Research and analyze the latest trends in AI technology"


@app.get("/api/idea")
async def api_get_idea(plan_id: str = Query("test", alias="planId")):
    idea = await get_idea(plan_id)
    return {"idea": idea or DEFAULT_EXAMPLE_IDEA}


@app.post("/api/execution/generate-from-plan")
async def api_generate_execution_from_plan(body: ExecutionRequest):
    """Extract atomic tasks from plan, clean deps, recompute stages, save to execution.json."""
    plan_id = body.plan_id
    plan = await get_plan(plan_id)
    if not plan or not plan.get("tasks"):
        return JSONResponse(status_code=400, content={"error": "No plan found. Generate plan first."})
    execution = build_execution_from_plan(plan)
    await save_execution(execution, plan_id)
    return {"execution": execution}


@app.get("/api/execution")
async def api_get_execution(plan_id: str = Query("test", alias="planId")):
    execution = await get_execution(plan_id)
    return {"execution": execution}


@app.post("/api/execution")
async def api_post_execution(body: ExecutionRequest):
    plan_id = body.plan_id
    payload = body.model_dump(exclude={"plan_id"})
    result = await save_execution(payload, plan_id)
    return result


@app.get("/api/validation")
async def api_get_validation(plan_id: str = Query("test", alias="planId")):
    validation = await get_validation(plan_id)
    return {"validation": validation}


@app.post("/api/validation")
async def api_post_validation(body: ValidationRequest):
    plan_id = body.plan_id
    payload = body.model_dump(exclude={"plan_id"})
    result = await save_validation(payload, plan_id)
    return result


@app.get("/api/executors")
async def api_get_executors():
    stats = executor_manager["get_executor_stats"]()
    executors = executor_manager["get_all_executors"]()
    return {"executors": executors, "stats": stats}


@app.post("/api/executors/assign")
async def api_executors_assign(body: TaskIdRequest):
    task_id = body.task_id
    executor_id = executor_manager["assign_task"](task_id)
    if executor_id is None:
        return JSONResponse(status_code=503, content={"error": "No idle executor available"})
    return {"executorId": executor_id, "taskId": task_id}


@app.post("/api/executors/release")
async def api_executors_release(body: TaskIdRequest):
    task_id = body.task_id
    executor_id = executor_manager["release_executor_by_task_id"](task_id)
    return {
        "success": True,
        "executorId": executor_id if executor_id is not None else None,
        "taskId": task_id,
        "message": "Executor released successfully" if executor_id else "No executor was assigned to this task",
    }


@app.post("/api/executors/reset")
async def api_executors_reset():
    executor_manager["initialize_executors"]()
    executors = executor_manager["get_all_executors"]()
    stats = executor_manager["get_executor_stats"]()
    return {"success": True, "executors": executors, "stats": stats}


@app.get("/api/validators")
async def api_get_validators():
    stats = validator_manager["get_validator_stats"]()
    validators = validator_manager["get_all_validators"]()
    return {"validators": validators, "stats": stats}


@app.post("/api/validators/assign")
async def api_validators_assign(body: TaskIdRequest):
    task_id = body.task_id
    validator_id = validator_manager["assign_task"](task_id)
    if validator_id is None:
        return JSONResponse(status_code=503, content={"error": "No idle validator available"})
    return {"validatorId": validator_id, "taskId": task_id}


@app.post("/api/validators/release")
async def api_validators_release(body: TaskIdRequest):
    task_id = body.task_id
    validator_id = validator_manager["release_validator_by_task_id"](task_id)
    return {
        "success": True,
        "validatorId": validator_id if validator_id is not None else None,
        "taskId": task_id,
        "message": "Validator released successfully" if validator_id else "No validator was assigned to this task",
    }


@app.post("/api/validators/reset")
async def api_validators_reset():
    validator_manager["initialize_validators"]()
    validators = validator_manager["get_all_validators"]()
    stats = validator_manager["get_validator_stats"]()
    return {"success": True, "validators": validators, "stats": stats}


@app.get("/api/config")
async def api_get_config():
    """Get API config from db."""
    config = await get_api_config()
    return {"config": config}


@app.post("/api/config")
async def api_save_config(body: ApiConfig = Body(...)):
    """Save API config to db."""
    config = body.model_dump(by_alias=True, exclude_none=True)
    await save_api_config(config)
    return {"success": True}


@app.post("/api/execution/run")
async def api_execution_run():
    api_config = await get_api_config()

    async def run():
        try:
            await executor_runner.start_execution(api_config=api_config)
        except Exception as e:
            logger.exception("Error in execution: {}", e)
            await sio.emit("execution-error", {"error": str(e)})

    asyncio.create_task(run())
    return {"success": True, "message": "Execution started"}


@app.post("/api/execution/stop")
async def api_execution_stop():
    await executor_runner.stop_async()
    return {"success": True, "message": "Execution stopped"}


# Static file serving - MUST come after all API routes
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")


# Socket.io events
@sio.event
async def connect(sid, environ, auth):
    logger.info("Client connected: %s", sid)
    executors = executor_manager["get_all_executors"]()
    executor_stats = executor_manager["get_executor_stats"]()
    await sio.emit("executor-states-update", {"executors": executors, "stats": executor_stats}, to=sid)
    validators = validator_manager["get_all_validators"]()
    validator_stats = validator_manager["get_validator_stats"]()
    await sio.emit("validator-states-update", {"validators": validators, "stats": validator_stats}, to=sid)


@sio.event
def disconnect(sid):
    logger.info("Client disconnected: %s", sid)


# ASGI app for uvicorn (Socket.io + FastAPI)
asgi_app = socketio.ASGIApp(sio, app)
