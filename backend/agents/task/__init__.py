"""Task Agent — ADK agent-mode runner."""

from typing import Any, Callable, Dict, Optional

from loguru import logger

from adk.runner import load_prompt, run_agent
from db import ensure_execution_task_dirs, ensure_sandbox_dir
from adk.bridge import prepare_api_env
from shared.constants import TASK_AGENT_MAX_TURNS

from agents.task.tools import TOOLS, execute_tool


async def run(
    *, task_id, description, input_spec, output_spec, resolved_inputs,
    api_config, abort_event, on_thinking, idea_id, plan_id,
    execution_run_id, docker_container_name, validation_spec,
    idea_context, execution_context, on_prompt_built,
):
    logger.info("Task: agent mode task_id={}", task_id)
    prepare_api_env(api_config)

    if idea_id and plan_id and task_id and execution_run_id:
        await ensure_execution_task_dirs(execution_run_id, task_id)
    elif idea_id and plan_id and task_id:
        await ensure_sandbox_dir(idea_id, plan_id, task_id)

    output_format = output_spec.get("format") or ""
    output_type = (output_spec.get("type") or "markdown").strip().lower()
    on_thinking_fn = on_thinking or (lambda *a, **_: None)

    task_output: list = [None]

    async def executor_fn(name: str, args_str: str) -> tuple[bool, str]:
        out, tool_result = await execute_tool(
            name, args_str, idea_id, plan_id, task_id,
            execution_run_id=execution_run_id,
            docker_container_name=docker_container_name,
            output_format=output_format,
        )
        if out is not None:
            task_output[0] = out
            return True, '{"status": "success", "message": "Task completed."}'
        return False, tool_result

    system_prompt = load_prompt("agents", "task-agent-prompt.txt")

    parts = [
        f"**Task ID:** {task_id}",
        f"**Description:** {description}",
        f"**Output type:** {output_type}",
        f"**Output format:** {output_format}",
    ]
    if input_spec.get("description"):
        parts.append(f"**Input:** {input_spec['description']}")
    if input_spec.get("artifacts"):
        parts.append(f"**Input artifacts:** {', '.join(str(a) for a in input_spec['artifacts'])}")
    if output_spec.get("description"):
        parts.append(f"**Output description:** {output_spec['description']}")
    if validation_spec and validation_spec.get("criteria"):
        parts.append("**Validation criteria:**\n" + "\n".join(f"- {c}" for c in validation_spec["criteria"]))
    if idea_context:
        parts.append(f"**Research context:** {idea_context[:500]}")
    if execution_context and isinstance(execution_context, dict):
        retry = execution_context.get("retryMemory")
        if isinstance(retry, dict) and retry:
            fail = str(retry.get("lastFailure") or "").strip()
            if fail:
                parts.append(f"**RETRY — last failure you must avoid:**\n{fail}")
    parts.append("\nUse ReadArtifact to fetch dependency outputs. Call Finish when done.")

    user_message = "\n".join(parts)

    if on_prompt_built:
        payload = {"taskId": task_id, "outputFormat": output_format,
                   "systemPrompt": system_prompt, "userMessage": user_message}
        maybe = on_prompt_built(payload)
        if hasattr(maybe, "__await__"):
            await maybe

    await run_agent(
        name="task", prompt=system_prompt, user_message=user_message,
        tools=TOOLS, executor_fn=executor_fn, api_config=api_config,
        max_turns=TASK_AGENT_MAX_TURNS, finish_tool="Finish", operation="Execute",
        on_thinking=on_thinking_fn, abort_event=abort_event, task_id=task_id,
    )

    if task_output[0] is not None:
        return task_output[0]
    raise ValueError(f"Agent reached max turns ({TASK_AGENT_MAX_TURNS}) without calling Finish")
