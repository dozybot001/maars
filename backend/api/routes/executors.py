"""Executors API."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from executor import executor_manager

from ..schemas import TaskIdRequest

router = APIRouter()


@router.get("/executors")
async def get_executors():
    stats = executor_manager["get_executor_stats"]()
    executors = executor_manager["get_all_executors"]()
    return {"executors": executors, "stats": stats}


@router.post("/executors/assign")
async def assign_executor(body: TaskIdRequest):
    task_id = body.task_id
    executor_id = executor_manager["assign_task"](task_id)
    if executor_id is None:
        return JSONResponse(status_code=503, content={"error": "No idle executor available"})
    return {"executorId": executor_id, "taskId": task_id}


@router.post("/executors/release")
async def release_executor(body: TaskIdRequest):
    task_id = body.task_id
    executor_id = executor_manager["release_executor_by_task_id"](task_id)
    return {
        "success": True,
        "executorId": executor_id if executor_id is not None else None,
        "taskId": task_id,
        "message": "Executor released successfully" if executor_id else "No executor was assigned to this task",
    }


@router.post("/executors/reset")
async def reset_executors():
    executor_manager["initialize_executors"]()
    executors = executor_manager["get_all_executors"]()
    stats = executor_manager["get_executor_stats"]()
    return {"success": True, "executors": executors, "stats": stats}
