"""
Task pipeline: build_tree_data(tasks) for display/save.
Plan.tasks is the single source; pipeline output overwrites for render and persist.

Pipeline (each run, no old stage reused):
  1. Extract: task_id, dependencies (never stage)
  2. Sink: 依赖下沉
  3. Stage: 重新计算 stage (topological sort)
  4. Clean: 依赖清洗 (跨 stage 依赖，保险步骤)
  5. Enrich: 合并完整 task 信息
"""

from typing import List, Dict

from tasks.task_stages import compute_task_stages


def extract_cache_from_tasks(tasks: List[Dict]) -> List[Dict]:
    """Extract task_id, dependencies. Never stage (always recompute)."""
    if not tasks or not isinstance(tasks, list):
        return []
    return [
        {
            "task_id": t.get("task_id") or "",
            "dependencies": list(t.get("dependencies") or []),
        }
        for t in tasks
        if t.get("task_id")
    ]


def enrich_tree_data(staged: List[List[Dict]], full_tasks: List[Dict]) -> List[Dict]:
    by_id = {t["task_id"]: t for t in (full_tasks or []) if t.get("task_id")}
    result = []
    for stage in staged:
        for c in stage:
            full = by_id.get(c["task_id"], {})
            result.append({**full, **c})
    return result


def build_tree_data(tasks: List[Dict]) -> List[Dict]:
    """
    Build treeData from tasks. Never uses old stage.
    Pipeline: extract (no stage) -> sink -> recompute stage -> clean deps -> enrich.
    """
    if not tasks or len(tasks) == 0:
        return []
    cache = extract_cache_from_tasks(tasks)
    staged = compute_task_stages(cache)
    return enrich_tree_data(staged, tasks)
