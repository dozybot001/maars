"""Task decomposition: recursively break an idea into atomic tasks with a dependency DAG."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Callable

from backend.utils import parse_json_fenced

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Task:
    id: str
    description: str
    dependencies: list[str] = field(default_factory=list)  # sibling-level IDs
    is_atomic: bool | None = None  # None = not yet judged
    children: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_TEMPLATE = """\
You are a research project planner. Given a task, decide whether it is atomic (executable as-is) or needs decomposition into subtasks.

CONTEXT: This is an automated research pipeline.
- Each atomic task is executed independently by an AI agent.
- A separate WRITE stage synthesizes all outputs into the final paper.
- Therefore: do NOT create "write paper" or "compile report" tasks.
- No human is in the loop. Make all decisions autonomously.

{atomic_definition}

{strategy}

WHEN TO STOP DECOMPOSING:
- A task is atomic when it produces ONE clear, verifiable deliverable: a single file, score, plot, cleaned dataset, or focused analysis.
- Err on the side of SMALLER, MORE RELIABLE tasks. It is better to have many tasks that each reliably succeed than fewer tasks that are ambitious but fragile.
- Decompose when a task has multiple independent deliverables, distinct reasoning steps, or when failure of one part would waste the work of other parts.
- Do NOT merge tasks just because they seem "related". If they produce different artifacts, they should be separate tasks.
- A task that requires more than 2-3 code_execute calls to complete is likely too large.

Rules for subtasks:
- Dependencies are ONLY between sibling subtasks (same parent).
- A subtask can only depend on earlier siblings (no circular dependencies).
- Subtask IDs are simple integers: "1", "2", "3", ...
- Task descriptions must be specific and actionable: state what output is expected.
- MAXIMIZE PARALLELISM: only add a dependency when a task truly CANNOT start without the other's output.

Respond with ONLY a JSON object (no markdown fencing, no extra text):

If atomic:
{{"is_atomic": true}}

If decomposing:
{{"is_atomic": false, "subtasks": [{{"id": "1", "description": "...", "dependencies": []}}, {{"id": "2", "description": "...", "dependencies": []}}, {{"id": "3", "description": "...", "dependencies": ["1"]}}]}}"""

def _build_user_prompt(task: Task, context: str) -> str:
    parts = [f"Research idea context:\n{context}\n"]
    if task.id == "0":
        parts.append("Judge whether this research idea can be executed as a single atomic task, or needs decomposition into subtasks.")
    else:
        parts.append(f"Task [{task.id}]: {task.description}")
        parts.append("Judge whether this task is atomic or needs decomposition.")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Core decompose function
# ---------------------------------------------------------------------------

async def decompose(
    idea: str,
    stream_fn: Callable,
    max_depth: int = 10,
    atomic_definition: str = "",
    strategy: str = "",
    emit: Callable | None = None,
    is_stale: Callable[[], bool] | None = None,
) -> tuple[list[dict], dict]:
    """Recursively decompose an idea into atomic tasks with a dependency DAG.

    Args:
        idea: The research idea or feedback text to decompose.
        stream_fn: async callable(messages, call_id, content_level) -> str.
            Handles LLM streaming + event dispatch uniformly.
        max_depth: Maximum recursion depth.
        atomic_definition: Custom atomic definition (e.g. for Agent mode).
        strategy: Strategy document from pre-decompose research.
        emit: Optional callback(event_type, data) for non-chunk events (tree).
        is_stale: Optional callable returning True if this run has been superseded.

    Returns:
        (flat_tasks, tree) where:
        - flat_tasks: plan_list.json format [{"id", "description", "dependencies"}, ...]
        - tree: nested tree structure for frontend visualization
    """
    strategy_block = f"STRATEGY (from prior research):\n{strategy}" if strategy else ""
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        atomic_definition=atomic_definition,
        strategy=strategy_block,
    )

    emit_fn = emit or (lambda t, d: None)
    stale = is_stale or (lambda: False)

    tasks: dict[str, Task] = {}
    pending: list[str] = []

    root = Task(id="0", description=idea)
    tasks["0"] = root
    pending.append("0")

    while pending:
        if stale():
            break

        batch = list(pending)
        pending.clear()

        coros = [
            _process_task(
                task_id=tid,
                tasks=tasks,
                pending=pending,
                context=idea,
                system_prompt=system_prompt,
                max_depth=max_depth,
                stream_fn=stream_fn,
                emit=emit_fn,
                stale=stale,
            )
            for tid in batch
        ]
        await asyncio.gather(*coros)

        if stale():
            break

        tree = _serialize_tree(tasks)
        emit_fn("tree", tree)

    tree = _serialize_tree(tasks)
    flat_tasks = _finalize(tasks)
    return flat_tasks, tree


async def _process_task(
    task_id: str,
    tasks: dict[str, Task],
    pending: list[str],
    context: str,
    system_prompt: str,
    max_depth: int,
    stream_fn: Callable,
    emit: Callable,
    stale: Callable[[], bool],
):
    """Process a single task: call LLM, parse result, update tree."""
    task = tasks[task_id]

    depth = 0 if task_id == "0" else len(task_id.split("_"))
    if depth >= max_depth:
        task.is_atomic = True
        return

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": _build_user_prompt(task, context)},
    ]

    call_id = "Decompose" if task_id == "0" else f"Judge {task_id}"
    label_level = 2 if task_id == "0" else 3
    content_level = label_level + 1

    # Emit session label, then stream via the unified stream_fn
    emit("chunk", {"text": call_id, "call_id": call_id, "label": True, "level": label_level})
    response = await stream_fn(messages, call_id, content_level)

    data = parse_json_fenced(response, fallback={"is_atomic": True})

    if data.get("is_atomic", True):
        subtasks = data.get("subtasks", [])
        if not subtasks or not all("id" in st and "description" in st for st in subtasks):
            task.is_atomic = True
            return

    task.is_atomic = False
    for st in data["subtasks"]:
        child_id = st["id"] if task_id == "0" else f"{task_id}_{st['id']}"
        child_deps = [
            d if task_id == "0" else f"{task_id}_{d}"
            for d in st.get("dependencies", [])
        ]
        child = Task(
            id=child_id,
            description=st["description"],
            dependencies=child_deps,
        )
        tasks[child_id] = child
        task.children.append(child_id)
        pending.append(child_id)


def _finalize(tasks: dict[str, Task]) -> list[dict]:
    """Resolve dependencies and return flat atomic task list."""
    atomic_tasks = {
        tid: t for tid, t in tasks.items()
        if t.is_atomic
    }
    resolved = _resolve_dependencies(tasks, atomic_tasks)
    return [
        {
            "id": tid,
            "description": atomic_tasks[tid].description,
            "dependencies": deps,
        }
        for tid, deps in resolved.items()
    ]


def _serialize_tree(tasks: dict[str, Task]) -> dict:
    """Serialize task tree from root for frontend rendering."""
    def build_node(task_id: str) -> dict | None:
        task = tasks.get(task_id)
        if not task:
            return None
        return {
            "id": task.id,
            "description": task.description,
            "dependencies": task.dependencies,
            "is_atomic": task.is_atomic,
            "children": [build_node(cid) for cid in task.children],
        }
    return build_node("0") or {}


# ---------------------------------------------------------------------------
# Dependency resolution: inherit + expand
# ---------------------------------------------------------------------------

def _resolve_dependencies(
    all_tasks: dict[str, Task],
    atomic_tasks: dict[str, Task],
) -> dict[str, list[str]]:
    """Two-step dependency resolution:
    1. Inherit: walk up ancestor chain, collect all ancestor dependencies
    2. Expand: replace non-atomic deps with their atomic descendants
    """
    resolved: dict[str, list[str]] = {}

    for tid in atomic_tasks:
        collected: set[str] = set()
        for ancestor_id in _ancestor_chain(tid):
            ancestor = all_tasks.get(ancestor_id)
            if ancestor:
                collected.update(ancestor.dependencies)
        collected.update(all_tasks[tid].dependencies)

        expanded: set[str] = set()
        for dep_id in collected:
            if dep_id in atomic_tasks:
                expanded.add(dep_id)
            else:
                expanded.update(_get_atomic_descendants(all_tasks, dep_id, atomic_tasks))

        expanded.discard(tid)
        resolved[tid] = sorted(expanded)

    return resolved


def _ancestor_chain(task_id: str) -> list[str]:
    """Return ancestor IDs from immediate parent up to root."""
    parts = task_id.split("_")
    ancestors = []
    for i in range(len(parts) - 1, 0, -1):
        ancestors.append("_".join(parts[:i]))
    ancestors.append("0")
    return ancestors


def _get_atomic_descendants(
    all_tasks: dict[str, Task],
    task_id: str,
    atomic_tasks: dict[str, Task],
) -> set[str]:
    """Recursively find all atomic descendants of a task."""
    result: set[str] = set()
    task = all_tasks.get(task_id)
    if not task:
        return result
    if task_id in atomic_tasks:
        result.add(task_id)
        return result
    for child_id in task.children:
        result.update(_get_atomic_descendants(all_tasks, child_id, atomic_tasks))
    return result
