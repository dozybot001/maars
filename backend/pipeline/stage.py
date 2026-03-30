"""Stage base classes for the pipeline.

Stage          — lifecycle + SSE broadcasting (shared by ALL stages)
AgentStage     — single-agent execution model (Refine, Research)

Write stage inherits Stage directly (multi-agent, no AgnoClient).
"""

from __future__ import annotations

import asyncio
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.agno.client import AgnoClient


class StageState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


# ======================================================================
# Stage — shared lifecycle for all stages
# ======================================================================

class Stage:
    """Lifecycle, SSE broadcasting, and cancellation for all pipeline stages.

    Subclasses must implement ``run()``.
    """

    def __init__(self, name: str, db=None, broadcast=None, **kwargs):
        self.name = name
        self.state = StageState.IDLE
        self.output = ""
        self.db = db
        self._broadcast = broadcast or (lambda event: None)
        self._run_id = 0

    # ------------------------------------------------------------------
    # Execution (to be overridden)
    # ------------------------------------------------------------------

    async def run(self) -> str:
        raise NotImplementedError

    def retry(self):
        self._run_id += 1
        self.output = ""
        self.state = StageState.IDLE
        self._emit("state", self.state.value)

    def get_status(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "output_length": len(self.output),
        }

    # ------------------------------------------------------------------
    # SSE broadcasting
    # ------------------------------------------------------------------

    def _emit(self, event_type: str, data):
        self._broadcast({
            "stage": self.name,
            "type": event_type,
            "data": data,
        })

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------

    def _is_stale(self, my_run_id: int) -> bool:
        return my_run_id != self._run_id


# ======================================================================
# AgentStage — single-agent execution via AgnoClient
# ======================================================================

class AgentStage(Stage):
    """Stage that executes via an AgnoClient instance.

    Provides:
    - ``_stream_llm()`` with retry and timeout
    - Default ``run()`` that does: load_input → LLM call → finalize
    - ``system_instruction``, ``rounds`` for single-session agents

    RefineStage uses the default run(). ResearchStage overrides run()
    but reuses _stream_llm() for individual agent calls within its workflow.
    """

    system_instruction: str = ""

    def __init__(self, name: str, llm_client: AgnoClient | None = None, **kwargs):
        super().__init__(name=name, **kwargs)
        self.llm_client = llm_client
        self.rounds: list[dict] = []

    # ------------------------------------------------------------------
    # Hooks for subclasses
    # ------------------------------------------------------------------

    def load_input(self) -> str:
        """Load this stage's input from DB. Override per stage."""
        return ""

    def get_round_label(self, round_index: int) -> str:
        return ""

    def finalize(self) -> str:
        """Finalize output and persist to DB. Override per stage."""
        return self.output

    # ------------------------------------------------------------------
    # Default single-pass execution
    # ------------------------------------------------------------------

    async def run(self) -> str:
        """Execute: load input → LLM call → save to DB."""
        self._run_id += 1
        my_run_id = self._run_id

        self.state = StageState.RUNNING
        self._emit("state", self.state.value)

        input_text = self.load_input()

        try:
            if self._is_stale(my_run_id):
                return self.output

            messages = []
            if self.system_instruction:
                messages.append({"role": "system", "content": self.system_instruction})
            messages.append({"role": "user", "content": input_text})
            call_id = self.get_round_label(0) or self.name
            self._emit("chunk", {"text": call_id, "call_id": call_id, "label": True, "level": 1})

            response = await self._stream_llm(
                self.llm_client, messages, call_id, my_run_id, content_level=2,
            )
            self.output += response

            if self._is_stale(my_run_id):
                return self.output

            self.rounds.append({"role": "assistant", "content": response})

            self.output = self.finalize()
            self.state = StageState.COMPLETED
            self._emit("state", self.state.value)
            return self.output

        except asyncio.CancelledError:
            if not self._is_stale(my_run_id):
                self.state = StageState.IDLE
                self._emit("state", self.state.value)
            return self.output

        except Exception as e:
            if not self._is_stale(my_run_id):
                self.state = StageState.FAILED
                self._emit("error", {"message": str(e)})
                self._emit("state", self.state.value)
            raise

    def retry(self):
        self._run_id += 1
        self.output = ""
        self.rounds = []
        self.state = StageState.IDLE
        self._emit("state", self.state.value)

    def get_status(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "output_length": len(self.output),
            "rounds": len(self.rounds),
        }

    # ------------------------------------------------------------------
    # LLM streaming with retry
    # ------------------------------------------------------------------

    async def _stream_llm(self, client, messages: list[dict], call_id: str,
                          my_run_id: int, content_level: int = 2,
                          timeout: float = 1800, max_retries: int = 3) -> str:
        """Stream LLM response, dispatching events to frontend via SSE.
        Retries on timeout and transient API errors with exponential backoff.
        """
        for attempt in range(max_retries):
            result = ""
            try:
                async with asyncio.timeout(timeout):
                    async for event in client.stream(messages):
                        if self._is_stale(my_run_id):
                            return result
                        if event.type == "content":
                            self._emit("chunk", {"text": event.text, "call_id": call_id, "level": content_level})
                            result += event.text
                        elif event.type in ("think", "tool_call"):
                            self._emit("chunk", {"text": event.call_id, "call_id": event.call_id, "label": True, "level": content_level})
                            if event.text:
                                self._emit("chunk", {"text": event.text, "call_id": event.call_id, "level": content_level})
                        elif event.type == "tool_result":
                            if event.text:
                                self._emit("chunk", {"text": event.text, "call_id": event.call_id, "level": content_level})
                        elif event.type == "tokens":
                            self._emit("tokens", event.metadata)
                return result
            except (TimeoutError, RuntimeError) as e:
                is_last = attempt >= max_retries - 1
                label = "TIMEOUT" if isinstance(e, TimeoutError) else "API ERROR"
                if is_last:
                    self._emit("chunk", {
                        "text": f"\n[{label}] Failed after {max_retries} attempts: {e}\n",
                        "call_id": call_id,
                        "level": content_level,
                    })
                    if isinstance(e, RuntimeError):
                        raise
                else:
                    delay = 2 ** attempt * 5  # 5s, 10s, 20s
                    self._emit("chunk", {
                        "text": f"\n[{label}] Retry {attempt + 1}/{max_retries - 1} in {delay}s — {e}\n",
                        "call_id": call_id,
                        "level": content_level,
                    })
                    await asyncio.sleep(delay)
        return result
