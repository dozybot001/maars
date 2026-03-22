"""Plan Agent — ADK agent-mode runner."""

from typing import Any, Callable, Dict, List, Optional

from loguru import logger

from adk.runner import load_prompt, run_agent
from shared.constants import PLAN_AGENT_MAX_TURNS
from shared.utils import OnThinking

from agents.plan.tools import PLAN_AGENT_TOOLS, execute_plan_agent_tool


async def run(plan, on_thinking, abort_event, on_tasks_batch, cfg, idea_id, plan_id):
    logger.info("Plan: agent mode")
    tasks = plan.get("tasks") or []
    root_task = next((t for t in tasks if t.get("task_id") == "0"), None)
    if not root_task:
        root_task = next(
            (t for t in tasks if t.get("task_id") and not (t.get("dependencies") or [])),
            tasks[0] if tasks else None,
        )
    if not root_task:
        raise ValueError("No decomposable task found. Generate plan first.")

    all_tasks = list(tasks)
    idea = plan.get("idea") or root_task.get("description") or ""
    state: Dict[str, Any] = {"all_tasks": all_tasks, "pending_queue": ["0"], "idea": idea}
    on_thinking_fn = on_thinking or (lambda *a, **_: None)

    async def executor_fn(name: str, args_str: str) -> tuple[bool, str]:
        return await execute_plan_agent_tool(
            name, args_str, state,
            on_thinking=on_thinking_fn, on_tasks_batch=on_tasks_batch,
            abort_event=abort_event, api_config=cfg,
            idea_id=idea_id, plan_id=plan_id,
        )

    finish, turn_count = await run_agent(
        name="plan", prompt=load_prompt("agents", "plan-agent-prompt.txt"),
        user_message=f"**Idea:** {idea}\n\n**Root task:** task_id \"0\", description \"{root_task.get('description', '')}\"\n\nProcess all tasks until GetNextTask returns null, then call FinishPlan.",
        tools=PLAN_AGENT_TOOLS, executor_fn=executor_fn,
        api_config=cfg, max_turns=PLAN_AGENT_MAX_TURNS,
        finish_tool="FinishPlan", operation="Decompose",
        on_thinking=on_thinking_fn, abort_event=abort_event,
    )

    plan["tasks"] = state["all_tasks"]
    return {
        "tasks": state["all_tasks"],
        "pending_queue": list(state.get("pending_queue") or []),
        "finished": bool(finish) and not (state.get("pending_queue") or []),
        "turn_count": int(turn_count or 0),
    }
