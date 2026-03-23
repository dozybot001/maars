from backend.mock.client import MockClient, ParallelMockClient
from backend.mock.data import (
    REFINE_RESPONSES,
    PLAN_RESPONSES,
    EXECUTE_RESPONSES,
    WRITE_RESPONSES,
)
from backend.pipeline.refine import RefineStage
from backend.pipeline.plan import PlanStage
from backend.pipeline.execute import ExecuteStage
from backend.pipeline.write import WriteStage


def create_mock_stages(chunk_delay: float = 0.08, db=None) -> dict:
    """Assemble all pipeline stages with mock LLM clients."""
    return {
        "refine": RefineStage(llm_client=MockClient(REFINE_RESPONSES, chunk_delay)),
        "plan": PlanStage(llm_client=MockClient(PLAN_RESPONSES, chunk_delay)),
        "execute": ExecuteStage(
            db=db,
            llm_client=ParallelMockClient(EXECUTE_RESPONSES, chunk_delay),
        ),
        "write": WriteStage(
            db=db,
            llm_client=MockClient(WRITE_RESPONSES, chunk_delay),
        ),
    }
