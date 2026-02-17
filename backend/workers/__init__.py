"""
Worker pool for executors and verifiers.
Manages state: idle | busy | failed
"""

from typing import Dict, List, Optional


def _create_worker_pool(max_workers: int) -> Dict:
    workers: List[Dict] = []

    def init() -> None:
        nonlocal workers
        workers = [{"id": i + 1, "status": "idle", "taskId": None} for i in range(max_workers)]

    def get_all() -> List[Dict]:
        return [{**w} for w in workers]

    def get_by_id(wid: int, copy: bool = False) -> Optional[Dict]:
        for w in workers:
            if w["id"] == wid:
                return {**w} if copy else w
        return None

    def get_idle() -> Optional[Dict]:
        for w in workers:
            if w["status"] == "idle":
                return w
        return None

    def assign_task(task_id: str) -> Optional[int]:
        w = get_idle()
        if w:
            if w["status"] != "idle":
                w["status"] = "idle"
                w["taskId"] = None
            w["status"] = "busy"
            w["taskId"] = task_id
            return w["id"]
        return None

    def release_by_task_id(task_id: str) -> Optional[int]:
        for w in workers:
            if w.get("taskId") == task_id:
                if w["status"] in ("busy", "failed"):
                    w["status"] = "idle"
                    w["taskId"] = None
                    return w["id"]
                return w["id"]
        return None

    def get_stats() -> Dict:
        for w in workers:
            if w["status"] not in ("idle", "busy", "failed"):
                w["status"] = "idle"
                w["taskId"] = None
        busy = sum(1 for w in workers if w["status"] == "busy")
        idle = sum(1 for w in workers if w["status"] == "idle")
        failed = sum(1 for w in workers if w["status"] == "failed")
        if busy + idle + failed != max_workers:
            init()
            return {"total": max_workers, "busy": 0, "idle": max_workers, "failed": 0}
        return {"total": max_workers, "busy": busy, "idle": idle, "failed": failed}

    init()
    return {
        "get_all": get_all,
        "get_by_id": get_by_id,
        "get_idle": get_idle,
        "assign_task": assign_task,
        "release_by_task_id": release_by_task_id,
        "get_stats": get_stats,
        "initialize": init,
    }


_executor_pool = _create_worker_pool(7)
_verifier_pool = _create_worker_pool(5)

executor_manager = {
    "get_all_executors": _executor_pool["get_all"],
    "get_executor_by_id": _executor_pool["get_by_id"],
    "get_idle_executor": _executor_pool["get_idle"],
    "assign_task": _executor_pool["assign_task"],
    "release_executor_by_task_id": _executor_pool["release_by_task_id"],
    "get_executor_stats": _executor_pool["get_stats"],
    "initialize_executors": _executor_pool["initialize"],
}

verifier_manager = {
    "get_all_verifiers": _verifier_pool["get_all"],
    "get_verifier_by_id": _verifier_pool["get_by_id"],
    "get_idle_verifier": _verifier_pool["get_idle"],
    "assign_task": _verifier_pool["assign_task"],
    "release_verifier_by_task_id": _verifier_pool["release_by_task_id"],
    "get_verifier_stats": _verifier_pool["get_stats"],
    "initialize_verifiers": _verifier_pool["initialize"],
}

from .runner import ExecutorRunner
