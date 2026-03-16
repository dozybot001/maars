"""Emit/persist helper mixin for Task ExecutionRunner."""

import asyncio
from typing import Any

from loguru import logger

from db import save_execution


class RunnerEmitMixin:
    def _persist_execution(self) -> None:
        """Persist chain_cache to execution.json. Serialized via _persist_lock to avoid concurrent write races."""
        if self.idea_id and self.plan_id and self.chain_cache:
            try:
                asyncio.create_task(self._persist_execution_async())
            except RuntimeError:
                pass

    async def _persist_execution_async(self) -> None:
        """Serialized persist: prevents multiple save_execution from overwriting each other with stale data."""
        async with self._persist_lock:
            if self.idea_id and self.plan_id and self.chain_cache:
                try:
                    await save_execution({"tasks": list(self.chain_cache)}, self.idea_id, self.plan_id)
                except Exception as e:
                    logger.warning("Failed to persist execution: %s", e)

    def _emit(self, event: str, data: dict) -> None:
        """Emit event to all clients (fire-and-forget)."""
        if hasattr(self.sio, "emit"):
            try:
                asyncio.create_task(self.sio.emit(event, data, to=self.session_id))
            except RuntimeError:
                pass

    async def _emit_await(self, event: str, data: dict) -> None:
        """Emit event and await; use for order-sensitive events (e.g. thinking chunks)."""
        if hasattr(self.sio, "emit"):
            try:
                await self.sio.emit(event, data, to=self.session_id)
            except Exception as e:
                logger.warning("%s emit failed: %s", event, e)

    async def _safe_emit_thinking(
        self,
        *,
        chunk: str,
        task_id: str | None,
        operation: str,
        payload_extras: dict | None = None,
    ) -> None:
        """Optional helper for future emit consolidation; currently unused by caller."""
        payload: dict[str, Any] = {
            "chunk": chunk,
            "source": "task",
            "taskId": task_id,
            "operation": operation,
        }
        if payload_extras:
            payload.update(payload_extras)
        await self._emit_await("task-thinking", payload)
