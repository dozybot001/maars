"""Executors and validators API routes."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from workers import executor_manager, validator_manager

from ..schemas import TaskIdRequest

router = APIRouter()


# Executors
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


# Validators
@router.get("/validators")
async def get_validators():
    stats = validator_manager["get_validator_stats"]()
    validators = validator_manager["get_all_validators"]()
    return {"validators": validators, "stats": stats}


@router.post("/validators/assign")
async def assign_validator(body: TaskIdRequest):
    task_id = body.task_id
    validator_id = validator_manager["assign_task"](task_id)
    if validator_id is None:
        return JSONResponse(status_code=503, content={"error": "No idle validator available"})
    return {"validatorId": validator_id, "taskId": task_id}


@router.post("/validators/release")
async def release_validator(body: TaskIdRequest):
    task_id = body.task_id
    validator_id = validator_manager["release_validator_by_task_id"](task_id)
    return {
        "success": True,
        "validatorId": validator_id if validator_id is not None else None,
        "taskId": task_id,
        "message": "Validator released successfully" if validator_id else "No validator was assigned to this task",
    }


@router.post("/validators/reset")
async def reset_validators():
    validator_manager["initialize_validators"]()
    validators = validator_manager["get_all_validators"]()
    stats = validator_manager["get_validator_stats"]()
    return {"success": True, "validators": validators, "stats": stats}
