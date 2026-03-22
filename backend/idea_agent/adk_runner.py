"""
Idea Agent - Google ADK 驱动实现。
当 ideaAgentMode=True 时使用，替代自实现 ReAct 循环。
"""

from typing import Any, Callable, Dict, Optional

from adk.runner import load_prompt, run_agent
from shared.constants import IDEA_AGENT_MAX_TURNS

from .agent_tools import execute_idea_agent_tool, get_idea_agent_tools


async def run_idea_agent_adk(
    idea: str,
    api_config: dict,
    limit: int = 10,
    on_thinking: Optional[Callable[..., Any]] = None,
    abort_event: Optional[Any] = None,
) -> dict:
    """
    使用 Google ADK Runner 运行 Idea Agent。
    返回 {keywords, papers, refined_idea}，与 collect_literature 一致。
    """
    idea_state: Dict[str, Any] = {
        "idea": idea,
        "keywords": [],
        "papers": [],
        "filtered_papers": [],
        "analysis": "",
        "refined_idea": "",
    }

    on_thinking_fn = on_thinking or (lambda *a, **_: None)

    async def executor_fn(name: str, args_str: str) -> tuple[bool, str]:
        return await execute_idea_agent_tool(
            name,
            args_str,
            idea_state,
            on_thinking=on_thinking_fn,
            abort_event=abort_event,
            api_config=api_config,
            limit=limit,
        )

    tools = get_idea_agent_tools(api_config)
    prompt = load_prompt("idea_agent", "idea-agent-prompt.txt")
    user_message = f"**User's fuzzy idea:** {idea}\n\nProcess the idea using the workflow. Call FinishIdea when done."

    finish_result, _ = await run_agent(
        name="idea",
        prompt=prompt,
        user_message=user_message,
        tools=tools,
        executor_fn=executor_fn,
        api_config=api_config,
        max_turns=IDEA_AGENT_MAX_TURNS,
        finish_tool="FinishIdea",
        operation="Refine",
        on_thinking=on_thinking_fn,
        abort_event=abort_event,
    )

    if finish_result:
        return {
            "keywords": finish_result.get("keywords", []),
            "papers": finish_result.get("papers", []),
            "refined_idea": finish_result.get("refined_idea", ""),
        }

    return {
        "keywords": idea_state.get("keywords", []),
        "papers": idea_state.get("papers", []),
        "refined_idea": idea_state.get("refined_idea", ""),
    }
