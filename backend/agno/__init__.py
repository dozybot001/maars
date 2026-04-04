"""Stage factory: assembles all pipeline stages."""

from agno.tools.arxiv import ArxivTools
from agno.tools.wikipedia import WikipediaTools

from backend.agno.tools import create_db_tools, create_docker_tools
from backend.agno.models import create_model
from backend.pipeline.research import ResearchStage
from backend.team.refine import RefineStage
from backend.team.write import WriteStage


def create_agno_stages(
    model_id: str = "gemini-2.5-flash",
    api_key: str = "",
    db=None,
    max_iterations: int = 1,
    max_delegations: int = 10,
) -> dict:
    model = create_model("google", model_id, api_key)
    db_tools = create_db_tools(db) if db else []
    docker_tools = create_docker_tools(db) if db else []
    list_artifacts = docker_tools[1:] if len(docker_tools) > 1 else []
    research_tools = [ArxivTools(), WikipediaTools()]
    all_research_tools = db_tools + docker_tools + research_tools
    writer_tools = db_tools + list_artifacts
    reviewer_tools = db_tools + list_artifacts

    return {
        "refine": RefineStage(model=model, explorer_tools=research_tools, db=db,
                              max_delegations=max_delegations),
        "research": ResearchStage(
            model=model, tools=all_research_tools, db=db,
            max_iterations=max_iterations,
        ),
        "write": WriteStage(model=model, writer_tools=writer_tools,
                            reviewer_tools=reviewer_tools, db=db,
                            max_delegations=max_delegations),
    }
