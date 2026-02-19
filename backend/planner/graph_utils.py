"""
Graph utilities for planner: cycle detection in decompose validation.
Uses networkx. Kept in planner to avoid circular imports with tasks/monitor.
"""

from typing import List, Dict, Set

import networkx as nx


def has_cycle_in_subset(tasks: List[Dict], valid_ids: Set[str]) -> bool:
    """Check for cycles in task dependency graph (only within valid_ids)."""
    by_id = {t["task_id"]: t for t in tasks if t.get("task_id") in valid_ids}
    if not by_id:
        return False
    G = nx.DiGraph()
    for t in tasks:
        tid = t.get("task_id")
        if tid not in by_id:
            continue
        G.add_node(tid)
        for dep in t.get("dependencies") or []:
            if dep in valid_ids and dep != tid and dep in by_id:
                G.add_edge(dep, tid)
    return not nx.is_directed_acyclic_graph(G)
