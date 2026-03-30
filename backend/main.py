from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.pipeline.orchestrator import PipelineOrchestrator
from backend.routes import pipeline as pipeline_routes
from backend.routes import events as event_routes

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app):
    yield
    # Shutdown: kill containers and cancel tasks
    from backend.agno.tools.docker_exec import kill_all_containers
    kill_all_containers()
    orch = getattr(app.state, "orchestrator", None)
    if orch:
        await orch._cancel_all_tasks()


app = FastAPI(title="MAARS", version="0.1.0", lifespan=lifespan)

# --- Pipeline stages ---
orchestrator = PipelineOrchestrator()

from backend.agno import create_agno_stages
stages = create_agno_stages(
    model_provider=settings.model_provider,
    model_id=settings.active_model,
    api_key=settings.active_api_key,
    db=orchestrator.db,
    max_iterations=settings.research_max_iterations,
)

orchestrator.stages.update(stages)
orchestrator._wire_broadcast()

# Store orchestrator on app.state for route access
app.state.orchestrator = orchestrator

# --- Routes ---
app.include_router(pipeline_routes.router)
app.include_router(event_routes.router)

# --- Serve frontend static files ---
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
