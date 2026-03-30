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
    orch = getattr(app.state, "orchestrator", None)
    if orch:
        await orch.shutdown()


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
# Prefer built Vue app (frontend/dist/), fall back to frontend/ for legacy
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
elif frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
