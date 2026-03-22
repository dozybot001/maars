"""Dependency container for ExecutionRunner.

All external callables that the runner needs are collected here, eliminating
the _runner_module() lazy-import hack and making dependencies explicit and
injectable for testing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set


@dataclass
class RunnerDeps:
    # Worker pool
    assign_task: Callable[[str], Optional[str]] = None
    release_worker: Callable[[str], Optional[str]] = None
    set_worker_status: Callable[[str, str], None] = None
    initialize_workers: Callable[..., None] = None
    get_worker_stats: Callable[[], Dict] = None

    # Artifact resolution
    resolve_artifacts: Callable[..., Awaitable[Dict[str, Any]]] = None

    # Execution
    run_task_agent: Callable[..., Awaitable[Any]] = None
    execute_task: Callable[..., Awaitable[Any]] = None

    # Docker
    ensure_execution_container: Callable[..., Awaitable[Dict]] = None
    stop_execution_container: Callable[..., Awaitable[None]] = None
    prepare_execution_runtime: Callable[..., Awaitable[Dict]] = None
    get_local_docker_status: Callable[..., Awaitable[Dict]] = None

    # DB persistence
    save_task_artifact: Callable[..., Awaitable[Any]] = None
    delete_task_artifact: Callable[..., Awaitable[Any]] = None
    save_validation_report: Callable[..., Awaitable[Any]] = None
    save_execution: Callable[..., Awaitable[Any]] = None
    get_idea: Callable[..., Awaitable[Optional[Dict]]] = None
    delete_task_attempt_memories: Callable[..., Awaitable[Any]] = None
    save_task_attempt_memory: Callable[..., Awaitable[Any]] = None
    list_task_attempt_memories: Callable[..., Awaitable[List]] = None

    # Validation
    validate_task_output: Callable[..., Awaitable[tuple]] = None
    review_contract_adjustment: Callable[..., Awaitable[Dict]] = None

    # Utilities
    chunk_string: Callable[..., Any] = None
    SKILLS_ROOT: Any = None
    MOCK_VALIDATOR_CHUNK_DELAY: float = 0.03


def build_default_deps() -> RunnerDeps:
    """Build RunnerDeps with real implementations. All imports are localized here."""
    from db import (
        delete_task_artifact,
        delete_task_attempt_memories,
        get_idea,
        list_task_attempt_memories,
        save_execution,
        save_task_artifact,
        save_task_attempt_memory,
        save_validation_report,
    )
    from shared.utils import chunk_string
    from validate_agent import review_contract_adjustment

    from mode import run_task
    from .task_context import TaskContext

    async def run_task_via_ctx(ctx: TaskContext):
        return await run_task(
            task_id=ctx.task_id, description=ctx.description,
            input_spec=ctx.input_spec, output_spec=ctx.output_spec,
            resolved_inputs=ctx.resolved_inputs, api_config=ctx.api_config,
            abort_event=ctx.abort_event, on_thinking=ctx.on_thinking,
            idea_id=ctx.idea_id, plan_id=ctx.plan_id,
            execution_run_id=ctx.execution_run_id,
            docker_container_name=ctx.docker_container_name,
            validation_spec=ctx.validation_spec,
            idea_context=ctx.idea_context,
            execution_context=ctx.execution_context,
            on_prompt_built=ctx.on_prompt_built,
        )
    from .agent_tools import SKILLS_ROOT
    from .artifact_resolver import resolve_artifacts
    from .docker_runtime import (
        ensure_execution_container,
        get_local_docker_status,
        prepare_execution_runtime,
        stop_execution_container,
    )
    from llm.task import validate_task_output_with_readonly_agent
    from .pools import worker_manager

    import os

    def _env_float(name: str, default: float) -> float:
        raw = os.getenv(name)
        if raw is None or raw == "":
            return default
        try:
            return float(raw)
        except ValueError:
            return default

    return RunnerDeps(
        assign_task=worker_manager["assign_task"],
        release_worker=worker_manager["release_worker_by_task_id"],
        set_worker_status=worker_manager["set_worker_status"],
        initialize_workers=worker_manager["initialize_workers"],
        get_worker_stats=worker_manager.get("get_worker_stats"),
        resolve_artifacts=resolve_artifacts,
        run_task_agent=run_task_via_ctx,
        execute_task=run_task_via_ctx,
        ensure_execution_container=ensure_execution_container,
        stop_execution_container=stop_execution_container,
        prepare_execution_runtime=prepare_execution_runtime,
        get_local_docker_status=get_local_docker_status,
        save_task_artifact=save_task_artifact,
        delete_task_artifact=delete_task_artifact,
        save_validation_report=save_validation_report,
        save_execution=save_execution,
        get_idea=get_idea,
        delete_task_attempt_memories=delete_task_attempt_memories,
        save_task_attempt_memory=save_task_attempt_memory,
        list_task_attempt_memories=list_task_attempt_memories,
        validate_task_output=validate_task_output_with_readonly_agent,
        review_contract_adjustment=review_contract_adjustment,
        chunk_string=chunk_string,
        SKILLS_ROOT=SKILLS_ROOT,
        MOCK_VALIDATOR_CHUNK_DELAY=_env_float("MAARS_MOCK_VALIDATOR_CHUNK_DELAY", 0.03),
    )
