from backend.agent.base import AgentStage
from backend.agent.execute import ExecuteAgentStage
from backend.agent.tools import create_db_tools, create_search_tools
from backend.llm.gemini_client import GeminiClient
from backend.pipeline.plan import PlanStage

_REFINE_INSTRUCTION = """\
You are a research advisor in a fully automated research system (MAARS).
No human is in the loop. Make all decisions autonomously.

Your job: take a vague research idea and refine it into a complete, well-structured research proposal.

Process:
1. Use Google Search to explore the real research landscape — find recent papers, trends, and open questions
2. Evaluate directions on novelty, feasibility, and impact
3. Produce a finalized research idea with: title, research question, methodology, expected contributions

Ground your analysis in real sources. Cite actual papers and researchers.
Output in markdown."""

_WRITE_INSTRUCTION = """\
You are a research paper writer in a fully automated research system (MAARS).
No human is in the loop. Make all decisions autonomously.

Your job: write a complete research paper based on the provided task outputs.

Process:
1. Review all completed task outputs (use the read_task_output tool)
2. Use Google Search to verify key claims and find additional citations
3. Design a paper structure with standard academic sections
4. Write each section based strictly on the task outputs — do not fabricate findings
5. Polish the final paper for coherence and academic tone

Use the read_refined_idea tool to get the research context.
Output the complete paper in markdown."""


def create_agent_stages(api_key: str, model: str = "gemini-2.0-flash", db=None) -> dict:
    """Assemble all pipeline stages with ADK Agents.

    Plan stage reuses the pipeline's recursive decomposition engine
    with a Gemini LLM client — recursive batch-parallel decomposition
    is a structural algorithm, not an agent reasoning task.
    """
    db_tools = create_db_tools(db) if db else []
    search_tools = create_search_tools()

    plan_client = GeminiClient(api_key=api_key, model=model)

    return {
        "refine": AgentStage(
            name="refine",
            instruction=_REFINE_INSTRUCTION,
            tools=search_tools,
            model=model,
        ),
        "plan": PlanStage(llm_client=plan_client),
        "execute": ExecuteAgentStage(
            db=db,
            tools=db_tools + search_tools,
            model=model,
        ),
        "write": AgentStage(
            name="write",
            instruction=_WRITE_INSTRUCTION,
            tools=db_tools + search_tools,
            model=model,
        ),
    }
