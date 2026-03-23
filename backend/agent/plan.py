"""Plan stage using ADK Agent — decomposes idea into atomic tasks."""

import json
import re

from backend.agent.base import AgentStage
from backend.pipeline.plan import (
    Task,
    _resolve_dependencies,
    _ancestor_chain,
    _get_atomic_descendants,
    _parse_json,
)

_PLAN_INSTRUCTION = """\
You are a research project planner in a fully automated LLM pipeline (MAARS).
No human is in the loop. Make all decisions autonomously.

Your job: decompose a research idea into a flat list of atomic tasks with dependencies.

An atomic task is one that a single focused LLM call can produce a reliable, complete text result for.
There is NO access to internet, code execution, or external tools.
All tasks must be completable through text-based reasoning and analysis alone.

Output ONLY a JSON array of atomic tasks:
[
  {"id": "1", "description": "...", "dependencies": []},
  {"id": "2", "description": "...", "dependencies": ["1"]},
  ...
]

Rules:
- Each task should be specific and actionable
- Dependencies reference other task IDs
- Aim for 10-20 atomic tasks total
- Prefer coarser tasks over many fine-grained ones
- No circular dependencies"""


class PlanAgentStage(AgentStage):
    """Agent-based plan decomposition."""

    def __init__(self, tools: list = None, **kwargs):
        super().__init__(
            name="plan",
            instruction=_PLAN_INSTRUCTION,
            tools=tools or [],
            **kwargs,
        )
        self._tasks_data: list[dict] = []

    def finalize_agent(self, final_text: str) -> str:
        """Parse the agent's output as a JSON task list."""
        data = _parse_json(final_text)

        # Agent might return a dict with a key, or directly an array
        if isinstance(data, dict):
            tasks = data.get("tasks", data.get("subtasks", []))
        elif isinstance(data, list):
            tasks = data
        else:
            tasks = []

        self._tasks_data = tasks

        # Emit tree for frontend
        self._emit("tree", self._build_tree_view(tasks))

        return json.dumps(tasks, indent=2, ensure_ascii=False)

    def _build_tree_view(self, tasks: list[dict]) -> dict:
        """Build a simple tree for frontend rendering."""
        children = []
        for t in tasks:
            children.append({
                "id": t.get("id", "?"),
                "description": t.get("description", ""),
                "dependencies": t.get("dependencies", []),
                "is_atomic": True,
                "children": [],
            })
        return {
            "id": "0",
            "description": "Research Plan",
            "dependencies": [],
            "is_atomic": False,
            "children": children,
        }

    def get_artifacts(self) -> dict | None:
        return self._build_tree_view(self._tasks_data)

    def retry(self):
        super().retry()
        self._tasks_data = []
