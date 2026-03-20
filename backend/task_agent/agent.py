"""
Task Agent - Google ADK 驱动 (taskAgentMode=True)。
替代自实现 ReAct 循环，使用 backend/task_agent/adk_runner.py。
"""

from typing import Any

from . import adk_runner
from .task_context import TaskContext


async def run_task_agent(ctx: TaskContext) -> Any:
    """Task Agent 入口。使用 Google ADK 驱动。"""
    return await adk_runner.run_task_agent_adk(
        task_id=ctx.task_id,
        description=ctx.description,
        input_spec=ctx.input_spec,
        output_spec=ctx.output_spec,
        resolved_inputs=ctx.resolved_inputs,
        api_config=ctx.api_config,
        abort_event=ctx.abort_event,
        on_thinking=ctx.on_thinking,
        idea_id=ctx.idea_id,
        plan_id=ctx.plan_id,
        execution_run_id=ctx.execution_run_id,
        docker_container_name=ctx.docker_container_name,
        validation_spec=ctx.validation_spec,
        idea_context=ctx.idea_context,
        execution_context=ctx.execution_context,
        on_prompt_built=ctx.on_prompt_built,
    )
