"""Agent mode: pipeline stages + AgentClient.

Same pipeline stages as gemini/mock modes, only the LLM client differs.
AgentClient wraps ADK Agent's ReAct loop into the LLMClient.stream() interface.
"""

from backend.agent.tools import (
    create_db_tools, create_docker_tools,
    create_arxiv_toolset, create_fetch_toolset,
)
from backend.llm.agent_client import AgentClient
from backend.pipeline.refine import RefineStage
from backend.pipeline.plan import PlanStage
from backend.pipeline.execute import ExecuteStage
from backend.pipeline.write import WriteStage

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

# ---------------------------------------------------------------------------
# Agent-specific instructions (adapter layer — not pipeline flow)
# ---------------------------------------------------------------------------

_REFINE_INSTRUCTION = """\
You have access to research tools. Use them to ground your analysis in real sources.

Available tools:
- Google Search: Web search for trends and context
- url_context: Read content from URLs
- search + download + read_paper: arXiv paper search and full-text reading
- fetch: Retrieve content from any URL

Process: search for relevant papers, read key ones in depth, then produce your analysis."""

_EXECUTE_INSTRUCTION = """\
You have access to research and experiment tools. You MUST use them — do NOT fabricate results.

CRITICAL RULES:
- When a task involves code, data analysis, or experiments: you MUST call code_execute to run real Python code. Do NOT describe code or simulate results — actually execute it.
- When a task involves literature: you MUST call search/fetch tools. Do NOT make up citations.
- NEVER pretend to have executed something. If you didn't call a tool, you didn't do it.

Available tools:
- Google Search + arXiv: Find papers, data, and evidence
- fetch: Retrieve content from any URL
- code_execute: Run Python in Docker (outputs persist as artifacts in /workspace/output/)
- list_artifacts: See experiment outputs produced so far"""

_WRITE_INSTRUCTION = """\
You have access to research tools to verify and enrich the paper.

Available tools:
- list_tasks + read_task_output: Read completed research outputs
- read_refined_idea + read_plan_tree: Research context and structure
- search + download + read_paper: arXiv papers for citations
- fetch: Retrieve content from any URL
- code_execute + list_artifacts: Reference experiment outputs
- Google Search: Broader verification

Do not fabricate findings."""


def create_agent_stages(api_key: str, model: str = "gemini-2.0-flash", db=None) -> dict:
    """Assemble pipeline stages with AgentClient.

    Identical structure to gemini/mock modes — only the client differs.
    """
    db_tools = create_db_tools(db) if db else []
    docker_tools = create_docker_tools(db) if db else []
    arxiv_toolset = create_arxiv_toolset()
    fetch_toolset = create_fetch_toolset()
    research_tools = _builtin_tools + [arxiv_toolset, fetch_toolset]

    refine_client = AgentClient(
        instruction=_REFINE_INSTRUCTION,
        tools=research_tools,
        model=model,
        code_executor=_code_executor,
    )
    plan_client = AgentClient(
        instruction="",
        tools=[],
        model=model,
    )

    # Agent mode: coarser atomic tasks — an Agent can search, read papers,
    # run code, and do multi-step reasoning in a single task
    agent_atomic_def = """\
Given a task, decide:
1. Is it **atomic**? In this pipeline, each task is executed by an AI Agent with tools (web search, paper reading, code execution). A task is atomic if a single Agent session can complete it end-to-end, even if it requires multiple tool calls. Examples of atomic tasks: "search and summarize literature on X", "implement and run experiment Y", "analyze dataset and produce visualization".
2. If NOT atomic, decompose it. But prefer FEWER, COARSER tasks. An Agent is powerful — don't split what one Agent can handle."""
    execute_client = AgentClient(
        instruction=_EXECUTE_INSTRUCTION,
        tools=db_tools + docker_tools + research_tools,
        model=model,
        code_executor=_code_executor,
    )
    write_client = AgentClient(
        instruction=_WRITE_INSTRUCTION,
        tools=db_tools + docker_tools + research_tools,
        model=model,
        code_executor=_code_executor,
    )

    return {
        "refine": RefineStage(llm_client=refine_client, db=db),
        "plan": PlanStage(llm_client=plan_client, db=db, atomic_definition=agent_atomic_def),
        "execute": ExecuteStage(llm_client=execute_client, db=db),
        "write": WriteStage(llm_client=write_client, db=db),
    }
