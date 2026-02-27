"""
Build treeData from staged tasks (for execution graph layout).
"""

from typing import Dict, List


def build_task_layout(task_stages: List[List[Dict]]) -> Dict:
    """
    Build treeData from staged tasks.
    Returns { treeData } for execution graph.
    """
    if not task_stages:
        return {"treeData": []}
    tree_data = []
    for stage in task_stages:
        for task in stage:
            tree_data.append({**task, "stage": task.get("stage", 1)})
    return {"treeData": tree_data}
