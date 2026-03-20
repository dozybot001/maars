"""TaskContext: packs the parameters for run_task_agent into a single object."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from shared.utils import OnThinking


@dataclass
class TaskContext:
    """All context needed to execute a single task via Task Agent."""

    # Required
    task_id: str
    description: str
    input_spec: Dict[str, Any]
    output_spec: Dict[str, Any]
    resolved_inputs: Dict[str, Any]
    api_config: Dict[str, Any]
    idea_id: str
    plan_id: str

    # Optional
    abort_event: Optional[Any] = None
    on_thinking: OnThinking = None
    execution_run_id: str = ""
    docker_container_name: str = ""
    validation_spec: Optional[Dict[str, Any]] = None
    idea_context: str = ""
    execution_context: Optional[Dict[str, Any]] = None
    on_prompt_built: Optional[Callable[[Dict[str, Any]], Any]] = None
