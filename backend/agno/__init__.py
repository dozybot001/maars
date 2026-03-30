"""Stage factory: assembles all pipeline stages.

Refine + Write: multi-agent via Agno Team (coordinate mode).
Research: agentic workflow via AgnoClient.
"""

from agno.tools.arxiv import ArxivTools
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.wikipedia import WikipediaTools

from backend.agno.tools import create_db_tools, create_docker_tools
from backend.agno.models import create_model
from backend.agno.client import AgnoClient
from backend.pipeline.research import ResearchStage
from backend.team.refine import RefineStage
from backend.team.write import WriteStage


def create_agno_stages(
    model_provider: str = "google",
    model_id: str = "gemini-2.0-flash",
    api_key: str = "",
    db=None,
    max_iterations: int = 1,
) -> dict:
    """Assemble pipeline stages.

    Refine + Write: Agno Team (multi-agent coordinate mode).
    Research: AgnoClient (single-client agentic workflow).
    """
    model = create_model(model_provider, model_id, api_key)

    db_tools = create_db_tools(db) if db else []
    docker_tools = create_docker_tools(db) if db else []
    list_artifacts = docker_tools[1:] if len(docker_tools) > 1 else []

    research_tools = [DuckDuckGoTools(), ArxivTools(), WikipediaTools()]

    # Research: single-client workflow (AgnoClient)
    research_client = AgnoClient(
        model=model,
        tools=db_tools + docker_tools + research_tools,
    )

    # Write: Team (Writer + Reviewer)
    writer_tools = db_tools + list_artifacts + research_tools

    return {
        "refine": RefineStage(model=model, explorer_tools=research_tools, db=db),
        "research": ResearchStage(
            llm_client=research_client, db=db,
            max_iterations=max_iterations,
        ),
        "write": WriteStage(model=model, writer_tools=writer_tools, db=db),
    }
