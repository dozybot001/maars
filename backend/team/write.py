"""Write stage: multi-agent paper writing via Agno Team coordinate mode.

Writer + Reviewer collaborate through a Team leader that orchestrates:
  1. Writer produces a complete paper draft
  2. Reviewer critically reviews the draft
  3. Writer revises based on feedback

This stage communicates with Research only through the session DB —
it reads task outputs, artifacts, and refined_idea, then produces paper.md.
"""

from backend.team.stage import TeamStage


class WriteStage(TeamStage):
    """Multi-agent Write stage: Writer + Reviewer."""

    _member_map = {"writer": "Writer", "reviewer": "Reviewer"}
    _capture_member = "Writer"

    def __init__(self, name: str = "write", model=None, writer_tools=None,
                 db=None, **kwargs):
        super().__init__(name=name, model=model, db=db, **kwargs)
        self._writer_tools = writer_tools or []

    def load_input(self) -> str:
        return (
            "Use list_tasks and read_task_output tools to read all completed research outputs. "
            "Use read_refined_idea for context and read_plan_tree for structure. "
            "Use list_artifacts to discover available images and include them using ![caption](filename). "
            "Write the complete research paper in markdown."
        )

    def _create_team(self):
        from agno.agent import Agent
        from agno.team.team import Team
        from agno.team.mode import TeamMode
        from backend.team.prompts import (
            WRITE_LEADER_SYSTEM, WRITE_WRITER_SYSTEM, WRITE_REVIEWER_SYSTEM,
        )

        writer = Agent(
            name="Writer",
            role="Research paper author — reads all task outputs and writes the paper",
            model=self._model,
            tools=self._writer_tools,
            instructions=[WRITE_WRITER_SYSTEM],
            markdown=True,
            id="writer",
        )

        reviewer = Agent(
            name="Reviewer",
            role="Research paper reviewer — critically reviews drafts for quality",
            model=self._model,
            instructions=[WRITE_REVIEWER_SYSTEM],
            markdown=True,
            id="reviewer",
        )

        return Team(
            name="Write Team",
            mode=TeamMode.coordinate,
            members=[writer, reviewer],
            model=self._model,
            instructions=[WRITE_LEADER_SYSTEM],
            share_member_interactions=True,
            stream_member_events=True,
            markdown=True,
            max_iterations=10,
        )

    def _finalize(self) -> str:
        result = self.output
        if self.db:
            self.db.save_paper(result)
        self._emit("document", {
            "name": "paper", "label": "Paper", "content": result,
        })
        return result
