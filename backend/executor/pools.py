"""
Executor pool - single pool for task execution + validation.
Validation is a fixed step after execution; Executor handles both.
"""

from typing import Dict, List, Optional


def _create_executor_pool(max_executors: int) -> Dict:
    executors: List[Dict] = []

    def init() -> None:
        nonlocal executors
        executors = [{"id": i + 1, "status": "idle", "taskId": None} for i in range(max_executors)]

    def get_all() -> List[Dict]:
        return [{**e} for e in executors]

    def get_by_id(eid: int, copy: bool = False) -> Optional[Dict]:
        for e in executors:
            if e["id"] == eid:
                return {**e} if copy else e
        return None

    def get_idle() -> Optional[Dict]:
        for e in executors:
            if e["status"] == "idle":
                return e
        return None

    def assign_task(task_id: str) -> Optional[int]:
        e = get_idle()
        if e:
            if e["status"] != "idle":
                e["status"] = "idle"
                e["taskId"] = None
            e["status"] = "busy"
            e["taskId"] = task_id
            return e["id"]
        return None

    def release_by_task_id(task_id: str) -> Optional[int]:
        for e in executors:
            if e.get("taskId") == task_id:
                if e["status"] in ("busy", "validating", "failed"):
                    e["status"] = "idle"
                    e["taskId"] = None
                    return e["id"]
                return e["id"]
        return None

    def set_status(eid: int, status: str) -> None:
        for e in executors:
            if e["id"] == eid:
                e["status"] = status
                break

    def get_stats() -> Dict:
        for e in executors:
            if e["status"] not in ("idle", "busy", "validating", "failed"):
                e["status"] = "idle"
                e["taskId"] = None
        busy = sum(1 for e in executors if e["status"] == "busy")
        validating = sum(1 for e in executors if e["status"] == "validating")
        idle = sum(1 for e in executors if e["status"] == "idle")
        failed = sum(1 for e in executors if e["status"] == "failed")
        if busy + validating + idle + failed != max_executors:
            init()
            return {"total": max_executors, "busy": 0, "validating": 0, "idle": max_executors, "failed": 0}
        return {"total": max_executors, "busy": busy, "validating": validating, "idle": idle, "failed": failed}

    init()
    return {
        "get_all": get_all,
        "get_by_id": get_by_id,
        "get_idle": get_idle,
        "assign_task": assign_task,
        "release_by_task_id": release_by_task_id,
        "set_status": set_status,
        "get_stats": get_stats,
        "initialize": init,
    }


_executor_pool = _create_executor_pool(7)

executor_manager = {
    "get_all_executors": _executor_pool["get_all"],
    "get_executor_by_id": _executor_pool["get_by_id"],
    "get_idle_executor": _executor_pool["get_idle"],
    "assign_task": _executor_pool["assign_task"],
    "release_executor_by_task_id": _executor_pool["release_by_task_id"],
    "set_executor_status": _executor_pool["set_status"],
    "get_executor_stats": _executor_pool["get_stats"],
    "initialize_executors": _executor_pool["initialize"],
}
