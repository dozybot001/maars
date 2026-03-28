from fastapi import APIRouter, HTTPException, Request

from backend.models import StartRequest, ActionResponse, PipelineStatus, StageStatus
from backend.pipeline.orchestrator import STAGE_ORDER

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

    # Auto-detect Kaggle competition URL → skip Refine, fetch data
    from backend.kaggle import extract_competition_id
    kaggle_id = extract_competition_id(req.input)
    if kaggle_id:
        await orch.start_kaggle(kaggle_id)
        return {"status": "started", "input": req.input, "kaggle": kaggle_id}

    await orch.start(req.input)
    return {"status": "started", "input": req.input}


@router.get("/stage/{stage_name}/output")
async def get_stage_output(stage_name: str, request: Request):
    _validate_stage(stage_name)
    orch = _get_orchestrator(request)
    return {"stage": stage_name, "output": orch.stages[stage_name].output}


@router.get("/pipeline/status", response_model=PipelineStatus)
async def get_status(request: Request):
    orch = _get_orchestrator(request)
    status = orch.get_status()
    return PipelineStatus(
        input=status["input"],
        stages=[StageStatus(**s) for s in status["stages"]],
    )


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


@router.post("/stage/{stage_name}/retry", response_model=ActionResponse)
async def retry_stage(stage_name: str, request: Request):
    _validate_stage(stage_name)
    orch = _get_orchestrator(request)
    await orch.retry_stage(stage_name)
    return ActionResponse(
        stage=stage_name,
        state=orch.stages[stage_name].state.value,
        message="Stage retrying from scratch",
    )


