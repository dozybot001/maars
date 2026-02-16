"""
Task cache module
Cache: task_id, dependencies (status for execution). Stage from backend. Db unchanged.
"""

from typing import List, Dict, Optional

from tasks.task_stages import compute_task_stages

_plan_cache: Dict[str, List[Dict]] = {}


def extract_cache_from_task(task: Optional[Dict]) -> Optional[Dict]:
    if not task or not task.get("task_id"):
        return None
    return {
        "task_id": task["task_id"],
        "dependencies": list(task.get("dependencies") or []),
    }


def extract_cache_from_tasks(tasks: List[Dict]) -> List[Dict]:
    if not tasks or not isinstance(tasks, list):
        return []
    return [
        {
            "task_id": t.get("task_id") or "",
            "dependencies": list(t.get("dependencies") or []),
            "status": t.get("status") or "undone",
        }
        for t in tasks
        if t.get("task_id")
    ]


def get_plan_cache(plan_id: str) -> List[Dict]:
    return _plan_cache.get(plan_id, [])


def append_plan_cache(plan_id: str, task: Dict) -> None:
    entry = extract_cache_from_task(task)
    if not entry:
        return
    cache = _plan_cache.setdefault(plan_id, [])
    idx = next((i for i, c in enumerate(cache) if c.get("task_id") == entry["task_id"]), -1)
    if idx >= 0:
        cache[idx] = entry
    else:
        cache.append(entry)


def clear_plan_cache(plan_id: str) -> None:
    if plan_id in _plan_cache:
        del _plan_cache[plan_id]


def compute_staged(cache_entries: List[Dict]) -> List[List[Dict]]:
    if not cache_entries or len(cache_entries) == 0:
        return []
    return compute_task_stages(cache_entries)


def enrich_tree_data(staged: List[List[Dict]], full_tasks: List[Dict]) -> List[Dict]:
    by_id = {t["task_id"]: t for t in (full_tasks or []) if t.get("task_id")}
    result = []
    for stage in staged:
        for c in stage:
            full = by_id.get(c["task_id"], {})
            result.append({**full, **c})
    return result


def build_tree_data(tasks: List[Dict]) -> List[Dict]:
    """Build flat treeData from tasks: extract cache -> compute stage -> enrich with full data."""
    if not tasks or len(tasks) == 0:
        return []
    cache = extract_cache_from_tasks(tasks)
    staged = compute_staged(cache)
    return enrich_tree_data(staged, tasks)
