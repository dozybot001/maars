"""Graph utilities for task dependencies and task_id hierarchy."""

from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx


def get_parent_id(task_id: str) -> str:
    """Get parent task_id. E.g. '1_2' -> '1', '1' -> '0'."""
    if "_" in task_id:
        return task_id.rsplit("_", 1)[0]
    return "0"


def get_ancestor_chain(task_id: str) -> List[str]:
    """Return ancestor ids from immediate parent up to root, e.g. '1_2_3' -> ['1_2', '1', '0']."""
    chain = []
    curr = task_id
    while True:
        parent = get_parent_id(curr)
        chain.append(parent)
        if parent == "0":
            break
        curr = parent
    return chain


def get_ancestor_path(task_id: str) -> str:
    """Build ancestor path string, e.g. '1_2' -> '0 → 1 → 1_2'."""
    if not task_id:
        return ""
    parts = []
    curr = task_id
    while True:
        parts.insert(0, curr)
        if curr == "0":
            break
        curr = get_parent_id(curr)
    return " → ".join(parts)


def natural_task_id_key(tid: str) -> Tuple:
    """Sort key: '1' < '1_1' < '1_2' < '1_10'."""
    parts = tid.split("_")
    return tuple(int(p) if p.isdigit() else p for p in parts)


def build_dependency_graph(tasks: List[Dict[str, Any]], ids: Optional[Set[str]] = None) -> nx.DiGraph:
    """Build dependency graph from tasks. ids: if provided, only include nodes in ids."""
    ids = ids or {t["task_id"] for t in (tasks or []) if t.get("task_id")}
    G = nx.DiGraph()
    for t in tasks or []:
        tid = t.get("task_id")
        if not tid or tid not in ids:
            continue
        G.add_node(tid)
        for dep in t.get("dependencies") or []:
            if dep in ids and dep != tid:
                G.add_edge(dep, tid)
    return G
