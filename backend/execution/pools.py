"""
Worker pool - single pool for task execution + validation.
Validation is a fixed step after execution; workers handle both.
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
                if w["status"] in ("busy", "validating", "failed"):
                    w["status"] = "idle"
                    w["taskId"] = None
                    return w["id"]
                return w["id"]
        return None

    def set_status(wid: int, status: str) -> None:
        for w in workers:
            if w["id"] == wid:
                w["status"] = status
                break

    def get_stats() -> Dict:
        for w in workers:
            if w["status"] not in ("idle", "busy", "validating", "failed"):
                w["status"] = "idle"
                w["taskId"] = None
        busy = sum(1 for w in workers if w["status"] == "busy")
        validating = sum(1 for w in workers if w["status"] == "validating")
        idle = sum(1 for w in workers if w["status"] == "idle")
        failed = sum(1 for w in workers if w["status"] == "failed")
        if busy + validating + idle + failed != max_workers:
            init()
            return {"total": max_workers, "busy": 0, "validating": 0, "idle": max_workers, "failed": 0}
        return {"total": max_workers, "busy": busy, "validating": validating, "idle": idle, "failed": failed}

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


_worker_pool = _create_worker_pool(7)

worker_manager = {
    "get_all_workers": _worker_pool["get_all"],
    "get_worker_by_id": _worker_pool["get_by_id"],
    "get_idle_worker": _worker_pool["get_idle"],
    "assign_task": _worker_pool["assign_task"],
    "release_worker_by_task_id": _worker_pool["release_by_task_id"],
    "set_worker_status": _worker_pool["set_status"],
    "get_worker_stats": _worker_pool["get_stats"],
    "initialize_workers": _worker_pool["initialize"],
}
