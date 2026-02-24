"""Graph utilities for task dependencies."""

from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx


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
