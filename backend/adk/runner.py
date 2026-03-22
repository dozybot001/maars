"""
Unified ADK agent runner.

Absorbs all boilerplate that was duplicated across four adk_runner.py files:
  prepare_api_env, create_executor_tools, get_model_for_adk,
  _on_tool_call / _on_tool_response / _on_text hooks,
  run_adk_agent_loop, finish_result capture.

Each agent only provides: tools, executor_fn, prompt, user_message, finish_tool name.
"""

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from adk.bridge import (
    create_executor_tools,
    get_model_for_adk,
    prepare_api_env,
)
from adk.runtime import (
    build_tool_args_preview,
    parse_function_response_payload,
    run_adk_agent_loop,
)


# ── Prompt loading ───────────────────────────────────────────────────

_prompt_cache: Dict[str, str] = {}


def load_prompt(agent_dir: str, filename: str) -> str:
    """Load and cache a prompt file from {backend}/{agent_dir}/prompts/{filename}."""
    key = f"{agent_dir}/{filename}"
    if key not in _prompt_cache:
        path = Path(__file__).resolve().parent.parent / agent_dir / "prompts" / filename
        _prompt_cache[key] = path.read_text(encoding="utf-8").strip()
    return _prompt_cache[key]


# ── Unified runner ───────────────────────────────────────────────────

async def run_agent(
    *,
    name: str,
    prompt: str,
    user_message: str,
    tools: List[dict],
    executor_fn: Callable[[str, dict], Any],
    api_config: dict,
    max_turns: int,
    finish_tool: str,
    operation: str,
    on_thinking: Optional[Callable] = None,
    abort_event: Optional[Any] = None,
    task_id: Optional[str] = None,
) -> tuple[Optional[dict], int]:
    """Run an ADK agent session.

    Returns (finish_result, turn_count).
    finish_result is the parsed payload from the finish tool, or None.
    """
    prepare_api_env(api_config)
    model = get_model_for_adk(api_config)
    on_thinking_fn = on_thinking or (lambda *a, **_: None)

    async def _executor(tool_name: str, args: dict) -> tuple[bool, str]:
        args_str = json.dumps(args, ensure_ascii=False)
        return await executor_fn(tool_name, args_str)

    adk_tools = create_executor_tools(tools, _executor)

    finish_result: Optional[dict] = None

    def _on_tool_call(tc_name: str, args: dict, turn_count: int, *extra):
        return on_thinking_fn(
            "",
            task_id=task_id,
            operation=operation,
            schedule_info={
                "turn": turn_count,
                "max_turns": max_turns,
                "tool_name": tc_name,
                "tool_args": build_tool_args_preview(args),
                "tool_args_preview": None,
                "operation": operation,
                **({"task_id": task_id} if task_id else {}),
            },
        )

    def _on_tool_response(tc_name: str, response: Any, _turn_count: int, *extra):
        nonlocal finish_result
        if tc_name == finish_tool and response:
            finish_result = parse_function_response_payload(response)

    def _on_text(text: str, turn_count: int, *extra):
        return on_thinking_fn(
            text,
            task_id=task_id,
            operation=operation,
            schedule_info={
                "turn": turn_count,
                "max_turns": max_turns,
                "operation": operation,
                **({"task_id": task_id} if task_id else {}),
            },
        )

    turn_count = await run_adk_agent_loop(
        app_name=f"maars_{name}",
        agent_name=name,
        model=model,
        instruction=prompt,
        tools=adk_tools,
        user_message=user_message,
        max_turns=max_turns,
        abort_event=abort_event,
        abort_message=f"{name} aborted",
        on_tool_call=_on_tool_call,
        on_tool_response=_on_tool_response,
        on_text=_on_text,
    )

    return finish_result, turn_count
