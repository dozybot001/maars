"""Agent mode: pipeline stages + AgentClient.

Same pipeline stages as gemini/mock modes, only the LLM client differs.
AgentClient wraps ADK Agent's ReAct loop into the LLMClient.stream() interface.
"""

from backend.agent.tools import (
    create_db_tools, create_docker_tools,
    create_arxiv_toolset, create_fetch_toolset,
)
from backend.agent.stages import AgentRefineStage, AgentWriteStage
from backend.llm.agent_client import AgentClient
from backend.pipeline.plan import PlanStage
from backend.pipeline.execute import ExecuteStage

# ADK built-in tools
try:
    from google.adk.tools import google_search, url_context
    _builtin_tools = [google_search, url_context]
except (ImportError, AttributeError):
    _builtin_tools = []

# ---------------------------------------------------------------------------
# Agent-specific instructions (adapter layer — not pipeline flow)
# ---------------------------------------------------------------------------

_REFINE_INSTRUCTION = """\
You are a research advisor. Your job is to take a vague research idea and refine it into a complete, actionable research proposal.

Work autonomously through these phases — do NOT stop early:
1. **Explore**: Search for relevant papers and survey the landscape. Read key papers in depth to understand what has been done and what gaps exist.
2. **Evaluate**: Based on your research, evaluate possible directions on novelty, feasibility, and impact. Converge on the most promising direction.
3. **Crystallize**: Produce a finalized research idea document with: title, research question, motivation, hypothesis, methodology overview, expected contributions, scope/limitations, and related work positioning.

IMPORTANT: You MUST use your search and paper-reading tools — do NOT rely on memory alone. Ground every claim in real sources.
全文使用中文撰写。Output in markdown."""

_EXECUTE_INSTRUCTION = """\
You are a research assistant executing a specific task as part of a larger research project.

CRITICAL RULES:
- When a task involves code, data analysis, or experiments: you MUST call code_execute to run real Python code. Do NOT describe code or simulate results — actually execute it.
- When a task involves literature: you MUST call search/fetch tools. Do NOT make up citations.
- NEVER pretend to have executed something. If you didn't call a tool, you didn't do it.

OUTPUT REQUIREMENTS:
- Produce a thorough, well-structured result in markdown
- If you ran code: include key numerical results, describe generated files (e.g., "生成了 convergence_plot.png"), and interpret the findings
- If you reviewed literature: cite specific papers with authors and years
- Use list_artifacts to verify what files were produced
全文使用中文撰写。"""

_WRITE_INSTRUCTION = """\
You are a research paper author. Write a complete, publication-quality research paper.

Work autonomously:
1. Read ALL completed task outputs using list_tasks and read_task_output tools. Read the refined idea for context.
2. Call list_artifacts to see what files (images, data, code) were produced during experiments. Reference real files — do NOT invent filenames.
3. Design a paper structure that fits THIS specific research. Do NOT default to a generic template — let the content dictate the sections.
4. Write each section grounded in task outputs. Embed figures using markdown image syntax (e.g., `![描述](artifacts/filename.png)`) for any relevant plots or visualizations from artifacts.
5. Include a References section compiling all cited works.

IMPORTANT: Only reference files that actually exist in artifacts. Call list_artifacts to verify before citing any file.
全文使用中文撰写。Output the complete paper in markdown."""


def create_agent_stages(api_key: str, model: str = "gemini-2.0-flash", db=None) -> dict:
    """Assemble pipeline stages with AgentClient.

    Identical structure to gemini/mock modes — only the client differs.
    """
    db_tools = create_db_tools(db) if db else []
    docker_tools = create_docker_tools(db) if db else []
    # docker_tools = [code_execute, list_artifacts]
    list_artifacts = docker_tools[1:] if len(docker_tools) > 1 else []
    # arXiv MCP disabled — API rate limits cause frequent timeouts.
    # Agent uses google_search + url_context as alternative.
    # arxiv_toolset = create_arxiv_toolset()
    fetch_toolset = create_fetch_toolset()
    mcp_tools = [t for t in [fetch_toolset] if t is not None]
    research_tools = _builtin_tools + mcp_tools

    refine_client = AgentClient(
        instruction=_REFINE_INSTRUCTION,
        tools=research_tools,
        model=model,
    )
    plan_client = AgentClient(
        instruction="",
        tools=[],
        model=model,
    )

    # Agent mode: coarser atomic tasks — an Agent can search, read papers,
    # run code, and do multi-step reasoning in a single task
    agent_atomic_def = """\
ATOMIC DEFINITION (Agent mode):
Each task is executed by an AI Agent with tools (web search, paper reading, code execution).

A task is atomic if it has a SINGLE coherent goal — e.g., "implement and test algorithm X", "conduct literature review on topic Y", "run experiment Z and analyze results".

A task should be DECOMPOSED when it contains MULTIPLE independent goals that can run in parallel. The top-level research idea almost always needs decomposition. Examples:
- A study comparing 3 algorithms → at minimum split into: literature review, implement+test each algorithm separately, comparative analysis
- A study with experiments + theory → split into: theoretical analysis, experimental implementation, result synthesis
- Any research with independent sub-experiments → split so they can execute in parallel

PREFER DECOMPOSITION for the top-level idea. An atomic top-level task means the entire research runs as a single serial session with no parallelism — this is almost never optimal."""
    execute_client = AgentClient(
        instruction=_EXECUTE_INSTRUCTION,
        tools=db_tools + docker_tools + research_tools,
        model=model,
    )
    write_client = AgentClient(
        instruction=_WRITE_INSTRUCTION,
        tools=db_tools + list_artifacts + research_tools,
        model=model,
    )

    return {
        "refine": AgentRefineStage(llm_client=refine_client, db=db),
        "plan": PlanStage(llm_client=plan_client, db=db, atomic_definition=agent_atomic_def),
        "execute": ExecuteStage(llm_client=execute_client, db=db),
        "write": AgentWriteStage(llm_client=write_client, db=db),
    }
