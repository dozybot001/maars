"""
Monitor Module
Builds layout from execution, generates execution from plan.
"""

import json
from typing import Any, Dict, List

from layout import compute_monitor_layout
from monitor.timetable import build_task_layout
from tasks.task_cache import build_tree_data

from .from_plan import build_execution_from_plan


def _group_by_stage(tree_data: List[Dict]) -> List[List[Dict]]:
    stage_map: Dict[int, List[Dict]] = {}
    for t in tree_data or []:
        idx = (t.get("stage") or 1) - 1
        if idx not in stage_map:
            stage_map[idx] = []
        stage_map[idx].append(t)
    return [stage_map[k] for k in sorted(stage_map.keys())]


def build_layout_from_execution(execution: Any) -> Dict:
    """Build layout from execution. Returns { grid, treeData, layout, ... }."""
    exec_data = execution
    if isinstance(execution, str):
        try:
            exec_data = json.loads(execution)
        except json.JSONDecodeError:
            raise ValueError("Invalid execution format")

    full_tasks = exec_data.get("tasks") if isinstance(exec_data.get("tasks"), list) else []
    if not full_tasks:
        return {"treeData": [], "layout": None, "grid": [], "maxRows": 0, "maxCols": 0, "isolatedTasks": []}

    tree_data = build_tree_data(full_tasks)
    staged = _group_by_stage(tree_data)
    result = build_task_layout(staged)
    result["layout"] = compute_monitor_layout(result.get("treeData") or tree_data)
    return result
