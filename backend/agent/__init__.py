from backend.agent.base import AgentStage
from backend.agent.execute import ExecuteAgentStage
from backend.agent.tools import create_db_tools, create_arxiv_toolset, create_fetch_toolset
from backend.llm.gemini_client import GeminiClient
from backend.pipeline.plan import PlanStage

# ADK built-in tools
try:
    from google.adk.tools import google_search, url_context
    _builtin_tools = [google_search, url_context]
except (ImportError, AttributeError):
    _builtin_tools = []

# ADK built-in code executor (Gemini native sandbox)
try:
    from google.adk.code_executors import BuiltInCodeExecutor
    _code_executor = BuiltInCodeExecutor()
except (ImportError, AttributeError):
    _code_executor = None

_REFINE_INSTRUCTION = """\
You are a research advisor in a fully automated research system (MAARS).
No human is in the loop. Make all decisions autonomously.

Your job: take a vague research idea and refine it into a complete, well-structured research proposal.

Available tools:
- Google Search: Web search for trends and context
- url_context: Automatically read content from URLs in the conversation
- search: Search arXiv for papers (via arXiv MCP)
- download + read_paper: Download and read a paper's full text
- fetch: Retrieve content from any URL
- Code execution: You can write and run Python code for data analysis

Process:
1. Use search to find relevant papers on arXiv
2. Use download + read_paper to read key papers in depth
3. Identify gaps, trends, and promising directions grounded in actual literature
4. Evaluate directions on novelty, feasibility, and impact
5. Produce a finalized research idea citing real papers and researchers

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
- search / download / read_paper: Find and read arXiv papers for citations
- fetch: Retrieve content from any URL for verification
- Google Search: Broader verification
- Code execution: You can write and run Python code for analysis

Process:
1. Use list_tasks to see what's available, then read_task_output for each
2. Use read_refined_idea for research context and read_plan_tree for structure
3. Search arXiv to verify claims and add real citations
4. Design paper structure, write each section based on task outputs
5. Polish for coherence and academic tone

Do not fabricate findings. Output in markdown."""


def create_agent_stages(api_key: str, model: str = "gemini-2.0-flash", db=None) -> dict:
    """Assemble all pipeline stages with ADK Agents.

    Uses:
    - ADK built-in: google_search, url_context, BuiltInCodeExecutor
    - MCP servers: arXiv, fetch
    - Custom: DB tools (internal data access)
    """
    db_tools = create_db_tools(db) if db else []
    arxiv_toolset = create_arxiv_toolset()
    fetch_toolset = create_fetch_toolset()

    plan_client = GeminiClient(api_key=api_key, model=model)

    research_tools = _builtin_tools + [arxiv_toolset, fetch_toolset]

    return {
        "refine": AgentStage(
            name="refine",
            instruction=_REFINE_INSTRUCTION,
            tools=research_tools,
            model=model,
            code_executor=_code_executor,
        ),
        "plan": PlanStage(llm_client=plan_client),
        "execute": ExecuteAgentStage(
            db=db,
            tools=db_tools + research_tools,
            model=model,
            code_executor=_code_executor,
        ),
        "write": AgentStage(
            name="write",
            instruction=_WRITE_INSTRUCTION,
            tools=db_tools + research_tools,
            model=model,
            code_executor=_code_executor,
        ),
    }
