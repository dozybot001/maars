"""
Plan Agent - Google ADK 驱动实现。
当 planAgentMode=True 时使用，替代自实现 ReAct 循环。
"""

from typing import Any, Callable, Dict, List, Optional

from adk.runner import load_prompt, run_agent
from shared.constants import PLAN_AGENT_MAX_TURNS

from .agent_tools import PLAN_AGENT_TOOLS, execute_plan_agent_tool


async def run_plan_agent_adk(
    plan: Dict,
    on_thinking: Callable[[str], None],
    abort_event: Optional[Any],
    on_tasks_batch: Optional[Callable[[List[Dict], Dict, List[Dict]], None]],
    api_config: Optional[Dict],
    idea_id: Optional[str] = None,
    plan_id: Optional[str] = None,
) -> Dict:
    """
    使用 Google ADK Runner 运行 Plan Agent。
    返回 {tasks}。
    """
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
    plan_state: Dict[str, Any] = {
        "all_tasks": all_tasks,
        "pending_queue": ["0"],
        "idea": idea,
    }

    on_thinking_fn = on_thinking or (lambda *a, **_: None)

    async def executor_fn(name: str, args_str: str) -> tuple[bool, str]:
        return await execute_plan_agent_tool(
            name,
            args_str,
            plan_state,
            on_thinking=on_thinking_fn,
            on_tasks_batch=on_tasks_batch,
            abort_event=abort_event,
            api_config=api_config,
            idea_id=idea_id,
            plan_id=plan_id,
        )

    system_prompt = load_prompt("plan_agent", "plan-agent-prompt.txt")
    user_message = f"**Idea:** {idea}\n\n**Root task:** task_id \"0\", description \"{root_task.get('description', '')}\"\n\nProcess all tasks until GetNextTask returns null, then call FinishPlan."

    finish_result, turn_count = await run_agent(
        name="plan_agent",
        prompt=system_prompt,
        user_message=user_message,
        tools=PLAN_AGENT_TOOLS,
        executor_fn=executor_fn,
        api_config=api_config or {},
        max_turns=PLAN_AGENT_MAX_TURNS,
        finish_tool="FinishPlan",
        operation="Decompose",
        on_thinking=on_thinking_fn,
        abort_event=abort_event,
    )

    plan["tasks"] = plan_state["all_tasks"]
    return {
        "tasks": plan_state["all_tasks"],
        "pending_queue": list(plan_state.get("pending_queue") or []),
        "finished": bool(finish_result) and not (plan_state.get("pending_queue") or []),
        "turn_count": int(turn_count or 0),
    }
