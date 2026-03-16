"""Execution runner state/scheduling/rollback helpers."""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Set

from loguru import logger

from db import get_execution_task_step_dir
from .pools import worker_manager


def _runner_module():
    from . import runner as runner_mod

    return runner_mod


class RunnerStateMixin:
    def _schedule_ready_tasks(self, tasks_to_check: List[Dict]) -> None:
        if not tasks_to_check or not self.is_running:
            return
        ready = [
            t for t in tasks_to_check
            if t and t["task_id"] not in self.completed_tasks
            and t["task_id"] not in self.running_tasks
            and t["task_id"] in self.pending_tasks
            and self._are_dependencies_satisfied(t)
        ]
        for task in ready:
            self._spawn_task_execution(task)

    async def _handle_task_error(self, task: Dict, error: Exception) -> None:
        logger.exception("Error executing task %s", task["task_id"])
        self._emit("task-error", {
            "taskId": task["task_id"],
            "phase": "execution",
            "willRetry": False,
            "error": str(error),
        })
        async with self._worker_lock:
            worker_manager["release_worker_by_task_id"](task["task_id"])
        self._broadcast_worker_states()
        self.running_tasks.discard(task["task_id"])
        self.pending_tasks.discard(task["task_id"])
        self._update_task_status(task["task_id"], "execution-failed")
        await self._trigger_fail_fast(
            failed_task_id=task["task_id"],
            phase="execution",
            reason=str(error),
        )

    async def _trigger_fail_fast(self, *, failed_task_id: str, phase: str, reason: str) -> None:
        if not self.is_running:
            return

        self.is_running = False
        if self.abort_event:
            self.abort_event.set()

        self._emit("task-error", {
            "taskId": failed_task_id,
            "phase": phase,
            "willRetry": False,
            "error": reason or "Task failed",
            "fatal": True,
        })

        for tid, asyncio_task in list(self.task_tasks.items()):
            if tid == failed_task_id:
                continue
            if asyncio_task and not asyncio_task.done():
                asyncio_task.cancel()

        for tid in list(self.running_tasks):
            if tid == failed_task_id:
                continue
            self.running_tasks.discard(tid)
            self.pending_tasks.discard(tid)
            self._update_task_status(tid, "stopped")

        self._broadcast_worker_states()

    def _are_dependencies_satisfied(self, task: Dict) -> bool:
        deps = task.get("dependencies") or []
        if not deps:
            return True
        return all(d in self.completed_tasks for d in deps)

    def _update_task_status(self, task_id: str, status: str) -> None:
        t = self.task_map.get(task_id)
        if t:
            t["status"] = status
        try:
            asyncio.create_task(self._append_step_event(task_id, "task-status", {"status": status}))
        except RuntimeError:
            pass
        self._persist_execution()
        self._broadcast_task_states()

    async def _append_step_event(self, task_id: str, event: str, payload: Dict[str, Any]) -> None:
        if not self.execution_run_id or not task_id:
            return
        try:
            step_dir = get_execution_task_step_dir(self.execution_run_id, task_id).resolve()
            step_dir.mkdir(parents=True, exist_ok=True)
            path = step_dir / "events.jsonl"
            record = {
                "ts": int(time.time() * 1000),
                "runId": self.execution_run_id,
                "taskId": task_id,
                "event": event,
                "payload": payload or {},
            }
            line = json.dumps(record, ensure_ascii=False) + "\n"
            await asyncio.to_thread(self._append_line, path, line)
        except Exception as e:
            logger.debug("Failed to append step event task_id={} event={} error={}", task_id, event, e)

    @staticmethod
    def _append_line(path: Path, line: str) -> None:
        with path.open("a", encoding="utf-8") as f:
            f.write(line)

    async def _stop_all_task_containers(self) -> None:
        runner_mod = _runner_module()
        containers = list(self.task_docker_containers.values())
        self.task_docker_containers.clear()
        for container_name in containers:
            try:
                await runner_mod.stop_execution_container(container_name)
            except Exception:
                logger.exception("Failed to stop Docker execution container {}", container_name)
        self.docker_container_name = ""

    def _broadcast_task_states(self) -> None:
        task_states = [{"task_id": t["task_id"], "status": t["status"]} for t in self.chain_cache]
        self._emit("task-states-update", {"tasks": task_states})

    def _broadcast_worker_states(self) -> None:
        """Broadcast execution concurrency stats. (Frontend uses syncExecutionStateOnConnect for stats.)"""

    async def _rollback_task(self, task: Dict) -> None:
        runner_mod = _runner_module()
        tasks_to_rollback: Set[str] = set()
        tasks_to_rollback.add(task["task_id"])

        visited: Set[str] = set()

        def find_downstream(tid: str) -> None:
            if tid in visited:
                return
            visited.add(tid)
            for dep_id in self.reverse_dependency_index.get(tid, []):
                if dep_id not in tasks_to_rollback:
                    tasks_to_rollback.add(dep_id)
                    find_downstream(dep_id)

        find_downstream(task["task_id"])

        async with self._worker_lock:
            for task_id in tasks_to_rollback:
                t = self.task_map.get(task_id)
                if t:
                    self.completed_tasks.discard(task_id)
                    self.pending_tasks.add(task_id)
                    self.running_tasks.discard(task_id)
                    self._update_task_status(task_id, "undone")
                    self._clear_task_failure_counts(task_id)
                    self.task_last_retry_attempt.pop(task_id, None)
                    self.task_run_attempt.pop(task_id, None)
                    self.task_forced_attempt.pop(task_id, None)
                    self.task_next_attempt_hint.pop(task_id, None)
                    self.task_execute_started_attempts.pop(task_id, None)
                    self.task_tasks.pop(task_id, None)
                    worker_manager["release_worker_by_task_id"](task_id)
                if self.idea_id and self.plan_id:
                    await runner_mod.delete_task_artifact(self.idea_id, self.plan_id, task_id)

        self._broadcast_worker_states()

        ready = [
            self.task_map[tid]
            for tid in tasks_to_rollback
            if self.task_map.get(tid)
            and self._are_dependencies_satisfied(self.task_map[tid])
            and tid in self.pending_tasks
        ]
        if ready:
            self._schedule_ready_tasks(ready)

    def set_layout(
        self,
        layout: Dict,
        idea_id: str | None = None,
        plan_id: str | None = None,
        execution: Dict | None = None,
    ) -> None:
        if self.is_running:
            raise ValueError("Cannot set layout while execution is running")
        self.execution_layout = layout
        self.idea_id = idea_id
        self.plan_id = plan_id
        self.chain_cache = []
        task_by_id = {}
        if execution:
            for t in execution.get("tasks") or []:
                if t.get("task_id"):
                    task_by_id[t["task_id"]] = t
        for t in layout.get("treeData") or []:
            if t and t.get("task_id"):
                tid = t["task_id"]
                full = task_by_id.get(tid, {})
                status = full.get("status") or t.get("status") or "undone"
                self.chain_cache.append({
                    "task_id": tid,
                    "title": full.get("title") or t.get("title"),
                    "dependencies": t.get("dependencies") or [],
                    "status": status,
                    "description": full.get("description") or t.get("description"),
                    "input": full.get("input") or t.get("input"),
                    "output": full.get("output") or t.get("output"),
                    "validation": full.get("validation") or t.get("validation"),
                })

    async def retry_task(self, task_id: str) -> bool:
        runner_mod = _runner_module()
        if task_id not in self.task_map:
            return False
        tasks_to_reset = self._get_downstream_task_ids(task_id)

        for tid in list(tasks_to_reset):
            asyncio_task = self.task_tasks.pop(tid, None)
            if asyncio_task and not asyncio_task.done():
                asyncio_task.cancel()

        async with self._worker_lock:
            for tid in tasks_to_reset:
                self.completed_tasks.discard(tid)
                self.running_tasks.discard(tid)
                self.pending_tasks.add(tid)
                self._clear_task_failure_counts(tid)
                self.task_last_retry_attempt.pop(tid, None)
                self.task_run_attempt.pop(tid, None)
                self.task_forced_attempt.pop(tid, None)
                self.task_next_attempt_hint.pop(tid, None)
                if not self.is_running:
                    self.task_execute_started_attempts.pop(tid, None)
                if tid in self.task_map:
                    self.task_map[tid]["status"] = "undone"
                worker_manager["release_worker_by_task_id"](tid)
                if self.idea_id and self.plan_id:
                    await runner_mod.delete_task_artifact(self.idea_id, self.plan_id, tid)

        await self._clear_attempt_history_for_tasks(tasks_to_reset)

        self._persist_execution()
        self._broadcast_task_states()
        self._broadcast_worker_states()

        if self.is_running:
            ready = [
                self.task_map[tid]
                for tid in tasks_to_reset
                if tid in self.task_map
                and tid in self.pending_tasks
                and self._are_dependencies_satisfied(self.task_map[tid])
            ]
            if ready:
                self._schedule_ready_tasks(ready)
        return True

    async def stop_async(self) -> None:
        runner_mod = _runner_module()
        self.is_running = False
        if self.abort_event:
            self.abort_event.set()
        self._emit("task-error", {"error": "Task execution stopped by user"})
        task_ids = list(self.task_tasks.keys())
        for task_id in task_ids:
            asyncio_task = self.task_tasks.get(task_id)
            if asyncio_task and not asyncio_task.done():
                asyncio_task.cancel()
        async with self._worker_lock:
            for task_id in task_ids:
                worker_manager["release_worker_by_task_id"](task_id)
        self.task_tasks.clear()
        self.running_tasks.clear()
        await self._stop_all_task_containers()
        self.docker_runtime_status = await runner_mod.get_local_docker_status(enabled=bool((self.api_config or {}).get("taskAgentMode")))
        self._emit_runtime_status()
        self._broadcast_worker_states()
