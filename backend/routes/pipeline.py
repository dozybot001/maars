from fastapi import APIRouter, HTTPException

from backend.models import StartRequest, ActionResponse, PipelineStatus, StageStatus
from backend.pipeline.orchestrator import STAGE_ORDER

router = APIRouter(prefix="/api")

# The orchestrator instance is injected by main.py via app.state
# and accessed through a dependency. For simplicity, we use a module-level ref.
_orchestrator = None


def set_orchestrator(orchestrator):
    global _orchestrator
    _orchestrator = orchestrator


def _get_orchestrator():
    if _orchestrator is None:
        raise HTTPException(status_code=500, detail="Pipeline not initialized")
    return _orchestrator


def _validate_stage(name: str):
    if name not in STAGE_ORDER:
        raise HTTPException(status_code=404, detail=f"Unknown stage: {name}")


@router.post("/pipeline/start")
async def start_pipeline(req: StartRequest):
    orch = _get_orchestrator()
    await orch.start(req.input)
    return {"status": "started", "input": req.input}


@router.get("/stage/{stage_name}/output")
async def get_stage_output(stage_name: str):
    _validate_stage(stage_name)
    orch = _get_orchestrator()
    return {"stage": stage_name, "output": orch.stages[stage_name].output}


@router.get("/pipeline/status", response_model=PipelineStatus)
async def get_status():
    orch = _get_orchestrator()
    status = orch.get_status()
    return PipelineStatus(
        input=status["input"],
        stages=[StageStatus(**s) for s in status["stages"]],
    )


@router.post("/stage/{stage_name}/run", response_model=ActionResponse)
async def run_stage(stage_name: str):
    _validate_stage(stage_name)
    orch = _get_orchestrator()
    err = orch.check_runnable(stage_name)
    if err:
        raise HTTPException(status_code=409, detail=err)
    await orch.run_stage_background(stage_name)
    return ActionResponse(
        stage=stage_name,
        state=orch.stages[stage_name].state.value,
        message="Stage started",
    )


@router.post("/stage/{stage_name}/stop", response_model=ActionResponse)
async def stop_stage(stage_name: str):
    _validate_stage(stage_name)
    orch = _get_orchestrator()
    orch.stop_stage(stage_name)
    return ActionResponse(
        stage=stage_name,
        state=orch.stages[stage_name].state.value,
        message="Stage paused",
    )


@router.post("/stage/{stage_name}/resume", response_model=ActionResponse)
async def resume_stage(stage_name: str):
    _validate_stage(stage_name)
    orch = _get_orchestrator()
    orch.resume_stage(stage_name)
    return ActionResponse(
        stage=stage_name,
        state=orch.stages[stage_name].state.value,
        message="Stage resumed",
    )


@router.post("/stage/{stage_name}/retry", response_model=ActionResponse)
async def retry_stage(stage_name: str):
    _validate_stage(stage_name)
    orch = _get_orchestrator()
    await orch.retry_stage(stage_name)
    return ActionResponse(
        stage=stage_name,
        state=orch.stages[stage_name].state.value,
        message="Stage retrying from scratch",
    )
