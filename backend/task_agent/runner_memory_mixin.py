"""Attempt-memory and execution-context helper mixin for Task ExecutionRunner."""

import time
from typing import Any, Dict, Optional, Set

from loguru import logger


class RunnerMemoryMixin:
    @staticmethod
    def _runner_module_db_call(name: str):
        # Keep compatibility with existing tests that monkeypatch task_agent.runner DB symbols.
        from . import runner as runner_mod

        fn = getattr(runner_mod, name, None)
        if fn is None:
            raise AttributeError(f"runner module has no DB helper '{name}'")
        return fn

    async def _record_task_attempt_failure(
        self,
        *,
        task_id: str,
        phase: str,
        attempt: int,
        error: str,
        will_retry: bool,
        decision: Optional[Dict[str, Any]] = None,
    ) -> None:
        decision = decision or {}
        history = self.task_attempt_history.setdefault(task_id, [])
        history.append({
            "attempt": attempt,
            "phase": phase,
            "error": (error or "").strip(),
            "willRetry": bool(will_retry),
            "decision": str(decision.get("action") or ""),
            "category": str(decision.get("category") or ""),
            "summary": str(decision.get("summary") or ""),
            "ts": int(time.time() * 1000),
        })
        if len(history) > 8:
            self.task_attempt_history[task_id] = history[-8:]
        if self.research_id:
            latest = self.task_attempt_history.get(task_id, [])[-1]
            save_fn = self._runner_module_db_call("save_task_attempt_memory")
            await save_fn(
                self.research_id,
                task_id,
                int(attempt),
                {
                    "attempt": int(attempt),
                    "phase": phase,
                    "error": latest.get("error") or "",
                    "willRetry": bool(will_retry),
                    "decision": latest.get("decision") or "",
                    "category": latest.get("category") or "",
                    "summary": latest.get("summary") or "",
                    "ts": latest.get("ts"),
                },
            )

    async def _load_task_attempt_memories(self) -> None:
        self.task_attempt_history.clear()
        if not self.research_id:
            return
        try:
            list_fn = self._runner_module_db_call("list_task_attempt_memories")
            rows = await list_fn(self.research_id)
        except Exception:
            logger.exception("Failed to load task attempt memories research_id={}", self.research_id)
            return
        grouped: Dict[str, list[Dict[str, Any]]] = {}
        for row in rows or []:
            task_id = str(row.get("taskId") or "").strip()
            if not task_id:
                continue
            data = row.get("data") or {}
            grouped.setdefault(task_id, []).append(
                {
                    "attempt": int(data.get("attempt") or row.get("attempt") or 0),
                    "phase": str(data.get("phase") or "execution"),
                    "error": str(data.get("error") or ""),
                    "willRetry": bool(data.get("willRetry")),
                    "decision": str(data.get("decision") or ""),
                    "category": str(data.get("category") or ""),
                    "summary": str(data.get("summary") or ""),
                    "ts": int(data.get("ts") or 0),
                }
            )
        for task_id, items in grouped.items():
            self.task_attempt_history[task_id] = sorted(items, key=lambda x: (x.get("attempt") or 0, x.get("ts") or 0))[-8:]

    async def _clear_attempt_history_for_tasks(self, task_ids: Set[str]) -> None:
        for task_id in set(task_ids or set()):
            self.task_attempt_history.pop(task_id, None)
            if self.research_id:
                try:
                    delete_fn = self._runner_module_db_call("delete_task_attempt_memories")
                    await delete_fn(self.research_id, task_id)
                except Exception:
                    logger.exception("Failed to clear task attempt memories research_id={} task_id={}", self.research_id, task_id)

    def _build_task_execution_context(
        self,
        task: Dict[str, Any],
        resolved_inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        task_id = task.get("task_id") or ""
        deps = task.get("dependencies") or []
        completed = sorted([tid for tid in self.completed_tasks if tid in set(deps)])
        pending = sorted([tid for tid in deps if tid not in self.completed_tasks])
        history = self.task_attempt_history.get(task_id, [])
        latest_failure = history[-1] if history else None

        done_count = 0
        running_count = 0
        failed_count = 0
        for t in self.chain_cache:
            status = str((t or {}).get("status") or "undone")
            if status == "done":
                done_count += 1
            elif status == "doing":
                running_count += 1
            elif status in ("execution-failed", "validation-failed"):
                failed_count += 1

        output_spec = task.get("output") or {}
        validation_spec = task.get("validation") or {}
        input_keys = sorted(list((resolved_inputs or {}).keys())) if isinstance(resolved_inputs, dict) else []

        context: Dict[str, Any] = {
            "globalGoal": (self._idea_text or "").strip(),
            "planContext": {
                "executionRunId": self.execution_run_id,
                "currentTaskId": task_id,
                "progress": {
                    "done": done_count,
                    "running": running_count,
                    "failed": failed_count,
                    "total": len(self.chain_cache),
                },
                "dependencies": {
                    "all": deps,
                    "completed": completed,
                    "pending": pending,
                },
            },
            "taskContract": {
                "description": task.get("description") or "",
                "inputKeys": input_keys,
                "outputFormat": output_spec.get("format") or "",
                "outputDescription": output_spec.get("description") or "",
                "validationCriteria": (validation_spec.get("criteria") or []) if isinstance(validation_spec, dict) else [],
            },
        }

        if latest_failure:
            context["retryMemory"] = {
                "attempt": latest_failure.get("attempt"),
                "phase": latest_failure.get("phase") or "execution",
                "lastFailure": latest_failure.get("error") or "",
                "historyCount": len(history),
                "doNext": [
                    "Reuse existing files and artifacts before creating new ones",
                    "Take the shortest path to produce required output and call Finish",
                ],
                "dontNext": [
                    "Do not repeat identical failing commands without a change",
                    "Do not keep exploring once output spec is satisfied",
                ],
            }

        return context
