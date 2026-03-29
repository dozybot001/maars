"""Stage overrides for Refine and Write.

The Agent has tools and can self-direct its research/writing
workflow autonomously in a single session.
"""

from backend.pipeline.stage import BaseStage


class RefineStage(BaseStage):
    """Single-session Agent refines a research idea."""

    system_instruction = """\
You are a research advisor. Your job is to take a vague research idea and refine it into a complete, actionable research proposal.

Work autonomously through these phases — do NOT stop early:
1. **Explore**: Search for relevant papers and survey the landscape. Read key papers in depth to understand what has been done and what gaps exist.
2. **Evaluate**: Based on your research, evaluate possible directions on novelty, feasibility, and impact. Converge on the most promising direction.
3. **Crystallize**: Produce a finalized research idea document with: title, research question, motivation, hypothesis, methodology overview, expected contributions, scope/limitations, and related work positioning.

IMPORTANT: You MUST use your search and paper-reading tools — do NOT rely on memory alone. Ground every claim in real sources.
全文使用中文撰写。Output in markdown."""

    def __init__(self, name: str = "refine", **kwargs):
        super().__init__(name=name, **kwargs)

    def load_input(self) -> str:
        return self.db.get_idea()

    def get_round_label(self, round_index: int) -> str:
        return "Refine"

    def finalize(self) -> str:
        result = self.rounds[-1]["content"] if self.rounds else self.output
        if self.db:
            self.db.save_refined_idea(result)
        self._emit("document", {"name": "refined_idea", "label": "Refined Idea", "content": result})
        return result


class WriteStage(BaseStage):
    """Single-session Agent writes the full research paper."""

    system_instruction = """\
You are a research paper author. Write a complete, publication-quality research paper.

Work autonomously:
1. Read ALL completed task outputs using list_tasks and read_task_output tools. Read the refined idea for context.
2. Call list_artifacts to see what files (images, data, code) were produced during experiments. Reference real files — do NOT invent filenames.
3. Design a paper structure that fits THIS specific research. Do NOT default to a generic template — let the content dictate the sections.
4. Write each section grounded in task outputs. Embed figures using markdown image syntax (e.g., `![描述](artifacts/filename.png)`) for any relevant plots or visualizations from artifacts.
5. Include a References section compiling all cited works.

IMPORTANT: Only reference files that actually exist in artifacts. Call list_artifacts to verify before citing any file.
全文使用中文撰写。Output the complete paper in markdown."""

    def __init__(self, name: str = "write", **kwargs):
        super().__init__(name=name, **kwargs)

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
        self._emit("document", {"name": "paper", "label": "Paper", "content": result})
        return result
