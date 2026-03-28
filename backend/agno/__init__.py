"""Agno mode: pipeline stages + AgnoClient.

Same pipeline stages as ADK mode, but uses Agno framework for the agent loop.
Supports multiple model providers (Google, Anthropic, OpenAI) via config.
"""

from agno.tools.arxiv import ArxivTools
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.wikipedia import WikipediaTools

from backend.agent import (
    _REFINE_INSTRUCTION, _EXECUTE_INSTRUCTION, _WRITE_INSTRUCTION,
)
from backend.agent.tools import create_db_tools, create_docker_tools
from backend.agent.stages import AgentRefineStage, AgentWriteStage
from backend.agno.models import create_model
from backend.llm.agno_client import AgnoClient
from backend.pipeline.research import ResearchStage


def create_agno_stages(
    model_provider: str = "google",
    model_id: str = "gemini-2.0-flash",
    api_key: str = "",
    db=None,
    max_iterations: int = 1,
) -> dict:
    """Assemble pipeline stages with AgnoClient.

    Identical structure to ADK mode — only the client differs.
    Tools (DB, Docker) are plain Python functions, directly compatible with Agno.
    """
    model = create_model(model_provider, model_id, api_key)

    db_tools = create_db_tools(db) if db else []
    docker_tools = create_docker_tools(db) if db else []
    # docker_tools = [code_execute, list_artifacts]
    list_artifacts = docker_tools[1:] if len(docker_tools) > 1 else []

    # Agno-native research tools (no API keys needed)
    research_tools = [DuckDuckGoTools(), ArxivTools(), WikipediaTools()]

    refine_client = AgnoClient(
        instruction=_REFINE_INSTRUCTION,
        model=model,
        tools=research_tools,
    )

    execute_client = AgnoClient(
        instruction=_EXECUTE_INSTRUCTION,
        model=model,
        tools=db_tools + docker_tools + research_tools,
    )
    write_client = AgnoClient(
        instruction=_WRITE_INSTRUCTION,
        model=model,
        tools=db_tools + list_artifacts + research_tools,
    )

    return {
        "refine": AgentRefineStage(llm_client=refine_client, db=db),
        "research": ResearchStage(
            llm_client=execute_client, db=db,
            max_iterations=max_iterations,
            # atomic_definition calibrated dynamically before decompose
        ),
        "write": AgentWriteStage(llm_client=write_client, db=db),
    }
