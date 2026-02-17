"""
Executor Runner - handles task execution and verification via worker pools.
Executor and verifier are both workers.
"""

import asyncio
import logging
import random
from typing import Any, Dict, List, Set

from . import executor_manager, verifier_manager

logger = logging.getLogger(__name__)


class ExecutorRunner:
    def __init__(self, sio: Any):
        self.sio = sio
        self._worker_lock = asyncio.Lock()
        self.is_running = False
        self.running_tasks: Set[str] = set()
        self.completed_tasks: Set[str] = set()
        self.pending_tasks: Set[str] = set()
        self.task_tasks: Dict[str, asyncio.Task] = {}
        self.chain_cache: List[Dict] = []
        self.task_map: Dict[str, Dict] = {}
        self.reverse_dependency_index: Dict[str, List[str]] = {}
        self.task_failure_count: Dict[str, int] = {}
        self.EXECUTION_PASS_PROBABILITY = 0.95
        self.VERIFY_PASS_PROBABILITY = 0.95
        self.MAX_FAILURES = 3
        self.timetable_layout = None

    def _emit(self, event: str, data: dict) -> None:
        """Emit event to all clients (fire-and-forget)."""
        if hasattr(self.sio, "emit"):
            try:
                asyncio.create_task(self.sio.emit(event, data))
            except RuntimeError:
                pass

    async def start_mock_execution(self) -> None:
        if self.is_running:
            raise ValueError("Execution is already running")
        if not self.chain_cache:
            raise ValueError("No execution map cache found. Please generate execution map first.")
        if not self.timetable_layout:
            raise ValueError("No timetable layout cache found. Please generate execution map first.")

        self.is_running = True
        try:
            executor_manager["initialize_executors"]()
            verifier_manager["initialize_verifiers"]()
            self._broadcast_executor_states()
            self._broadcast_verifier_states()

            timetable_layout = self.timetable_layout
            for task in self.chain_cache:
                task["status"] = "undone"

            self.running_tasks.clear()
            self.completed_tasks.clear()
            self.pending_tasks.clear()
            self.task_tasks.clear()
            self.task_map.clear()
            self.reverse_dependency_index.clear()
            self.task_failure_count.clear()

            for task in self.chain_cache:
                self.task_map[task["task_id"]] = task
                self.pending_tasks.add(task["task_id"])
                self.reverse_dependency_index[task["task_id"]] = []

            for task in self.chain_cache:
                for dep_id in (task.get("dependencies") or []):
                    if dep_id in self.reverse_dependency_index:
                        self.reverse_dependency_index[dep_id].append(task["task_id"])

            self._emit("timetable-layout", {"layout": timetable_layout})
            self._broadcast_task_states()
            await self._execute_tasks()
        except Exception as e:
            logger.exception("Error in mock execution")
            self._emit("execution-error", {"error": str(e)})
            raise
        finally:
            self.is_running = False
            executor_manager["initialize_executors"]()
            verifier_manager["initialize_verifiers"]()
            self._broadcast_executor_states()
            self._broadcast_verifier_states()

    def _get_pending_ready_tasks(self) -> List[Dict]:
        result = []
        for task_id in self.pending_tasks:
            if task_id in self.running_tasks or task_id in self.completed_tasks:
                continue
            task = self.task_map.get(task_id)
            if task and self._are_dependencies_satisfied(task):
                result.append(task)
        return result

    async def _execute_tasks(self) -> None:
        initial_ready = self._get_pending_ready_tasks()
        logger.info("Found %d initial ready tasks out of %d total tasks", len(initial_ready), len(self.chain_cache))

        for task in initial_ready:
            async def run_with_error_handling(t=task):
                try:
                    await self._execute_task(t)
                except Exception as e:
                    await self._handle_task_error(t, e)

            self.task_tasks[task["task_id"]] = asyncio.create_task(run_with_error_handling())

        # Event-driven: wait for completion (task completion triggers _check_specific_tasks)
        while len(self.completed_tasks) < len(self.chain_cache) or len(self.running_tasks) > 0:
            await asyncio.sleep(0.1)

        logger.info("Final state: %d/%d tasks completed", len(self.completed_tasks), len(self.chain_cache))
        self._emit("execution-complete", {"completed": len(self.completed_tasks), "total": len(self.chain_cache)})

    async def _execute_task(self, task: Dict) -> None:
        executor_id = None
        retry_count = 0
        while executor_id is None and retry_count < 50:
            async with self._worker_lock:
                executor_id = executor_manager["assign_task"](task["task_id"])
            if executor_id is None:
                await asyncio.sleep(min(0.1 + retry_count * 0.02, 0.5))
                retry_count += 1
                if retry_count % 5 == 0:
                    self._broadcast_executor_states()
            else:
                break

        if executor_id is None:
            logger.warning("Failed to assign executor to task %s after %d retries", task["task_id"], retry_count)
            self.completed_tasks.add(task["task_id"])
            self.running_tasks.discard(task["task_id"])
            self.pending_tasks.discard(task["task_id"])
            self._update_task_status(task["task_id"], "done")
            dependents = self.reverse_dependency_index.get(task["task_id"], [])
            self._check_specific_tasks([self.task_map[id] for id in dependents if self.task_map.get(id)])
            return

        self.running_tasks.add(task["task_id"])
        self._update_task_status(task["task_id"], "doing")
        self._broadcast_executor_states()

        try:
            await asyncio.sleep(0.5 + random.random() * 1.5)
            execution_passed = random.random() < self.EXECUTION_PASS_PROBABILITY

            if not execution_passed:
                self._update_task_status(task["task_id"], "execution-failed")
                exec_obj = executor_manager["get_executor_by_id"](executor_id)
                if exec_obj:
                    exec_obj["status"] = "failed"
                    self._broadcast_executor_states()
                    await asyncio.sleep(0.5)
                failure_count = self.task_failure_count.get(task["task_id"], 0)
                self.task_failure_count[task["task_id"]] = failure_count + 1
                async with self._worker_lock:
                    executor_manager["release_executor_by_task_id"](task["task_id"])
                self._broadcast_executor_states()
                await asyncio.sleep(1.0)
                if failure_count < self.MAX_FAILURES - 1:
                    self.running_tasks.discard(task["task_id"])
                    self.completed_tasks.discard(task["task_id"])
                    await self._execute_task(task)
                    return
                else:
                    self.running_tasks.discard(task["task_id"])
                    self.completed_tasks.discard(task["task_id"])
                    await self._rollback_task(task)
                    return

            async with self._worker_lock:
                executor_manager["release_executor_by_task_id"](task["task_id"])
            self._broadcast_executor_states()
            self._update_task_status(task["task_id"], "verifying")

            verifier_id = None
            retry_count = 0
            while verifier_id is None and retry_count < 50:
                async with self._worker_lock:
                    verifier_id = verifier_manager["assign_task"](task["task_id"])
                if verifier_id is None:
                    await asyncio.sleep(min(0.1 + retry_count * 0.02, 0.5))
                    retry_count += 1
                    if retry_count % 5 == 0:
                        self._broadcast_verifier_states()
                else:
                    break

            if verifier_id:
                self._broadcast_verifier_states()

            await asyncio.sleep(0.2 + random.random() * 0.6)
            verification_passed = random.random() < self.VERIFY_PASS_PROBABILITY

            if verification_passed:
                if verifier_id:
                    async with self._worker_lock:
                        verifier_manager["release_verifier_by_task_id"](task["task_id"])
                    self._broadcast_verifier_states()
            else:
                self._update_task_status(task["task_id"], "verification-failed")
                if verifier_id:
                    ver_obj = verifier_manager["get_verifier_by_id"](verifier_id)
                    if ver_obj:
                        ver_obj["status"] = "failed"
                        self._broadcast_verifier_states()
                        await asyncio.sleep(0.5)
                failure_count = self.task_failure_count.get(task["task_id"], 0)
                self.task_failure_count[task["task_id"]] = failure_count + 1
                await asyncio.sleep(1.0)
                if verifier_id:
                    async with self._worker_lock:
                        verifier_manager["release_verifier_by_task_id"](task["task_id"])
                    self._broadcast_verifier_states()
                if failure_count < self.MAX_FAILURES - 1:
                    self.running_tasks.discard(task["task_id"])
                    self.completed_tasks.discard(task["task_id"])
                    await self._execute_task(task)
                    return
                else:
                    self.running_tasks.discard(task["task_id"])
                    self.completed_tasks.discard(task["task_id"])
                    await self._rollback_task(task)
                    return

        except Exception as e:
            async with self._worker_lock:
                executor_manager["release_executor_by_task_id"](task["task_id"])
                verifier_manager["release_verifier_by_task_id"](task["task_id"])
            self._broadcast_executor_states()
            self._broadcast_verifier_states()
            raise

        self.running_tasks.discard(task["task_id"])
        self.completed_tasks.add(task["task_id"])
        self.pending_tasks.discard(task["task_id"])
        self._update_task_status(task["task_id"], "done")
        self.task_failure_count.pop(task["task_id"], None)

        dependents = self.reverse_dependency_index.get(task["task_id"], [])
        candidates = set(dependents)
        for t in self.chain_cache:
            if not (t.get("dependencies") or []):
                if t["task_id"] in self.pending_tasks and t["task_id"] not in self.running_tasks:
                    candidates.add(t["task_id"])
        for task_id in self.pending_tasks:
            if task_id not in self.running_tasks and task_id not in self.completed_tasks:
                pt = self.task_map.get(task_id)
                if pt and self._are_dependencies_satisfied(pt):
                    candidates.add(task_id)

        self._check_specific_tasks([self.task_map[id] for id in candidates if self.task_map.get(id)])

    def _check_specific_tasks(self, tasks_to_check: List[Dict]) -> None:
        if not tasks_to_check:
            return
        ready = [
            t for t in tasks_to_check
            if t and t["task_id"] not in self.completed_tasks
            and t["task_id"] not in self.running_tasks
            and t["task_id"] in self.pending_tasks
            and self._are_dependencies_satisfied(t)
        ]
        for task in ready:
            if task["task_id"] not in self.task_tasks:
                async def run_with_error_handling(t=task):
                    try:
                        await self._execute_task(t)
                    except Exception as e:
                        await self._handle_task_error(t, e)

                self.task_tasks[task["task_id"]] = asyncio.create_task(run_with_error_handling())

    async def _handle_task_error(self, task: Dict, error: Exception) -> None:
        logger.exception("Error executing task %s", task["task_id"])
        async with self._worker_lock:
            executor_manager["release_executor_by_task_id"](task["task_id"])
            verifier_manager["release_verifier_by_task_id"](task["task_id"])
        self._broadcast_executor_states()
        self._broadcast_verifier_states()
        self.completed_tasks.add(task["task_id"])
        self.running_tasks.discard(task["task_id"])
        self.pending_tasks.discard(task["task_id"])
        self._update_task_status(task["task_id"], "verifying")

        async def delayed_done() -> None:
            await asyncio.sleep(0.3)
            self._update_task_status(task["task_id"], "done")

        asyncio.create_task(delayed_done())
        dependents = self.reverse_dependency_index.get(task["task_id"], [])
        self._check_specific_tasks([self.task_map[id] for id in dependents if self.task_map.get(id)])

    def _are_dependencies_satisfied(self, task: Dict) -> bool:
        deps = task.get("dependencies") or []
        if not deps:
            return True
        return all(d in self.completed_tasks for d in deps)

    def _update_task_status(self, task_id: str, status: str) -> None:
        for t in self.chain_cache:
            if t.get("task_id") == task_id:
                t["status"] = status
                self._broadcast_task_states()
                break

    def _broadcast_task_states(self) -> None:
        task_states = [{"task_id": t["task_id"], "status": t["status"]} for t in self.chain_cache]
        self._emit("task-states-update", {"tasks": task_states})

    def _broadcast_executor_states(self) -> None:
        executors = executor_manager["get_all_executors"]()
        stats = executor_manager["get_executor_stats"]()
        self._emit("executor-states-update", {"executors": executors, "stats": stats})

    def _broadcast_verifier_states(self) -> None:
        verifiers = verifier_manager["get_all_verifiers"]()
        stats = verifier_manager["get_verifier_stats"]()
        self._emit("verifier-states-update", {"verifiers": verifiers, "stats": stats})

    async def _rollback_task(self, task: Dict) -> None:
        """Rollback task and all affected: upstream deps + downstream dependents.
        Once a task is undone, its downstream results are unreliable and must be undone too."""
        tasks_to_rollback: Set[str] = set()
        tasks_to_rollback.add(task["task_id"])
        for dep_id in (task.get("dependencies") or []):
            tasks_to_rollback.add(dep_id)

        visited: Set[str] = set()

        def find_downstream(tid: str) -> None:
            if tid in visited:
                return
            visited.add(tid)
            for dep_id in self.reverse_dependency_index.get(tid, []):
                if dep_id not in tasks_to_rollback:
                    tasks_to_rollback.add(dep_id)
                    find_downstream(dep_id)

        for dep_id in (task.get("dependencies") or []):
            find_downstream(dep_id)
        # Downstream of the rolled-back task: all dependents become unreliable
        find_downstream(task["task_id"])

        async with self._worker_lock:
            for task_id in tasks_to_rollback:
                t = self.task_map.get(task_id)
                if t:
                    self.completed_tasks.discard(task_id)
                    self.pending_tasks.add(task_id)
                    self.running_tasks.discard(task_id)
                    self._update_task_status(task_id, "undone")
                    self.task_failure_count.pop(task_id, None)
                    self.task_tasks.pop(task_id, None)
                    executor_manager["release_executor_by_task_id"](task_id)
                    verifier_manager["release_verifier_by_task_id"](task_id)

        self._broadcast_executor_states()
        self._broadcast_verifier_states()

        ready = [
            self.task_map[tid]
            for tid in tasks_to_rollback
            if self.task_map.get(tid)
            and self._are_dependencies_satisfied(self.task_map[tid])
            and tid in self.pending_tasks
        ]
        if ready:
            self._check_specific_tasks(ready)

    def set_timetable_layout_cache(self, layout: Dict) -> None:
        self.timetable_layout = layout
        self.chain_cache = []
        grid = layout.get("grid", [])
        isolated_tasks = layout.get("isolatedTasks", [])
        for row in grid:
            for cell in row or []:
                if cell and cell.get("task_id"):
                    self.chain_cache.append({
                        "task_id": cell["task_id"],
                        "dependencies": cell.get("dependencies") or [],
                        "status": cell.get("status") or "undone",
                    })
        for t in isolated_tasks or []:
            if t and t.get("task_id"):
                self.chain_cache.append({
                    "task_id": t["task_id"],
                    "dependencies": t.get("dependencies") or [],
                    "status": t.get("status") or "undone",
                })

    def stop(self) -> None:
        """Stop execution (sync). Use stop_async for lock-protected release."""
        self.is_running = False
        task_ids = list(self.task_tasks.keys())
        for task_id in task_ids:
            executor_manager["release_executor_by_task_id"](task_id)
            verifier_manager["release_verifier_by_task_id"](task_id)
        self.task_tasks.clear()
        self._broadcast_executor_states()
        self._broadcast_verifier_states()

    async def stop_async(self) -> None:
        """Stop execution with lock-protected release (preferred from API)."""
        self.is_running = False
        task_ids = list(self.task_tasks.keys())
        async with self._worker_lock:
            for task_id in task_ids:
                executor_manager["release_executor_by_task_id"](task_id)
                verifier_manager["release_verifier_by_task_id"](task_id)
        self.task_tasks.clear()
        self._broadcast_executor_states()
        self._broadcast_verifier_states()
