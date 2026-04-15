"""Task decomposition: recursively break an idea into atomic tasks with a dependency DAG."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Callable

from backend.utils import parse_json_fenced
from backend.pipeline.prompts import build_decompose_system, build_decompose_user


@dataclass
class Task:
    id: str
    description: str
    dependencies: list[str] = field(default_factory=list)
    is_atomic: bool | None = None
    children: list[str] = field(default_factory=list)


async def decompose(
    idea: str,
    stream_fn: Callable,
    max_depth: int = 10,
    atomic_definition: str = "",
    strategy: str = "",
    on_judge_done: Callable | None = None,
    is_stale: Callable[[], bool] | None = None,
    context: str = "",
    root_siblings: list[dict] | None = None,
    root_id: str = "0",
) -> tuple[list[dict], dict]:
    system_prompt = build_decompose_system(atomic_definition, strategy)
    progress_fn = on_judge_done or (lambda tree: None)
    stale = is_stale or (lambda: False)
    ctx = context or idea

    tasks: dict[str, Task] = {}
    pending: list[str] = []

    root = Task(id=root_id, description=idea)
    tasks[root_id] = root
    pending.append(root_id)

    while pending:
        if stale():
            break
        batch = list(pending)
        pending.clear()
        await asyncio.gather(*[
            _process_task(tid, tasks, pending, ctx, system_prompt,
                          max_depth, stream_fn, progress_fn, stale,
                          root_id, root_siblings)
            for tid in batch
        ])

    tree = _serialize_tree(tasks, root_id)
    flat_tasks = _finalize(tasks, root_id)
    return flat_tasks, tree


async def _process_task(task_id, tasks, pending, context, system_prompt,
                        max_depth, stream_fn, progress_fn, stale,
                        root_id="0", root_siblings=None):
    task = tasks[task_id]
    depth = _depth(task_id, root_id)
    if depth >= max_depth:
        task.is_atomic = True
        progress_fn(_serialize_tree(tasks, root_id))
        return

    is_root = task_id == root_id
    call_id = f"Judge {task_id}"
    label_level = 3
    content_level = label_level + 1

    siblings = root_siblings if is_root and root_siblings else _get_siblings(task_id, tasks, root_id)
    extra_kw = {} if is_root else {"tools": []}
    response = await stream_fn(
        system_prompt, build_decompose_user(task.id, task.description, context, siblings),
        call_id, content_level, label=True, label_level=label_level, **extra_kw,
    )

    data = parse_json_fenced(response, fallback={"is_atomic": True})

    if data.get("is_atomic", True):
        task.is_atomic = True
        progress_fn(_serialize_tree(tasks, root_id))
        return

    subtasks = data.get("subtasks", [])
    if not subtasks or not all("id" in st and "description" in st for st in subtasks):
        task.is_atomic = True
        progress_fn(_serialize_tree(tasks, root_id))
        return

    task.is_atomic = False
    for st in subtasks:
        child_id = st["id"] if is_root and root_id == "0" else f"{task_id}_{st['id']}"
        child_deps = [
            d if is_root and root_id == "0" else f"{task_id}_{d}"
            for d in st.get("dependencies", [])
        ]
        child = Task(id=child_id, description=st["description"], dependencies=child_deps)
        tasks[child_id] = child
        task.children.append(child_id)
        pending.append(child_id)

    progress_fn(_serialize_tree(tasks, root_id))


def _depth(task_id: str, root_id: str) -> int:
    """Compute depth relative to root."""
    if task_id == root_id:
        return 0
    if root_id == "0":
        return len(task_id.split("_"))
    # Verify task_id is actually a descendant (must start with root_id + "_")
    prefix = root_id + "_"
    if not task_id.startswith(prefix):
        return 0
    return len(task_id[len(root_id):].split("_")) - 1


def _get_siblings(task_id: str, tasks: dict[str, Task], root_id: str = "0") -> list[dict]:
    """Return sibling tasks (same parent, excluding self)."""
    if task_id == root_id:
        return []
    parts = task_id.rsplit("_", 1)
    parent_id = parts[0] if len(parts) > 1 else root_id
    parent = tasks.get(parent_id)
    if not parent:
        return []
    return [
        {"id": tasks[cid].id, "description": tasks[cid].description}
        for cid in parent.children
        if cid != task_id and cid in tasks
    ]


def _finalize(tasks, root_id="0"):
    atomic_tasks = {tid: t for tid, t in tasks.items() if t.is_atomic}
    resolved = _resolve_dependencies(tasks, atomic_tasks, root_id)
    return [
        {"id": tid, "description": atomic_tasks[tid].description, "dependencies": deps}
        for tid, deps in resolved.items()
    ]


def _serialize_tree(tasks, root_id="0"):
    def build_node(task_id):
        task = tasks.get(task_id)
        if not task:
            return None
        return {
            "id": task.id, "description": task.description,
            "dependencies": task.dependencies, "is_atomic": task.is_atomic,
            "children": [build_node(cid) for cid in task.children],
        }
    return build_node(root_id) or {}


def _resolve_dependencies(all_tasks, atomic_tasks, root_id="0"):
    resolved = {}
    for tid in atomic_tasks:
        collected = set()
        for ancestor_id in _ancestor_chain(tid, root_id):
            ancestor = all_tasks.get(ancestor_id)
            if ancestor:
                collected.update(ancestor.dependencies)
        collected.update(all_tasks[tid].dependencies)
        expanded = set()
        for dep_id in collected:
            if dep_id in atomic_tasks:
                expanded.add(dep_id)
            else:
                expanded.update(_get_atomic_descendants(all_tasks, dep_id, atomic_tasks))
        expanded.discard(tid)
        resolved[tid] = sorted(expanded)
    return resolved


def _ancestor_chain(task_id, root_id="0"):
    parts = task_id.split("_")
    ancestors = []
    for i in range(len(parts) - 1, 0, -1):
        candidate = "_".join(parts[:i])
        ancestors.append(candidate)
        if candidate == root_id:
            break
    else:
        if root_id not in ancestors:
            ancestors.append(root_id)
    return ancestors


def _get_atomic_descendants(all_tasks, task_id, atomic_tasks):
    result = set()
    task = all_tasks.get(task_id)
    if not task:
        return result
    if task_id in atomic_tasks:
        result.add(task_id)
        return result
    for child_id in task.children:
        result.update(_get_atomic_descendants(all_tasks, child_id, atomic_tasks))
    return result
