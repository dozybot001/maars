"""Paper Agent — ADK agent-mode runner."""

import json
from typing import Any, Dict, Optional

from loguru import logger

from adk.runner import load_prompt, run_agent
from shared.constants import PAPER_AGENT_MAX_TURNS
from shared.utils import OnThinking

from agents.paper.tools import execute_paper_agent_tool, get_paper_agent_tools


async def run(plan, outputs, cfg, format_type, on_thinking, abort_event):
    logger.info("Paper: agent mode")
    from shared.utils import maars_plan_to_paper_format, build_output_digest

    plan_fmt = maars_plan_to_paper_format(plan)
    output_digest = build_output_digest(outputs or {})
    state: Dict[str, Any] = {"format_type": format_type}

    async def executor_fn(name: str, args_str: str) -> tuple[bool, str]:
        return await execute_paper_agent_tool(
            name, args_str, state,
            on_thinking=on_thinking, abort_event=abort_event, api_config=cfg,
        )

    user_message = f"""**Research Goal:** {plan_fmt.get('goal', 'N/A')}

**Plan Steps:**
{json.dumps(plan_fmt.get('steps', []), ensure_ascii=False, indent=2)}

**Task Output Digest:**
{json.dumps(output_digest, ensure_ascii=False, indent=2)}

**Output Format:** {format_type}

Write the full paper, then call FinishPaper with the complete content."""

    finish, _ = await run_agent(
        name="paper", prompt=load_prompt("agents", "paper-agent-prompt.txt"),
        user_message=user_message,
        tools=get_paper_agent_tools(cfg), executor_fn=executor_fn,
        api_config=cfg, max_turns=PAPER_AGENT_MAX_TURNS,
        finish_tool="FinishPaper", operation="Paper",
        on_thinking=on_thinking, abort_event=abort_event,
    )
    return finish.get("content", "") if finish else ""
