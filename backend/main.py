from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from backend.agno import create_agno_stages
from backend.config import settings
from backend.pipeline.orchestrator import PipelineOrchestrator
from backend.routes import events as event_routes
from backend.routes import pipeline as pipeline_routes
from backend.routes import sessions as session_routes


class AccessTokenMiddleware(BaseHTTPMiddleware):
    """Optional Bearer token auth for /api/* routes.

    Only active when MAARS_ACCESS_TOKEN is set. Non-API routes (frontend static
    files) are always allowed through.
    """

    async def dispatch(self, request: Request, call_next):
        if settings.access_token and request.url.path.startswith("/api"):
            auth = request.headers.get("Authorization", "")
            if auth != f"Bearer {settings.access_token}":
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing access token"},
                )
        return await call_next(request)


@asynccontextmanager
async def lifespan(app):
    # Warn if API is exposed without authentication
    if not settings.access_token:
        import logging
        logging.getLogger("maars").warning(
            "\033[33m⚠  MAARS_ACCESS_TOKEN is not set — the API is open without "
            "authentication. Set MAARS_ACCESS_TOKEN in .env before exposing "
            "this service on a network.\033[0m"
        )
    yield
    orch = getattr(app.state, "orchestrator", None)
    if orch:
        await orch.shutdown()


app = FastAPI(title="MAARS", version="0.1.0", lifespan=lifespan)
app.add_middleware(AccessTokenMiddleware)

# --- Pipeline stages ---
orchestrator = PipelineOrchestrator()

# Build per-stage model overrides (only include stages with explicit config)
_stage_configs = {}
for _stage in ("refine", "research", "write"):
    _p, _m, _k = settings.stage_config(_stage)
    if getattr(settings, f"{_stage}_provider", "") or getattr(settings, f"{_stage}_model", ""):
        _stage_configs[_stage] = (_p, _m, _k)

stages = create_agno_stages(
    model_provider=settings.model_provider,
    model_id=settings.active_model,
    api_key=settings.active_api_key,
    db=orchestrator.db,
    max_iterations=settings.research_max_iterations,
    stage_configs=_stage_configs or None,
)

orchestrator.stages.update(stages)
orchestrator._wire_broadcast()

# Store orchestrator on app.state for route access
app.state.orchestrator = orchestrator

# --- Routes ---
app.include_router(pipeline_routes.router)
app.include_router(event_routes.router)
app.include_router(session_routes.router)

# --- Serve frontend static files ---
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
