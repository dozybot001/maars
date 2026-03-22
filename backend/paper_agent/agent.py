"""
Paper Agent - Google ADK 驱动 (paperAgentMode=True)。
替代自实现多步 MVP 循环，使用 backend/paper_agent/adk_runner.py。
"""

from typing import Any, Callable, Optional

from shared.utils import OnThinking

from . import adk_runner


async def run_paper_agent(
    plan: dict,
    outputs: dict,
    api_config: dict,
    format_type: str = "markdown",
    on_thinking: OnThinking = None,
    abort_event: Optional[Any] = None,
) -> str:
    """
    Paper Agent 入口。使用 Google ADK 驱动。
    返回 paper content string。
    """
    return await adk_runner.run_paper_agent_adk(
        plan=plan,
        outputs=outputs,
        api_config=api_config,
        format_type=format_type,
        on_thinking=on_thinking,
        abort_event=abort_event,
    )
