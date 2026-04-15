import asyncio
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from backend.models import StartRequest, StageRunRequest, ActionResponse, PipelineStatus, StageStatus

router = APIRouter(prefix="/api")
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
PATH_PREFIX_RE = re.compile(r"^(?:\./|\.\./|~/|\.\\|\.\.\\|~\\|[A-Za-z]:[\\/]|/)")
TEXT_FILE_EXTENSIONS = {
    ".md", ".txt", ".markdown", ".rst",
    ".json", ".yaml", ".yml", ".toml",
    ".csv", ".tsv",
}


def _get_orchestrator(request: Request):
    orch = getattr(request.app.state, "orchestrator", None)
    if orch is None:
        raise HTTPException(status_code=500, detail="Pipeline not initialized")
    return orch


def _looks_like_strict_file_path(candidate_text: str) -> bool:
    if not candidate_text or "\n" in candidate_text or "\r" in candidate_text:
        return False
    suffix = Path(candidate_text).suffix.lower()
    if suffix not in TEXT_FILE_EXTENSIONS:
        return False
    if PATH_PREFIX_RE.match(candidate_text):
        return True
    if "/" in candidate_text or "\\" in candidate_text:
        return True
    return " " not in candidate_text and "\t" not in candidate_text


def _resolve_research_input(raw_input: str) -> str:
    from backend.kaggle import extract_competition_id

    text = raw_input.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Input cannot be empty")

    candidate_text = text
    if len(candidate_text) >= 2 and candidate_text[0] == candidate_text[-1] and candidate_text[0] in {"'", '"'}:
        candidate_text = candidate_text[1:-1].strip()

    if _looks_like_strict_file_path(candidate_text):
        raw_path = Path(candidate_text).expanduser()
        candidates = [raw_path] if raw_path.is_absolute() else [WORKSPACE_ROOT / raw_path]
        for candidate in candidates:
            if not candidate.exists():
                continue
            if not candidate.is_file():
                raise HTTPException(status_code=400, detail=f"Input path '{candidate_text}' is not a file")
            try:
                return candidate.read_text(encoding="utf-8").strip()
            except UnicodeDecodeError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Input file '{candidate_text}' is not valid UTF-8 text",
                ) from exc
            except OSError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not read input file '{candidate_text}'",
                ) from exc

        raise HTTPException(
            status_code=400,
            detail=(
                f"Input file '{candidate_text}' was not found. "
                "Provide plain research text, a Kaggle URL, or a readable file path."
            ),
        )

    if extract_competition_id(candidate_text):
        return text

    return text


@router.post("/pipeline/start")
async def start_pipeline(req: StartRequest, request: Request):
    orch = _get_orchestrator(request)
    research_input = _resolve_research_input(req.input)
    try:
        await orch.start(research_input)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "started", "input": research_input}


@router.post("/pipeline/run-stage", response_model=ActionResponse)
async def run_stage(req: StageRunRequest, request: Request):
    orch = _get_orchestrator(request)
    try:
        await orch.run_stage(
            stage_name=req.stage,
            session_id=req.session_id,
            clear_outputs=req.clear_outputs,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return ActionResponse(stage=req.stage, state="running", message="Stage started")


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
    try:
        import docker
        def _ping():
            client = docker.from_env()
            client.ping()
        await asyncio.to_thread(_ping)
        return {"connected": True}
    except Exception as e:
        return {"connected": False, "error": str(e)}


@router.post("/pipeline/stop", response_model=ActionResponse)
async def stop_pipeline(request: Request):
    orch = _get_orchestrator(request)
    await orch.stop()
    from backend.pipeline.stage import StageState
    running = next((n for n in ["refine", "research", "write"]
                     if orch.stages[n].state == StageState.PAUSED), "")
    return ActionResponse(stage=running, state="paused", message="Pipeline paused")


@router.post("/pipeline/resume", response_model=ActionResponse)
async def resume_pipeline(request: Request):
    orch = _get_orchestrator(request)
    await orch.resume()
    from backend.pipeline.stage import StageState
    resumed = next((n for n in ["refine", "research", "write"]
                     if orch.stages[n].state == StageState.RUNNING), "")
    return ActionResponse(stage=resumed, state="running", message="Pipeline resumed")
