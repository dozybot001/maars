"""
Paper Agent implementation.

- Mock mode: via llm_call mock parameter
- LLM mode: single-pass full paper drafting (via llm/paper.py)
- Agent mode: ADK-driven outline -> section drafting -> assembly (via adk_runner.py)
"""

from typing import Any, Callable, Optional

from loguru import logger

from mock import load_mock

from .adk_runner import run_paper_agent_adk
from llm.paper import draft_paper_single_pass


async def run_paper_agent(
    plan: dict,
    outputs: dict,
    api_config: dict,
    format_type: str = "markdown",
    on_thinking: Optional[Callable[..., Any]] = None,
    abort_event: Optional[Any] = None,
) -> str:
    """Generate paper draft in mock / llm / agent mode."""
    mock = None
    if api_config.get("paperUseMock", True):
        entry = load_mock("paper")
        if not entry:
            raise ValueError("No mock data for paper/_default")
        mock = entry["content"]

    try:
        if not mock and api_config.get("paperAgentMode", False):
            logger.info("Paper Agent mode selected; running ADK-driven pipeline")
            return await run_paper_agent_adk(
                plan=plan,
                outputs=outputs,
                api_config=api_config,
                format_type=format_type,
                on_thinking=on_thinking,
                abort_event=abort_event,
            )

        return await draft_paper_single_pass(
            plan=plan,
            outputs=outputs,
            api_config=api_config,
            format_type=format_type,
            on_thinking=on_thinking,
            abort_event=abort_event,
            mock=mock,
        )
    except Exception as e:
        return f"Error generating paper: {str(e)}"
