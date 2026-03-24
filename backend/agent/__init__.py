from backend.agent.base import AgentStage
from backend.agent.execute import ExecuteAgentStage
from backend.agent.tools import create_db_tools, create_search_tools, create_academic_tools
from backend.llm.gemini_client import GeminiClient
from backend.pipeline.plan import PlanStage

_REFINE_INSTRUCTION = """\
You are a research advisor in a fully automated research system (MAARS).
No human is in the loop. Make all decisions autonomously.

Your job: take a vague research idea and refine it into a complete, well-structured research proposal.

Available tools:
- arxiv_search: Search arXiv for real papers (use specific technical terms)
- semantic_scholar_search: Find papers with citation counts and impact metrics
- Google Search: Broader web search for trends and context

Process:
1. Search arXiv and Semantic Scholar to map the real research landscape
2. Identify gaps, trends, and promising directions grounded in actual literature
3. Evaluate directions on novelty, feasibility, and impact
4. Produce a finalized research idea citing real papers and researchers

Output in markdown."""

_WRITE_INSTRUCTION = """\
You are a research paper writer in a fully automated research system (MAARS).
No human is in the loop. Make all decisions autonomously.

Your job: write a complete research paper based on the provided task outputs.

Available tools:
- list_tasks: See all completed task IDs and sizes
- read_task_output: Read a specific task's output by ID
- read_refined_idea: Get the research context from Refine stage
- read_plan_tree: See the full task decomposition structure
- arxiv_search / semantic_scholar_search: Find and verify citations
- Google Search: Broader verification

Process:
1. Use list_tasks to see what's available, then read_task_output for each
2. Use read_refined_idea for research context and read_plan_tree for structure
3. Search academic sources to verify claims and add real citations
4. Design paper structure, write each section based on task outputs
5. Polish for coherence and academic tone

Do not fabricate findings. Output in markdown."""


def create_agent_stages(api_key: str, model: str = "gemini-2.0-flash", db=None) -> dict:
    """Assemble all pipeline stages with ADK Agents.

    Plan stage reuses the pipeline's recursive decomposition engine
    with a Gemini LLM client — recursive batch-parallel decomposition
    is a structural algorithm, not an agent reasoning task.
    """
    db_tools = create_db_tools(db) if db else []
    search_tools = create_search_tools()
    academic_tools = create_academic_tools()

    plan_client = GeminiClient(api_key=api_key, model=model)

    return {
        "refine": AgentStage(
            name="refine",
            instruction=_REFINE_INSTRUCTION,
            tools=search_tools + academic_tools,
            model=model,
        ),
        "plan": PlanStage(llm_client=plan_client),
        "execute": ExecuteAgentStage(
            db=db,
            tools=db_tools + search_tools + academic_tools,
            model=model,
        ),
        "write": AgentStage(
            name="write",
            instruction=_WRITE_INSTRUCTION,
            tools=db_tools + search_tools + academic_tools,
            model=model,
        ),
    }
