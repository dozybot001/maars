"""
Plan visualization - Decomposition Tree, Execution Graph.

Builds layout from execution, generates execution from plan.
All layout and visualization logic consolidated here.
"""

import json
from typing import Any, Dict, List

from .decomposition_layout import compute_decomposition_layout
from .execution_layout import compute_execution_graph_layout
from .tasks.tree_data import build_tree_data
from .execution_builder import build_execution_from_plan

__all__ = [
    "build_layout_from_execution",
    "build_execution_from_plan",
    "compute_decomposition_layout",
    "compute_execution_graph_layout",
]


def build_layout_from_execution(execution: Any) -> Dict:
    """Build layout from execution. Returns { treeData, layout } for execution graph."""
    exec_data = execution
    if isinstance(execution, str):
        try:
            exec_data = json.loads(execution)
        except json.JSONDecodeError:
            raise ValueError("Invalid execution format")

    full_tasks = exec_data.get("tasks") if isinstance(exec_data.get("tasks"), list) else []
    if not full_tasks:
        return {"treeData": [], "layout": None}

    tree_data = build_tree_data(full_tasks)
    layout = compute_execution_graph_layout(tree_data)
    return {"treeData": tree_data, "layout": layout}
