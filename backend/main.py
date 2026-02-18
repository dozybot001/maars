"""
MAARS Backend - FastAPI + Socket.io entry point.
Python implementation of the planner backend.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

import socketio
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from db import (
    get_execution,
    get_idea,
    get_plan,
    get_verification,
    save_execution,
    save_plan,
    save_verification,
)
from monitor import build_execution_from_plan, build_layout_from_execution
from planner.index import run_plan
from tasks import task_cache
from workers import ExecutorRunner, executor_manager, verifier_manager

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

logger = logging.getLogger(__name__)


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


# Pydantic request models
class ApiConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    base_url: Optional[str] = Field(None, alias="baseUrl")
    api_key: Optional[str] = Field(None, alias="apiKey")
    model: Optional[str] = None


class PlanRunRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    idea: Optional[str] = None
    plan_id: str = Field(default="test", alias="planId")
    use_mock: bool = Field(default=False, alias="useMock")
    api_config: Optional[ApiConfig] = Field(None, alias="apiConfig")


class MonitorTimetableRequest(BaseModel):
    execution: dict = Field(..., description="Execution data with tasks")


class TaskIdRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    task_id: str = Field(..., alias="taskId")


class ExecutionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    plan_id: str = Field(default="test", alias="planId")


class VerificationRequest(BaseModel):
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
        use_mock = body.use_mock
        api_config = body.api_config.model_dump(by_alias=True, exclude_none=True) if body.api_config else {}

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

        result = await run_plan(plan, None, on_thinking, abort_event, on_tasks_batch, use_mock=use_mock, api_config=api_config)
        plan["tasks"] = task_cache.build_tree_data(result["tasks"])
        await save_plan(plan, plan_id)
        await sio.emit("plan-complete", {"treeData": plan["tasks"], "planId": plan_id})

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
    try:
        execution = body.execution
        layout = build_layout_from_execution(execution)
        executor_runner.set_timetable_layout_cache(layout)
        return {"layout": layout}
    except Exception as e:
        logger.exception("Monitor timetable error")
        return JSONResponse(status_code=500, content={"error": str(e) or "Failed to generate timetable layout"})


@app.get("/api/plan")
async def api_get_plan(plan_id: str = Query("test", alias="planId")):
    try:
        plan = await get_plan(plan_id)
        return {"plan": plan}
    except Exception as e:
        logger.exception("Error loading plan")
        return JSONResponse(status_code=500, content={"error": str(e) or "Failed to load plan"})


@app.get("/api/plan/tree")
async def api_get_plan_tree(plan_id: str = Query("test", alias="planId")):
    try:
        plan = await get_plan(plan_id)
        if not plan or not plan.get("tasks") or len(plan["tasks"]) == 0:
            return {"treeData": []}
        tasks = task_cache.build_tree_data(plan["tasks"])
        return {"treeData": tasks}
    except Exception as e:
        logger.exception("Error loading plan tree")
        return JSONResponse(status_code=500, content={"error": str(e) or "Failed to load plan tree"})


DEFAULT_EXAMPLE_IDEA = "Research and analyze the latest trends in AI technology"


@app.get("/api/idea")
async def api_get_idea(plan_id: str = Query("test", alias="planId")):
    try:
        idea = await get_idea(plan_id)
        return {"idea": idea or DEFAULT_EXAMPLE_IDEA}
    except Exception as e:
        logger.exception("Error loading idea")
        return JSONResponse(status_code=500, content={"error": "Failed to load idea"})


@app.post("/api/execution/generate-from-plan")
async def api_generate_execution_from_plan(body: ExecutionRequest):
    """Extract atomic tasks from plan, clean deps, recompute stages, save to execution.json."""
    try:
        plan_id = body.plan_id
        plan = await get_plan(plan_id)
        if not plan or not plan.get("tasks"):
            return JSONResponse(status_code=400, content={"error": "No plan found. Generate plan first."})
        execution = build_execution_from_plan(plan)
        await save_execution(execution, plan_id)
        return {"execution": execution}
    except Exception as e:
        logger.exception("Error generating execution from plan")
        return JSONResponse(status_code=500, content={"error": str(e) or "Failed to generate execution"})


@app.get("/api/execution")
async def api_get_execution(plan_id: str = Query("test", alias="planId")):
    try:
        execution = await get_execution(plan_id)
        return {"execution": execution}
    except Exception as e:
        logger.exception("Error loading execution")
        return JSONResponse(status_code=500, content={"error": "Failed to load execution"})


@app.post("/api/execution")
async def api_post_execution(body: ExecutionRequest):
    try:
        plan_id = body.plan_id
        payload = body.model_dump(exclude={"plan_id"})
        result = await save_execution(payload, plan_id)
        return result
    except Exception as e:
        logger.exception("Error saving execution")
        return JSONResponse(status_code=500, content={"error": str(e) or "Failed to save execution"})


@app.get("/api/verification")
async def api_get_verification(plan_id: str = Query("test", alias="planId")):
    try:
        verification = await get_verification(plan_id)
        return {"verification": verification}
    except Exception as e:
        logger.exception("Error loading verification")
        return JSONResponse(status_code=500, content={"error": "Failed to load verification"})


@app.post("/api/verification")
async def api_post_verification(body: VerificationRequest):
    try:
        plan_id = body.plan_id
        payload = body.model_dump(exclude={"plan_id"})
        result = await save_verification(payload, plan_id)
        return result
    except Exception as e:
        logger.exception("Error saving verification")
        return JSONResponse(status_code=500, content={"error": str(e) or "Failed to save verification"})


@app.get("/api/executors")
async def api_get_executors():
    try:
        stats = executor_manager["get_executor_stats"]()
        executors = executor_manager["get_all_executors"]()
        return {"executors": executors, "stats": stats}
    except Exception as e:
        logger.exception("Error getting executors")
        return JSONResponse(status_code=500, content={"error": "Failed to get executor states"})


@app.post("/api/executors/assign")
async def api_executors_assign(body: TaskIdRequest):
    try:
        task_id = body.task_id
        executor_id = executor_manager["assign_task"](task_id)
        if executor_id is None:
            return JSONResponse(status_code=503, content={"error": "No idle executor available"})
        return {"executorId": executor_id, "taskId": task_id}
    except Exception as e:
        logger.exception("Error assigning executor")
        return JSONResponse(status_code=500, content={"error": "Failed to assign executor"})


@app.post("/api/executors/release")
async def api_executors_release(body: TaskIdRequest):
    try:
        task_id = body.task_id
        executor_id = executor_manager["release_executor_by_task_id"](task_id)
        return {
            "success": True,
            "executorId": executor_id if executor_id is not None else None,
            "taskId": task_id,
            "message": "Executor released successfully" if executor_id else "No executor was assigned to this task",
        }
    except Exception as e:
        logger.exception("Error releasing executor")
        return JSONResponse(status_code=500, content={"error": "Failed to release executor: " + str(e)})


@app.post("/api/executors/reset")
async def api_executors_reset():
    try:
        executor_manager["initialize_executors"]()
        executors = executor_manager["get_all_executors"]()
        stats = executor_manager["get_executor_stats"]()
        return {"success": True, "executors": executors, "stats": stats}
    except Exception as e:
        logger.exception("Error resetting executors")
        return JSONResponse(status_code=500, content={"error": "Failed to reset executors"})


@app.get("/api/verifiers")
async def api_get_verifiers():
    try:
        stats = verifier_manager["get_verifier_stats"]()
        verifiers = verifier_manager["get_all_verifiers"]()
        return {"verifiers": verifiers, "stats": stats}
    except Exception as e:
        logger.exception("Error getting verifiers")
        return JSONResponse(status_code=500, content={"error": "Failed to get verifier states"})


@app.post("/api/verifiers/assign")
async def api_verifiers_assign(body: TaskIdRequest):
    try:
        task_id = body.task_id
        verifier_id = verifier_manager["assign_task"](task_id)
        if verifier_id is None:
            return JSONResponse(status_code=503, content={"error": "No idle verifier available"})
        return {"verifierId": verifier_id, "taskId": task_id}
    except Exception as e:
        logger.exception("Error assigning verifier")
        return JSONResponse(status_code=500, content={"error": "Failed to assign verifier"})


@app.post("/api/verifiers/release")
async def api_verifiers_release(body: TaskIdRequest):
    try:
        task_id = body.task_id
        verifier_id = verifier_manager["release_verifier_by_task_id"](task_id)
        return {
            "success": True,
            "verifierId": verifier_id if verifier_id is not None else None,
            "taskId": task_id,
            "message": "Verifier released successfully" if verifier_id else "No verifier was assigned to this task",
        }
    except Exception as e:
        logger.exception("Error releasing verifier")
        return JSONResponse(status_code=500, content={"error": "Failed to release verifier: " + str(e)})


@app.post("/api/verifiers/reset")
async def api_verifiers_reset():
    try:
        verifier_manager["initialize_verifiers"]()
        verifiers = verifier_manager["get_all_verifiers"]()
        stats = verifier_manager["get_verifier_stats"]()
        return {"success": True, "verifiers": verifiers, "stats": stats}
    except Exception as e:
        logger.exception("Error resetting verifiers")
        return JSONResponse(status_code=500, content={"error": "Failed to reset verifiers"})


@app.post("/api/mock-execution")
async def api_mock_execution():
    try:
        async def run():
            try:
                await executor_runner.start_mock_execution()
            except Exception as e:
                logger.exception("Error in background execution")
                await sio.emit("execution-error", {"error": str(e)})

        asyncio.create_task(run())
        return {"success": True, "message": "Mock execution started"}
    except Exception as e:
        logger.exception("Error starting mock execution")
        return JSONResponse(status_code=500, content={"error": str(e) or "Failed to start mock execution"})


@app.post("/api/mock-execution/stop")
async def api_mock_execution_stop():
    try:
        await executor_runner.stop_async()
        return {"success": True, "message": "Mock execution stopped"}
    except Exception as e:
        logger.exception("Error stopping mock execution")
        return JSONResponse(status_code=500, content={"error": str(e) or "Failed to stop mock execution"})


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
    verifiers = verifier_manager["get_all_verifiers"]()
    verifier_stats = verifier_manager["get_verifier_stats"]()
    await sio.emit("verifier-states-update", {"verifiers": verifiers, "stats": verifier_stats}, to=sid)


@sio.event
def disconnect(sid):
    logger.info("Client disconnected: %s", sid)


# ASGI app for uvicorn (Socket.io + FastAPI)
asgi_app = socketio.ASGIApp(sio, app)
