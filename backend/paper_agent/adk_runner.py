"""
Paper Agent - Google ADK driven implementation (pure agent mode).
When paperAgentMode=True, the LLM writes all paper content directly
and submits via FinishPaper. No intermediate BuildOutline / DraftSection
/ AssemblePaper tool calls.
"""

import json
from typing import Any, Callable, Dict, Optional

from adk import run_agent
from adk.runner import load_prompt
from shared.constants import PAPER_AGENT_MAX_TURNS

from shared.utils import build_output_digest, maars_plan_to_paper_format

from .agent_tools import execute_paper_agent_tool
from .tool_schemas import get_paper_agent_tools


async def run_paper_agent_adk(
    plan: dict,
    outputs: dict,
    api_config: dict,
    format_type: str = "markdown",
    on_thinking: Optional[Callable[..., Any]] = None,
    abort_event: Optional[Any] = None,
) -> str:
    """
    Run Paper Agent via Google ADK Runner.
    Returns paper content string.
    """
    plan_fmt = maars_plan_to_paper_format(plan)
    output_digest = build_output_digest(outputs or {})

    paper_state: Dict[str, Any] = {
        "format_type": format_type,
    }

    async def executor_fn(name: str, args_str: str) -> tuple[bool, str]:
        return await execute_paper_agent_tool(
            name,
            args_str,
            paper_state,
            on_thinking=on_thinking,
            abort_event=abort_event,
            api_config=api_config,
        )

    tools = get_paper_agent_tools(api_config)
    system_prompt = load_prompt("paper_agent", "paper-agent-prompt.txt")

    user_message = f"""**Research Goal:** {plan_fmt.get('goal', 'N/A')}

**Plan Steps:**
{json.dumps(plan_fmt.get('steps', []), ensure_ascii=False, indent=2)}

**Task Output Digest:**
{json.dumps(output_digest, ensure_ascii=False, indent=2)}

**Output Format:** {format_type}

Write the full paper, then call FinishPaper with the complete content."""

    finish_result, _turn_count = await run_agent(
        name="paper_agent",
        prompt=system_prompt,
        user_message=user_message,
        tools=tools,
        executor_fn=executor_fn,
        api_config=api_config,
        max_turns=PAPER_AGENT_MAX_TURNS,
        finish_tool="FinishPaper",
        operation="Paper",
        on_thinking=on_thinking,
        abort_event=abort_event,
    )

    if finish_result:
        return finish_result.get("content", "")

    return ""
