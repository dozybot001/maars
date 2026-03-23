from backend.llm.gemini_client import GeminiClient
from backend.pipeline.refine import RefineStage
from backend.pipeline.plan import PlanStage
from backend.pipeline.execute import ExecuteStage
from backend.pipeline.write import WriteStage


def create_gemini_stages(api_key: str, model: str = "gemini-2.0-flash", db=None) -> dict:
    """Assemble all pipeline stages with Gemini LLM client."""
    client = GeminiClient(api_key=api_key, model=model)
    return {
        "refine": RefineStage(llm_client=client),
        "plan": PlanStage(llm_client=client),
        "execute": ExecuteStage(llm_client=client, db=db),
        "write": WriteStage(llm_client=client, db=db),
    }
