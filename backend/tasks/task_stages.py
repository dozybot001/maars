"""
Unified task stages module
Single source: clean dependencies + compute stages. Does not modify original data.
Uses networkx for topological sort and cycle detection.
"""

import re
from typing import List, Dict

import networkx as nx

from monitor.timetable import clean_dependencies


def _is_in_subtree(task_id: str, parent_id: str) -> bool:
    if not task_id or not parent_id:
        return False
    if parent_id == "0":
        return bool(re.match(r"^[1-9]\d*$", task_id))
    return task_id.startswith(parent_id + "_")


def sink_dependencies(tasks: List[Dict]) -> List[Dict]:
    """
    Sink dependencies: when parent task is decomposed, dependencies pointing to it
    should sink to leaf tasks of its subtree.
    """
    if not tasks or not isinstance(tasks, list) or len(tasks) == 0:
        return tasks

    task_map = {t["task_id"]: {**t, "dependencies": list(t.get("dependencies") or [])} for t in tasks if t.get("task_id")}

    def get_leaf_tasks_of_subtree_inner(parent_id: str) -> List[str]:
        if parent_id == "0":
            subtasks = [t for t in tasks if t.get("task_id") and re.match(r"^[1-9]\d*$", t["task_id"])]
        else:
            subtasks = [t for t in tasks if t.get("task_id") and t["task_id"].startswith(parent_id + "_")]
        if not subtasks:
            return []

        depended_on = set()
        for t in subtasks:
            for dep_id in (t.get("dependencies") or []):
                if dep_id:
                    if parent_id == "0" and re.match(r"^[1-9]\d*$", dep_id):
                        depended_on.add(dep_id)
                    elif parent_id != "0" and dep_id.startswith(parent_id + "_"):
                        depended_on.add(dep_id)

        return [t["task_id"] for t in subtasks if t["task_id"] not in depended_on]

    for task in task_map.values():
        deps = task.get("dependencies") or []
        sunk = []
        for dep_id in deps:
            if not dep_id or not isinstance(dep_id, str):
                continue
            if _is_in_subtree(task["task_id"], dep_id):
                sunk.append(dep_id)
                continue
            leaves = get_leaf_tasks_of_subtree_inner(dep_id)
            if leaves:
                sunk.extend(leaves)
            else:
                sunk.append(dep_id)
        task["dependencies"] = sunk

    return list(task_map.values())


def compute_task_stages(tasks: List[Dict]) -> List[List[Dict]]:
    """
    Compute staged format from flat tasks. No old stage data used.
    Order: 1) 依赖下沉 2) 重新计算 stage (topological sort) 3) 依赖清洗 (跨 stage，保险)
    Returns [[stage0_tasks], [stage1_tasks], ...], each task has stage (1-based)
    """
    if not tasks or not isinstance(tasks, list) or len(tasks) == 0:
        return []

    resolved = sink_dependencies(tasks)
    task_list = [
        {**t, "task_id": t.get("task_id") or str(idx + 1), "dependencies": list(t.get("dependencies") or [])}
        for idx, t in enumerate(resolved)
    ]
    task_by_id = {t["task_id"]: t for t in task_list}

    G = nx.DiGraph()
    for t in task_list:
        G.add_node(t["task_id"])
        for dep in t["dependencies"]:
            if dep in task_by_id:
                G.add_edge(dep, t["task_id"])

    if not nx.is_directed_acyclic_graph(G):
        raise ValueError("Circular dependency detected in task graph")

    stages: List[List[Dict]] = []
    for level in nx.topological_generations(G):
        stage_tasks = [task_by_id[nid] for nid in level if nid in task_by_id]
        if stage_tasks:
            stages.append([{**t} for t in stage_tasks])

    cleaned_stages = clean_dependencies(stages)
    return [
        [{**task, "stage": idx + 1} for task in stage]
        for idx, stage in enumerate(cleaned_stages)
    ]
