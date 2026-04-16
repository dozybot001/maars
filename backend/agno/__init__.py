"""Stage factory: assembles all pipeline stages."""

from agno.tools.arxiv import ArxivTools
from agno.tools.wikipedia import WikipediaTools

from backend.agno.tools import create_db_tools, create_docker_tools
from backend.agno.models import create_model
from backend.pipeline.research import ResearchStage
from backend.team.refine import RefineStage
from backend.team.write import WriteStage
from backend.team.polish import PolishStage


def create_agno_stages(
    model_id: str = "gemini-2.5-flash",
    refine_model_id: str | None = None,
    research_model_id: str | None = None,
    write_model_id: str | None = None,
    polish_model_id: str | None = None,
    api_key: str = "",
    db=None,
    max_iterations: int = 1,
    max_delegations: int = 10,
) -> dict:
    model_cache: dict[str, object] = {}

    def get_model(stage_model_id: str | None) -> object:
        resolved = stage_model_id or model_id
        if resolved not in model_cache:
            model_cache[resolved] = create_model("google", resolved, api_key)
        return model_cache[resolved]

    refine_model = get_model(refine_model_id)
    research_model = get_model(research_model_id)
    write_model = get_model(write_model_id)
    polish_model = get_model(polish_model_id or write_model_id)
    db_tools = create_db_tools(db) if db else []
    docker_tools = create_docker_tools(db) if db else []
    list_artifacts = docker_tools[1:] if len(docker_tools) > 1 else []
    research_tools = [ArxivTools(), WikipediaTools()]
    all_research_tools = db_tools + docker_tools + research_tools
    writer_tools = db_tools + list_artifacts
    reviewer_tools = db_tools + list_artifacts

    return {
        "refine": RefineStage(model=refine_model, explorer_tools=research_tools, db=db,
                              max_delegations=max_delegations),
        "research": ResearchStage(
            model=research_model, tools=all_research_tools, db=db,
            max_iterations=max_iterations,
        ),
        "write": WriteStage(model=write_model, writer_tools=writer_tools,
                            reviewer_tools=reviewer_tools, db=db,
                            max_delegations=max_delegations),
        "polish": PolishStage(model=polish_model, db=db),
    }
