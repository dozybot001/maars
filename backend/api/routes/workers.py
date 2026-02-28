"""Workers API - task worker pool management."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from execution import worker_manager

from ..schemas import TaskIdRequest

router = APIRouter()


@router.get("/workers")
async def get_workers():
    stats = worker_manager["get_worker_stats"]()
    workers_list = worker_manager["get_all_workers"]()
    return {"workers": workers_list, "stats": stats}


@router.post("/workers/assign")
async def assign_worker(body: TaskIdRequest):
    task_id = body.task_id
    worker_id = worker_manager["assign_task"](task_id)
    if worker_id is None:
        return JSONResponse(status_code=503, content={"error": "No idle worker available"})
    return {"workerId": worker_id, "taskId": task_id}


@router.post("/workers/release")
async def release_worker(body: TaskIdRequest):
    task_id = body.task_id
    worker_id = worker_manager["release_worker_by_task_id"](task_id)
    return {
        "success": True,
        "workerId": worker_id if worker_id is not None else None,
        "taskId": task_id,
        "message": "Worker released successfully" if worker_id else "No worker was assigned to this task",
    }


@router.post("/workers/reset")
async def reset_workers():
    worker_manager["initialize_workers"]()
    workers_list = worker_manager["get_all_workers"]()
    stats = worker_manager["get_worker_stats"]()
    return {"success": True, "workers": workers_list, "stats": stats}
