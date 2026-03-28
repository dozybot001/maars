"""AgentSession — multi-agent lifecycle manager.

Replaces PipelineOrchestrator when ``MAARS_ARCHITECTURE=agents``.
Manages the three persistent agents (Orchestrator, Scholar, Critic),
SSE broadcast, and session lifecycle (start/stop/resume/retry).

The old PipelineOrchestrator is untouched and remains the default.
"""

from __future__ import annotations

import asyncio
from typing import Callable

from backend.db import ResearchDB
from backend.agents.base import PersistentAgent


class AgentSession:
    """Manages a multi-agent research session."""

    def __init__(self):
        self.research_input = ""
        self.db = ResearchDB()

        # SSE subscribers — same pattern as PipelineOrchestrator
        self._subscribers: list[asyncio.Queue] = []

        # Agents — populated by configure()
        self.orchestrator: PersistentAgent | None = None
        self.scholar: PersistentAgent | None = None
        self.critic: PersistentAgent | None = None

        # Background task
        self._task: asyncio.Task | None = None
        self._current_phase = "idle"

    # ------------------------------------------------------------------
    # Configuration: inject agents after construction
    # ------------------------------------------------------------------

    def configure(
        self,
        orchestrator: PersistentAgent,
        scholar: PersistentAgent,
        critic: PersistentAgent,
    ):
        """Wire agents into the session. Called from main.py factory."""
        self.orchestrator = orchestrator
        self.scholar = scholar
        self.critic = critic

    # ------------------------------------------------------------------
    # SSE subscriber management (mirrors PipelineOrchestrator)
    # ------------------------------------------------------------------

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=512)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    def _broadcast(self, event: dict):
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def start(self, research_input: str):
        """Start a multi-agent research session."""
        await self._cancel_task()

        self.research_input = research_input
        self.db.create_session(research_input)
        self.db.save_idea(research_input)

        # Reset all agents
        for agent in (self.orchestrator, self.scholar, self.critic):
            if agent:
                agent.reset()

        self._task = asyncio.create_task(self._run())

    async def _run(self):
        """Run the Orchestrator agent's ReAct session.

        The Orchestrator has tools (consult_scholar, request_critique,
        decompose, dispatch_workers, emit_phase, write_paper) and
        decides the workflow autonomously.
        """
        try:
            self._set_phase("refine")

            # The Orchestrator drives everything via a single invoke()
            # with the research idea. Its tools do the actual work.
            result = await self.orchestrator.invoke(
                f"Research idea:\n{self.research_input}\n\n"
                f"Begin the research process. Use your tools to refine the idea, "
                f"decompose into tasks, execute research, and write the paper."
            )

            self._set_phase("completed")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._broadcast({
                "stage": self._current_phase,
                "type": "error",
                "data": {"message": str(e)},
            })
            self._broadcast({
                "stage": self._current_phase,
                "type": "state",
                "data": "failed",
            })

    async def stop(self):
        """Pause the session."""
        for agent in (self.orchestrator, self.scholar, self.critic):
            if agent:
                agent.request_stop()
        await self._cancel_task()
        self._broadcast({
            "stage": self._current_phase,
            "type": "state",
            "data": "paused",
        })

    async def resume(self):
        """Resume from checkpoint (Phase 5 — not yet implemented)."""
        # TODO: rebuild agent state from DB, continuation prompt
        await self.start(self.research_input)

    async def retry(self):
        """Reset everything and start from scratch."""
        await self._cancel_task()
        for agent in (self.orchestrator, self.scholar, self.critic):
            if agent:
                agent.reset()
        if self.db:
            self.db.clear_tasks()
            self.db.clear_plan()
        await self.start(self.research_input)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        running = self._task is not None and not self._task.done()
        return {
            "input": self.research_input,
            "architecture": "agents",
            "phase": self._current_phase,
            "running": running,
            "agents": [
                {"name": a.name, "history_length": len(a.history)}
                for a in (self.orchestrator, self.scholar, self.critic)
                if a
            ],
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _set_phase(self, phase: str):
        """Update current phase and broadcast state event."""
        self._current_phase = phase
        if phase == "completed":
            self._broadcast({"stage": "write", "type": "state", "data": "completed"})
        elif phase in ("refine", "research", "write"):
            self._broadcast({"stage": phase, "type": "state", "data": "running"})

    async def _cancel_task(self):
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
