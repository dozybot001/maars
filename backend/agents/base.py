"""PersistentAgent — base class for all MAARS agents.

Wraps an LLMClient with accumulated conversation history so that
Scholar/Critic/Orchestrator maintain context across multiple invocations
within a single research session.
"""

from __future__ import annotations

import json
from typing import Callable

from backend.db import ResearchDB
from backend.llm.client import LLMClient, StreamEvent


class PersistentAgent:
    """An LLM-backed agent that accumulates conversation history.

    Each ``invoke()`` call appends the user message and assistant response
    to ``self.history``, so the agent "remembers" earlier interactions.
    All StreamEvents are broadcast to the frontend via ``_broadcast``.
    """

    def __init__(
        self,
        name: str,
        system_prompt: str,
        llm_client: LLMClient,
        db: ResearchDB | None = None,
        broadcast: Callable | None = None,
    ):
        self.name = name
        self.system_prompt = system_prompt
        self.llm_client = llm_client
        self.db = db
        self._broadcast = broadcast or (lambda event: None)
        self.history: list[dict] = []
        self._stop_requested = False

    # ------------------------------------------------------------------
    # Core: invoke
    # ------------------------------------------------------------------

    async def invoke(self, message: str) -> str:
        """Send a message to this agent, get a response.

        The exchange (user + assistant) is appended to history so
        subsequent invocations see the full conversation.
        """
        self._stop_requested = False

        # Build message list: system + history + new user message
        messages: list[dict] = [
            {"role": "system", "content": self.system_prompt},
        ]
        messages.extend(self.history)
        messages.append({"role": "user", "content": message})

        # Emit agent-level event
        call_id = f"{self.name}"
        self._emit("agent_state", {"agent": self.name, "status": "thinking"})
        self._emit("chunk", {"text": call_id, "call_id": call_id, "label": True})

        # Stream LLM response
        response = ""
        async for event in self.llm_client.stream(messages):
            if self._stop_requested:
                break
            response += self._dispatch_stream(event, call_id)

        # Accumulate history
        self.history.append({"role": "user", "content": message})
        self.history.append({"role": "assistant", "content": response})

        self._emit("agent_state", {"agent": self.name, "status": "idle"})
        return response

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def request_stop(self):
        """Signal the agent to stop after the current event."""
        self._stop_requested = True
        self.llm_client.request_stop()

    def reset(self):
        """Clear conversation history (for retry)."""
        self.history.clear()
        self.llm_client.reset()

    # ------------------------------------------------------------------
    # Checkpoint: persist / restore
    # ------------------------------------------------------------------

    def save_checkpoint(self):
        """Persist a summary of agent state to DB for resume."""
        if not self.db:
            return
        data = {
            "name": self.name,
            "history_length": len(self.history),
            "last_exchange": self.history[-2:] if len(self.history) >= 2 else [],
        }
        self.db.save_agent_state(self.name, data)

    def load_checkpoint(self) -> dict | None:
        """Load agent state from DB. Returns None if no checkpoint."""
        if not self.db:
            return None
        return self.db.get_agent_state(self.name)

    # ------------------------------------------------------------------
    # Broadcast helpers
    # ------------------------------------------------------------------

    def _emit(self, event_type: str, data):
        """Broadcast an event tagged with this agent's name."""
        self._broadcast({
            "stage": "research",  # agents operate within the research "phase"
            "type": event_type,
            "data": data,
        })

    def _dispatch_stream(self, event: StreamEvent, call_id: str) -> str:
        """Convert StreamEvent to broadcast event. Returns content text."""
        if event.type == "content":
            self._emit("chunk", {"text": event.text, "call_id": call_id})
            return event.text
        if event.type in ("think", "tool_call", "tool_result"):
            self._emit("chunk", {
                "text": event.call_id,
                "call_id": event.call_id,
                "label": True,
            })
            if event.text:
                self._emit("chunk", {"text": event.text, "call_id": event.call_id})
        elif event.type == "tokens":
            self._emit("tokens", event.metadata)
        return ""
