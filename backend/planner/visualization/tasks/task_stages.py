"""
Unified task stages module.
Single source: compute stages from flat task list. Does not modify original data.
Uses shared.graph.build_dependency_graph, networkx for topological sort and transitive reduction.
"""

from typing import List, Dict

import networkx as nx

from shared.graph import build_dependency_graph


def _reduce_dependencies(G: nx.DiGraph, stages: List[List[Dict]]) -> List[List[Dict]]:
    """
    Transitive reduction: remove edges that are implied by other paths.
    E.g. if A→B→C exists, the direct edge A→C is redundant and removed.
    Keeps the minimal edge set that preserves the same reachability.
    """
    G_reduced = nx.transitive_reduction(G)
    reduced_edges = set(G_reduced.edges())

    return [
        [
            {**t, "dependencies": [d for d in t.get("dependencies", []) if (d, t["task_id"]) in reduced_edges]}
            for t in stage
        ]
        for stage in stages
    ]


def compute_task_stages(
    tasks: List[Dict],
    reduce: bool = False,
) -> List[List[Dict]]:
    """
    Compute staged format from flat task list. No old stage data used.

    reduce=True:  display/tree view — transitive reduction, minimal edges.
    reduce=False: execution scheduling — keep all deps as-is.

    Returns [[stage0_tasks], [stage1_tasks], ...], each task has stage (1-based).
    """
    if not tasks or not isinstance(tasks, list) or len(tasks) == 0:
        return []

    task_list = [
        {**t, "task_id": t.get("task_id") or str(idx + 1), "dependencies": list(t.get("dependencies") or [])}
        for idx, t in enumerate(tasks)
    ]
    task_by_id = {t["task_id"]: t for t in task_list}

    G = build_dependency_graph(task_list)

    if not nx.is_directed_acyclic_graph(G):
        raise ValueError("Circular dependency detected in task graph")

    stages: List[List[Dict]] = []
    for level in nx.topological_generations(G):
        stage_tasks = [task_by_id[nid] for nid in level if nid in task_by_id]
        if stage_tasks:
            stages.append([{**t} for t in stage_tasks])

    final_stages = _reduce_dependencies(G, stages) if reduce else stages

    return [
        [{**task, "stage": idx + 1} for task in stage]
        for idx, stage in enumerate(final_stages)
    ]
