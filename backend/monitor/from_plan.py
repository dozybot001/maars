"""
Generate execution from plan: extract atomic tasks, clean dependencies, recompute stages.
"""

from typing import Dict, List, Set


def _is_atomic(task: Dict) -> bool:
    """Task is atomic if it has both input and output (formatted by planner)."""
    return bool(task.get("input") and task.get("output"))


def _get_transitive_atomic_deps(
    dep_id: str,
    task_map: Dict[str, Dict],
    atomic_ids: Set[str],
    visited: Set[str],
) -> List[str]:
    """Get atomic task_ids that dep_id transitively depends on."""
    if dep_id in visited:
        return []
    visited.add(dep_id)
    if dep_id in atomic_ids:
        return [dep_id]
    task = task_map.get(dep_id)
    if not task:
        return []
    result = []
    for d in task.get("dependencies") or []:
        result.extend(_get_transitive_atomic_deps(d, task_map, atomic_ids, visited))
    return result


def _clean_dependencies_for_atomic(
    tasks: List[Dict],
    atomic_tasks: List[Dict],
    task_map: Dict[str, Dict],
) -> List[Dict]:
    """Clean dependencies: remove non-atomic deps, replace with transitive atomic deps."""
    atomic_ids = {t["task_id"] for t in atomic_tasks}
    result = []
    for t in atomic_tasks:
        deps = t.get("dependencies") or []
        new_deps = []
        seen = set()
        for dep_id in deps:
            if dep_id in atomic_ids:
                if dep_id not in seen:
                    new_deps.append(dep_id)
                    seen.add(dep_id)
            else:
                for aid in _get_transitive_atomic_deps(dep_id, task_map, atomic_ids, set()):
                    if aid not in seen:
                        new_deps.append(aid)
                        seen.add(aid)
        result.append({**t, "dependencies": new_deps})
    return result


def build_execution_from_plan(plan: Dict) -> Dict:
    """
    Extract atomic tasks from plan, clean dependencies, recompute stages.
    Returns execution dict with tasks (each has status: "undone").
    """
    all_tasks = plan.get("tasks") or []
    if not all_tasks:
        return {"tasks": []}

    atomic_tasks = [t for t in all_tasks if _is_atomic(t)]
    if not atomic_tasks:
        return {"tasks": []}

    task_map = {t["task_id"]: t for t in all_tasks if t.get("task_id")}
    cleaned = _clean_dependencies_for_atomic(all_tasks, atomic_tasks, task_map)

    from tasks.task_stages import compute_task_stages  # lazy to avoid circular import when run standalone
    staged = compute_task_stages(cleaned)
    flat = []
    for stage_list in staged:
        for task in stage_list:
            flat.append({**task, "status": "undone"})
    return {"tasks": flat}
