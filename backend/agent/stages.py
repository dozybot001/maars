"""Agent-mode stage overrides for Refine and Write.

In Agent mode, these stages run as a single Agent session (max_rounds=1)
instead of multi-round LLM calls. The Agent has tools and can self-direct
its research/writing workflow autonomously.

Plan and Execute stages are shared across all modes.
"""

from backend.pipeline.stage import BaseStage


class AgentRefineStage(BaseStage):
    """Single-session Agent refines a research idea.

    Unlike the Gemini 3-round approach (Explore → Evaluate → Crystallize),
    the Agent autonomously searches literature, evaluates directions,
    and produces a finalized research idea in one session.
    """

    def __init__(self, name: str = "refine", **kwargs):
        super().__init__(name=name, max_rounds=1, **kwargs)

    def load_input(self) -> str:
        return self.db.get_idea()

    def get_round_label(self, round_index: int) -> str:
        return "Refine"

    def finalize(self) -> str:
        result = self.rounds[-1]["content"] if self.rounds else self.output
        if self.db:
            self.db.save_refined_idea(result)
        return result


class AgentWriteStage(BaseStage):
    """Single-session Agent writes the full research paper.

    Unlike the Gemini multi-phase approach (outline → sections → polish),
    the Agent reads all task outputs via tools and writes the complete
    paper in one session, structuring it as it sees fit.
    """

    def __init__(self, name: str = "write", **kwargs):
        super().__init__(name=name, max_rounds=1, **kwargs)

    def load_input(self) -> str:
        return (
            "Use list_tasks and read_task_output tools to read all completed research outputs. "
            "Use read_refined_idea for context and read_plan_tree for structure. "
            "Use list_artifacts to discover available images and include them using ![caption](filename). "
            "Write the complete research paper in markdown."
        )

    def get_round_label(self, round_index: int) -> str:
        return "Write"

    def finalize(self) -> str:
        result = self.rounds[-1]["content"] if self.rounds else self.output
        if self.db:
            self.db.save_paper(result)
        return result
