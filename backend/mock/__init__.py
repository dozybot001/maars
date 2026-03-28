from backend.mock.client import MockClient, ParallelMockClient
from backend.mock.data import (
    REFINE_RESPONSES,
    PLAN_RESPONSES,
    EXECUTE_RESPONSES,
    WRITE_RESPONSES,
)
from backend.pipeline.refine import RefineStage
from backend.pipeline.research import ResearchStage
from backend.pipeline.write import WriteStage


def create_mock_stages(chunk_delay: float = 0.08, db=None,
                       max_iterations: int = 1) -> dict:
    """Assemble all pipeline stages with mock LLM clients."""
    return {
        "refine": RefineStage(llm_client=MockClient(REFINE_RESPONSES, chunk_delay), db=db),
        "research": ResearchStage(
            llm_client=ParallelMockClient(EXECUTE_RESPONSES, chunk_delay), db=db,
            max_iterations=max_iterations,
        ),
        "write": WriteStage(llm_client=MockClient(WRITE_RESPONSES, chunk_delay), db=db),
    }
