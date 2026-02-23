"""
Task Layout Module
Builds grid layout from staged tasks.
"""

from typing import List, Dict


def build_task_layout(task_stages: List[List[Dict]]) -> Dict:
    """
    Build task layout (grid) from staged tasks.
    Returns { grid, maxRows, maxCols, isolatedTasks, treeData }
    """
    if not task_stages or len(task_stages) == 0:
        return {"grid": [], "maxRows": 0, "maxCols": 0, "isolatedTasks": [], "treeData": []}

    all_tasks: Dict[str, Dict] = {}
    task_dependents: Dict[str, List[str]] = {}

    for stage in task_stages:
        for task in stage:
            tid = task.get("task_id")
            if tid:
                all_tasks[tid] = task
                if tid not in task_dependents:
                    task_dependents[tid] = []
                for dep_id in (task.get("dependencies") or []):
                    if dep_id not in task_dependents:
                        task_dependents[dep_id] = []
                    task_dependents[dep_id].append(tid)

    dependency_tasks = []
    isolated_tasks = []

    for task_id, task in all_tasks.items():
        has_deps = bool(task.get("dependencies"))
        has_dependents = bool(task_dependents.get(task_id))
        if not has_deps and not has_dependents:
            isolated_tasks.append(task)
        else:
            dependency_tasks.append(task)

    task_positions: Dict[str, Dict] = {}
    dependency_columns: List[List[Dict]] = []
    placed_tasks = set()

    while len(placed_tasks) < len(dependency_tasks):
        current_column = []
        for task in dependency_tasks:
            if task["task_id"] in placed_tasks:
                continue
            deps = task.get("dependencies") or []
            if not deps:
                current_column.append(task)
            elif all(d in placed_tasks for d in deps):
                current_column.append(task)

        if not current_column:
            for task in dependency_tasks:
                if task["task_id"] not in placed_tasks:
                    current_column.append(task)

        if current_column:
            dependency_columns.append(current_column)
            for t in current_column:
                placed_tasks.add(t["task_id"])
        else:
            break

    max_rows = 0
    for col_index, column in enumerate(dependency_columns):
        tasks_by_rightmost_dep: Dict[str, List[Dict]] = {}
        tasks_with_no_deps = []

        for task in column:
            deps = task.get("dependencies") or []
            if not deps:
                tasks_with_no_deps.append(task)
            else:
                rightmost_dep_id = None
                rightmost_dep_col = -1
                for dep_id in deps:
                    pos = task_positions.get(dep_id)
                    if pos and pos["col"] > rightmost_dep_col:
                        rightmost_dep_id = dep_id
                        rightmost_dep_col = pos["col"]

                if rightmost_dep_id:
                    if rightmost_dep_id not in tasks_by_rightmost_dep:
                        tasks_by_rightmost_dep[rightmost_dep_id] = []
                    tasks_by_rightmost_dep[rightmost_dep_id].append(task)
                else:
                    tasks_with_no_deps.append(task)

        current_row = 0
        for task in tasks_with_no_deps:
            task_positions[task["task_id"]] = {"col": col_index, "row": current_row, "task": task}
            current_row += 1
        for tasks_list in tasks_by_rightmost_dep.values():
            for task in tasks_list:
                task_positions[task["task_id"]] = {"col": col_index, "row": current_row, "task": task}
                current_row += 1
        if current_row > max_rows:
            max_rows = current_row

    if max_rows == 0:
        max_rows = 1

    regular_cols = len(dependency_columns)
    grid: List[List[Optional[Dict]]] = [[None] * regular_cols for _ in range(max_rows)]

    for task_id, pos in task_positions.items():
        if pos["col"] < regular_cols:
            grid[pos["row"]][pos["col"]] = pos["task"]

    tree_data = []
    for stage in task_stages:
        for task in stage:
            tree_data.append({**task, "stage": task.get("stage", 1)})

    return {
        "grid": grid,
        "maxRows": max_rows,
        "maxCols": regular_cols,
        "isolatedTasks": isolated_tasks,
        "treeData": tree_data,
    }
