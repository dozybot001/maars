"""Idea Agent — ADK agent-mode runner."""

from typing import Any, Dict, Optional

from loguru import logger

from adk.runner import load_prompt, run_agent
from shared.constants import IDEA_AGENT_MAX_TURNS
from shared.utils import OnThinking

from agents.idea.tools import execute_idea_agent_tool, get_idea_agent_tools


async def run(idea, cfg, limit, on_thinking, abort_event):
    logger.info("Idea: agent mode")
    state: Dict[str, Any] = {
        "idea": idea, "keywords": [], "papers": [],
        "filtered_papers": [], "analysis": "", "refined_idea": "",
    }
    on_thinking_fn = on_thinking or (lambda *a, **_: None)

    async def executor_fn(name: str, args_str: str) -> tuple[bool, str]:
        return await execute_idea_agent_tool(
            name, args_str, state,
            on_thinking=on_thinking_fn, abort_event=abort_event,
            api_config=cfg, limit=limit,
        )

    finish, _ = await run_agent(
        name="idea", prompt=load_prompt("agents", "idea-agent-prompt.txt"),
        user_message=f"**User's fuzzy idea:** {idea}\n\nProcess the idea using the workflow. Call FinishIdea when done.",
        tools=get_idea_agent_tools(cfg), executor_fn=executor_fn,
        api_config=cfg, max_turns=IDEA_AGENT_MAX_TURNS,
        finish_tool="FinishIdea", operation="Refine",
        on_thinking=on_thinking_fn, abort_event=abort_event,
    )
    if finish:
        return {k: finish.get(k, state.get(k, "")) for k in ("keywords", "papers", "refined_idea")}
    return {k: state.get(k, "") for k in ("keywords", "papers", "refined_idea")}
