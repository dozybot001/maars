import logging

from fastapi import APIRouter, HTTPException, Request

from backend.models import StartRequest, ActionResponse, PipelineStatus, StageStatus
from backend.pipeline.orchestrator import STAGE_ORDER

log = logging.getLogger("maars")

router = APIRouter(prefix="/api")


def _get_orchestrator(request: Request):
    orch = getattr(request.app.state, "orchestrator", None)
    if orch is None:
        raise HTTPException(status_code=500, detail="Pipeline not initialized")
    return orch


def _validate_stage(name: str):
    if name not in STAGE_ORDER:
        raise HTTPException(status_code=404, detail=f"Unknown stage: {name}")


@router.post("/pipeline/start")
async def start_pipeline(req: StartRequest, request: Request):
    orch = _get_orchestrator(request)
    try:
        await orch.start(req.input)
    except Exception as e:
        log.exception("Pipeline start failed")
        raise HTTPException(status_code=500, detail=f"Failed to start pipeline: {e}")
    return {"status": "started", "input": req.input}


@router.get("/pipeline/status", response_model=PipelineStatus)
async def get_status(request: Request):
    orch = _get_orchestrator(request)
    status = orch.get_status()
    return PipelineStatus(
        input=status["input"],
        stages=[StageStatus(**s) for s in status["stages"]],
    )


@router.get("/docker/status")
async def docker_status():
    """Check if Docker daemon is reachable."""
    try:
        import docker
        client = docker.from_env()
        client.ping()
        return {"connected": True}
    except Exception as e:
        return {"connected": False, "error": str(e)}


@router.post("/pipeline/stop")
async def stop_pipeline(request: Request):
    """Stop whatever stage is currently running. Used by beforeunload."""
    orch = _get_orchestrator(request)
    for name in STAGE_ORDER:
        stage = orch.stages[name]
        if stage.state.value == "running":
            await orch.stop_stage(name)
            return {"stopped": name}
    return {"stopped": None}


@router.post("/stage/{stage_name}/stop", response_model=ActionResponse)
async def stop_stage(stage_name: str, request: Request):
    _validate_stage(stage_name)
    orch = _get_orchestrator(request)
    await orch.stop_stage(stage_name)
    return ActionResponse(
        stage=stage_name,
        state=orch.stages[stage_name].state.value,
        message="Stage paused",
    )


@router.post("/stage/{stage_name}/resume", response_model=ActionResponse)
async def resume_stage(stage_name: str, request: Request):
    _validate_stage(stage_name)
    orch = _get_orchestrator(request)
    await orch.resume_stage(stage_name)
    return ActionResponse(
        stage=stage_name,
        state=orch.stages[stage_name].state.value,
        message="Stage resumed",
    )
