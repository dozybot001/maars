from backend.agent.base import AgentStage
from backend.agent.plan import PlanAgentStage
from backend.agent.execute import ExecuteAgentStage
from backend.agent.tools import create_db_tools

_REFINE_INSTRUCTION = """\
You are a research advisor in a fully automated research system (MAARS).
No human is in the loop. Make all decisions autonomously.

Your job: take a vague research idea and refine it into a complete, well-structured research proposal.

Process:
1. Explore the research landscape — identify domains, open questions, possible directions
2. Evaluate directions on novelty, feasibility, and impact
3. Produce a finalized research idea with: title, research question, methodology, expected contributions

IMPORTANT: All research must be conducted through text-based reasoning only. No internet, no code, no experiments.
Output in markdown."""

_WRITE_INSTRUCTION = """\
You are a research paper writer in a fully automated research system (MAARS).
No human is in the loop. Make all decisions autonomously.

Your job: write a complete research paper based on the provided task outputs.

Process:
1. Review all completed task outputs (use the read_task_output tool)
2. Design a paper structure with standard academic sections
3. Write each section based strictly on the task outputs — do not fabricate findings
4. Polish the final paper for coherence and academic tone

Use the read_refined_idea tool to get the research context.
Output the complete paper in markdown."""


def create_agent_stages(model: str = "gemini-2.0-flash", db=None) -> dict:
    """Assemble all pipeline stages with ADK Agents."""
    db_tools = create_db_tools(db) if db else []

    return {
        "refine": AgentStage(
            name="refine",
            instruction=_REFINE_INSTRUCTION,
            model=model,
        ),
        "plan": PlanAgentStage(
            model=model,
        ),
        "execute": ExecuteAgentStage(
            db=db,
            tools=db_tools,
            model=model,
        ),
        "write": AgentStage(
            name="write",
            instruction=_WRITE_INSTRUCTION,
            tools=db_tools,
            model=model,
        ),
    }
