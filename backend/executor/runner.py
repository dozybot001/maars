"""
Executor Runner - handles task execution and output validation via worker pools.
Executor runs tasks; Validator checks task output against criteria (distinct from planner's atomicity check).
Task status changes are persisted to execution.json in real-time.
"""

import asyncio
import os
import random
from typing import Any, Dict, List, Optional, Set

from loguru import logger

from db import save_execution, save_task_artifact
from . import executor_manager
from .execution import resolve_artifacts, execute_task
from validator import validator_manager

# Mock validator chunk delay (seconds), same as executor for consistent streaming UX
_MOCK_VALIDATOR_CHUNK_DELAY = 0.03

# Configurable via env (Mock mode); defaults for tuning
def _float_env(name: str, default: float) -> float:
    v = os.environ.get(name)
    return float(v) if v is not None else default

def _int_env(name: str, default: int) -> int:
    v = os.environ.get(name)
    return int(v) if v is not None else default

_RUNNER_EXECUTION_PASS_PROBABILITY = _float_env("MAARS_EXECUTION_PASS_PROBABILITY", 0.95)
_RUNNER_VALIDATION_PASS_PROBABILITY = _float_env("MAARS_VALIDATION_PASS_PROBABILITY", 0.95)
_RUNNER_MAX_FAILURES = _int_env("MAARS_MAX_FAILURES", 3)


def _chunk_string(s: str, size: int):
    """Yield string in chunks for simulated streaming."""
    for i in range(0, len(s), size):
        yield s[i : i + size]


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
        self.EXECUTION_PASS_PROBABILITY = _RUNNER_EXECUTION_PASS_PROBABILITY
        self.VALIDATION_PASS_PROBABILITY = _RUNNER_VALIDATION_PASS_PROBABILITY
        self.MAX_FAILURES = _RUNNER_MAX_FAILURES
        self.timetable_layout = None
        self.plan_id: Optional[str] = None
        self.api_config: Optional[Dict] = None
        self.abort_event: Optional[asyncio.Event] = None
        self._persist_lock = asyncio.Lock()
        self._start_lock = asyncio.Lock()

    def _persist_execution(self) -> None:
        """Persist chain_cache to execution.json. Serialized via _persist_lock to avoid concurrent write races."""
        if self.plan_id and self.chain_cache:
            try:
                asyncio.create_task(self._persist_execution_async())
            except RuntimeError:
                pass

    async def _persist_execution_async(self) -> None:
        """Serialized persist: prevents multiple save_execution from overwriting each other with stale data."""
        async with self._persist_lock:
            if self.plan_id and self.chain_cache:
                try:
                    await save_execution({"tasks": list(self.chain_cache)}, self.plan_id)
                except Exception as e:
                    logger.warning("Failed to persist execution: %s", e)

    def _emit(self, event: str, data: dict) -> None:
        """Emit event to all clients (fire-and-forget)."""
        if hasattr(self.sio, "emit"):
            try:
                asyncio.create_task(self.sio.emit(event, data))
            except RuntimeError:
                pass

    async def _emit_await(self, event: str, data: dict) -> None:
        """Emit event and await; use for order-sensitive events (e.g. thinking chunks)."""
        if hasattr(self.sio, "emit"):
            try:
                await self.sio.emit(event, data)
            except Exception:
                pass

    async def start_execution(self, api_config: Optional[Dict] = None) -> None:
        if api_config is not None:
            self.api_config = api_config
            mock_cfg = (api_config.get("modeConfig") or {}).get("mock") or {}
            if mock_cfg:
                v = mock_cfg.get("executionPassProbability")
                if v is not None:
                    self.EXECUTION_PASS_PROBABILITY = float(v)
                v = mock_cfg.get("validationPassProbability")
                if v is not None:
                    self.VALIDATION_PASS_PROBABILITY = float(v)
                v = mock_cfg.get("maxFailures")
                if v is not None:
                    self.MAX_FAILURES = int(v)
        async with self._start_lock:
            if self.is_running:
                raise ValueError("Execution is already running")
            if not self.chain_cache:
                raise ValueError("No execution map cache found. Please generate map first.")
            if not self.timetable_layout:
                raise ValueError("No timetable layout cache found. Please generate map first.")
            self.is_running = True
        self.abort_event = asyncio.Event()
        self.abort_event.clear()
        try:
            executor_manager["initialize_executors"]()
            validator_manager["initialize_validators"]()
            self._broadcast_executor_states()
            self._broadcast_validator_states()

            timetable_layout = self.timetable_layout
            for task in self.chain_cache:
                task["status"] = "undone"
            if self.plan_id and self.chain_cache:
                await save_execution({"tasks": self.chain_cache}, self.plan_id)

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

            self._emit("execution-start", {})
            self._emit("timetable-layout", {"layout": timetable_layout})
            self._broadcast_task_states()
            await self._execute_tasks()
        except Exception as e:
            logger.exception("Error in execution")
            self._emit("execution-error", {"error": str(e)})
            raise
        finally:
            self.is_running = False
            executor_manager["initialize_executors"]()
            validator_manager["initialize_validators"]()
            self._broadcast_executor_states()
            self._broadcast_validator_states()

    def _get_ready_tasks(self) -> List[Dict]:
        result = []
        for task_id in self.pending_tasks:
            if task_id in self.running_tasks or task_id in self.completed_tasks:
                continue
            task = self.task_map.get(task_id)
            if task and self._are_dependencies_satisfied(task):
                result.append(task)
        return result

    async def _execute_tasks(self) -> None:
        initial_ready = self._get_ready_tasks()
        logger.info("Found %d initial ready tasks out of %d total tasks", len(initial_ready), len(self.chain_cache))

        for task in initial_ready:
            async def run_with_error_handling(t=task):
                try:
                    await self._execute_task(t)
                except Exception as e:
                    await self._handle_task_error(t, e)

            self.task_tasks[task["task_id"]] = asyncio.create_task(run_with_error_handling())

        # Event-driven: wait for completion (task completion triggers _schedule_ready_tasks)
        while self.is_running and (len(self.completed_tasks) < len(self.chain_cache) or len(self.running_tasks) > 0):
            await asyncio.sleep(0.1)

        logger.info("Final state: %d/%d tasks completed", len(self.completed_tasks), len(self.chain_cache))
        if self.is_running:
            self._emit("execution-complete", {"completed": len(self.completed_tasks), "total": len(self.chain_cache)})
        else:
            self._emit("execution-error", {"error": "Execution stopped by user"})

    async def _execute_task(self, task: Dict) -> None:
        if not self.is_running:
            return
        executor_id = None
        retry_count = 0
        while self.is_running and executor_id is None and retry_count < 50:
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
            self._schedule_ready_tasks([self.task_map[id] for id in dependents if self.task_map.get(id)])
            return

        self.running_tasks.add(task["task_id"])
        self._update_task_status(task["task_id"], "doing")
        self._broadcast_executor_states()

        try:
            input_spec = task.get("input") or {}
            output_spec = task.get("output") or {}
            if not output_spec:
                raise ValueError(f"Task {task['task_id']} has no output spec")
            try:
                resolved_inputs = await resolve_artifacts(task, self.task_map, self.plan_id or "")

                async def _on_thinking(chunk: str, task_id: Optional[str] = None, operation: Optional[str] = None) -> None:
                    await self._emit_await("executor-thinking", {"chunk": chunk, "taskId": task_id, "operation": operation or "Execute"})

                result = await execute_task(
                    task_id=task["task_id"],
                    description=task.get("description") or "",
                    input_spec=input_spec,
                    output_spec=output_spec,
                    resolved_inputs=resolved_inputs,
                    api_config=self.api_config or {},
                    abort_event=self.abort_event,
                    on_thinking=_on_thinking,
                    plan_id=self.plan_id or "",
                )
                to_save = result if isinstance(result, dict) else {"content": result}
                await save_task_artifact(self.plan_id or "", task["task_id"], to_save)
                self._emit("executor-output", {"taskId": task["task_id"], "output": result})
                execution_passed = True
            except Exception as exec_err:
                logger.warning("LLM execution failed for task %s: %s", task["task_id"], exec_err)
                execution_passed = False

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
            self._update_task_status(task["task_id"], "validating")

            validator_id = None
            retry_count = 0
            while validator_id is None and retry_count < 50:
                async with self._worker_lock:
                    validator_id = validator_manager["assign_task"](task["task_id"])
                if validator_id is None:
                    await asyncio.sleep(min(0.1 + retry_count * 0.02, 0.5))
                    retry_count += 1
                    if retry_count % 5 == 0:
                        self._broadcast_validator_states()
                else:
                    break

            if validator_id:
                self._broadcast_validator_states()

            # Mock validator thinking stream (simulates validation report)
            validation_passed = random.random() < self.VALIDATION_PASS_PROBABILITY
            task_id = task["task_id"]
            mock_report = (
                f"# Validating Task {task_id}\n\n"
                "Checking output against criteria...\n\n"
                "- Criterion 1: Output format ✓\n"
                "- Criterion 2: Content completeness ✓\n"
                "- Criterion 3: Alignment with spec ✓\n\n"
                f"**Result: {'PASS' if validation_passed else 'FAIL'}**\n\n"
                "(Mock validation mode)"
            )
            for chunk in _chunk_string(mock_report, 20):
                await self._emit_await("validator-thinking", {"chunk": chunk, "taskId": task_id, "operation": "Validate"})
                await asyncio.sleep(_MOCK_VALIDATOR_CHUNK_DELAY)

            await asyncio.sleep(0.1)

            if validation_passed:
                if validator_id:
                    async with self._worker_lock:
                        validator_manager["release_validator_by_task_id"](task["task_id"])
                    self._broadcast_validator_states()
            else:
                self._update_task_status(task["task_id"], "validation-failed")
                if validator_id:
                    validator_obj = validator_manager["get_validator_by_id"](validator_id)
                    if validator_obj:
                        validator_obj["status"] = "failed"
                        self._broadcast_validator_states()
                        await asyncio.sleep(0.5)
                failure_count = self.task_failure_count.get(task["task_id"], 0)
                self.task_failure_count[task["task_id"]] = failure_count + 1
                await asyncio.sleep(1.0)
                if validator_id:
                    async with self._worker_lock:
                        validator_manager["release_validator_by_task_id"](task["task_id"])
                    self._broadcast_validator_states()
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
                validator_manager["release_validator_by_task_id"](task["task_id"])
            self._broadcast_executor_states()
            self._broadcast_validator_states()
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

        self._schedule_ready_tasks([self.task_map[id] for id in candidates if self.task_map.get(id)])

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
            validator_manager["release_validator_by_task_id"](task["task_id"])
        self._broadcast_executor_states()
        self._broadcast_validator_states()
        self.completed_tasks.add(task["task_id"])
        self.running_tasks.discard(task["task_id"])
        self.pending_tasks.discard(task["task_id"])
        self._update_task_status(task["task_id"], "execution-failed")
        dependents = self.reverse_dependency_index.get(task["task_id"], [])
        self._schedule_ready_tasks([self.task_map[id] for id in dependents if self.task_map.get(id)])

    def _are_dependencies_satisfied(self, task: Dict) -> bool:
        deps = task.get("dependencies") or []
        if not deps:
            return True
        return all(d in self.completed_tasks for d in deps)

    def _update_task_status(self, task_id: str, status: str) -> None:
        t = self.task_map.get(task_id)
        if t:
            t["status"] = status
        self._persist_execution()
        self._broadcast_task_states()

    def _broadcast_task_states(self) -> None:
        task_states = [{"task_id": t["task_id"], "status": t["status"]} for t in self.chain_cache]
        self._emit("task-states-update", {"tasks": task_states})

    def _broadcast_executor_states(self) -> None:
        executors = executor_manager["get_all_executors"]()
        stats = executor_manager["get_executor_stats"]()
        self._emit("executor-states-update", {"executors": executors, "stats": stats})

    def _broadcast_validator_states(self) -> None:
        validators = validator_manager["get_all_validators"]()
        stats = validator_manager["get_validator_stats"]()
        self._emit("validator-states-update", {"validators": validators, "stats": stats})

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
                    validator_manager["release_validator_by_task_id"](task_id)

        self._broadcast_executor_states()
        self._broadcast_validator_states()

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
        plan_id: Optional[str] = None,
        execution: Optional[Dict] = None,
    ) -> None:
        if self.is_running:
            raise ValueError("Cannot set layout while execution is running")
        self.timetable_layout = layout
        self.plan_id = plan_id
        self.chain_cache = []
        task_by_id = {}
        if execution:
            for t in execution.get("tasks") or []:
                if t.get("task_id"):
                    task_by_id[t["task_id"]] = t
        grid = layout.get("grid", [])
        isolated_tasks = layout.get("isolatedTasks", [])
        for row in grid:
            for cell in row or []:
                if cell and cell.get("task_id"):
                    tid = cell["task_id"]
                    full = task_by_id.get(tid, {})
                    status = full.get("status") or cell.get("status") or "undone"
                    self.chain_cache.append({
                        "task_id": tid,
                        "dependencies": cell.get("dependencies") or [],
                        "status": status,
                        "description": full.get("description") or cell.get("description"),
                        "input": full.get("input") or cell.get("input"),
                        "output": full.get("output") or cell.get("output"),
                        "validation": full.get("validation") or cell.get("validation"),
                    })
        for t in isolated_tasks or []:
            if t and t.get("task_id"):
                tid = t["task_id"]
                full = task_by_id.get(tid, {})
                status = full.get("status") or t.get("status") or "undone"
                self.chain_cache.append({
                    "task_id": tid,
                    "dependencies": t.get("dependencies") or [],
                    "status": status,
                    "description": full.get("description") or t.get("description"),
                    "input": full.get("input") or t.get("input"),
                    "output": full.get("output") or t.get("output"),
                    "validation": full.get("validation") or t.get("validation"),
                })

    async def stop_async(self) -> None:
        """Stop execution: signal abort (stops API calls/token use), cancel tasks, release workers."""
        self.is_running = False
        if self.abort_event:
            self.abort_event.set()
        task_ids = list(self.task_tasks.keys())
        for task_id in task_ids:
            asyncio_task = self.task_tasks.get(task_id)
            if asyncio_task and not asyncio_task.done():
                asyncio_task.cancel()
        async with self._worker_lock:
            for task_id in task_ids:
                executor_manager["release_executor_by_task_id"](task_id)
                validator_manager["release_validator_by_task_id"](task_id)
        self.task_tasks.clear()
        self.running_tasks.clear()
        self._broadcast_executor_states()
        self._broadcast_validator_states()
