from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.routes import pipeline as pipeline_routes
from backend.routes import events as event_routes

app = FastAPI(title="MAARS", version="0.1.0")

# --- Architecture selection ---
# "pipeline" (default) = legacy orchestrated pipeline
# "agents" = multi-agent (Orchestrator + Scholar + Critic)

if settings.architecture == "agents":
    from backend.agents.session import AgentSession

    session = AgentSession()
    # TODO (Phase 2+): create and configure Scholar, Critic, Orchestrator agents
    # session.configure(orchestrator=..., scholar=..., critic=...)
    app.state.orchestrator = session

else:
    # Legacy pipeline mode — unchanged
    from backend.pipeline.orchestrator import PipelineOrchestrator

    orchestrator = PipelineOrchestrator()

    if settings.llm_mode in ("agent", "adk"):
        from backend.agent import create_agent_stages
        stages = create_agent_stages(
            api_key=settings.google_api_key,
            model=settings.gemini_model,
            db=orchestrator.db,
            max_iterations=settings.research_max_iterations,
        )
    elif settings.llm_mode == "agno":
        from backend.agno import create_agno_stages
        stages = create_agno_stages(
            model_provider=settings.agno_model_provider,
            model_id=settings.agno_model_id or settings.gemini_model,
            api_key=settings.google_api_key,
            db=orchestrator.db,
            max_iterations=settings.research_max_iterations,
        )
    elif settings.llm_mode == "gemini":
        from backend.gemini import create_gemini_stages
        stages = create_gemini_stages(
            api_key=settings.google_api_key,
            model=settings.gemini_model,
            db=orchestrator.db,
            max_iterations=settings.research_max_iterations,
        )
    else:
        from backend.mock import create_mock_stages
        stages = create_mock_stages(
            chunk_delay=settings.mock_chunk_delay,
            db=orchestrator.db,
            max_iterations=settings.research_max_iterations,
        )

    orchestrator.stages.update(stages)
    orchestrator._wire_broadcast()
    app.state.orchestrator = orchestrator

# --- Routes ---
app.include_router(pipeline_routes.router)
app.include_router(event_routes.router)

# --- Serve frontend static files ---
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
