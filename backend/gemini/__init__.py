"""Gemini mode: pipeline stages + GeminiClient."""

from backend.llm.gemini_client import GeminiClient
from backend.pipeline.refine import RefineStage
from backend.pipeline.research import ResearchStage
from backend.pipeline.write import WriteStage


def create_gemini_stages(api_key: str, model: str = "gemini-2.0-flash", db=None,
                         max_iterations: int = 1) -> dict:
    """Assemble all pipeline stages with Gemini LLM client."""
    client = GeminiClient(api_key=api_key, model=model)
    return {
        "refine": RefineStage(llm_client=client, db=db),
        "research": ResearchStage(
            llm_client=client, db=db,
            max_iterations=max_iterations,
        ),
        "write": WriteStage(llm_client=client, db=db),
    }
