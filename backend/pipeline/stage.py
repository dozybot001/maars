import asyncio
from enum import Enum

from backend.llm.client import LLMClient


class StageState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class BaseStage:
    """Base class for all pipeline stages.

    Each stage runs a multi-round LLM conversation. Concrete stages
    will override build_messages / is_complete once the specific
    LLM call flow is defined. For now the default implementation
    does a fixed number of rounds.
    """

    def __init__(self, name: str, llm_client: LLMClient | None = None, broadcast=None, max_rounds: int = 2):
        self.name = name
        self.state = StageState.IDLE
        self.output = ""
        self.rounds: list[dict] = []
        self.max_rounds = max_rounds

        self.llm_client = llm_client
        self._broadcast = broadcast or (lambda event: None)
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # starts unpaused
        self._run_id = 0  # generation counter — prevents stale coroutines from mutating state

    # ------------------------------------------------------------------
    # Methods to be overridden by concrete stages (later)
    # ------------------------------------------------------------------

    def build_messages(self, input_text: str, round_index: int) -> list[dict]:
        """Build LLM messages for the current round.

        Default implementation: system prompt with stage name + user input.
        Concrete stages will override this.
        """
        messages = [
            {"role": "system", "content": f"You are the {self.name} stage of a research pipeline."},
        ]
        if round_index == 0:
            messages.append({"role": "user", "content": input_text})
        else:
            # Include conversation history for subsequent rounds
            messages.extend(self.rounds)
            messages.append({"role": "user", "content": "Please continue and refine the previous output."})
        return messages

    def is_complete(self, response: str, round_index: int) -> bool:
        """Whether this stage needs more rounds. Default: fixed count."""
        return round_index >= self.max_rounds - 1

    def get_round_label(self, round_index: int) -> str:
        """Return a label for the current round. Override per stage."""
        return ""

    def process_response(self, response: str, round_index: int):
        """Hook called after each LLM round. Override to parse/process."""
        pass

    def finalize(self) -> str:
        """Hook called after all rounds complete. Returns final output for next stage."""
        return self.output

    def get_artifacts(self) -> dict | None:
        """Return stage-specific artifacts for DB persistence. Override per stage."""
        return None

    # ------------------------------------------------------------------
    # Execution control
    # ------------------------------------------------------------------

    async def run(self, input_text: str) -> str:
        """Execute the stage: multi-round LLM loop.

        Each invocation captures a run_id snapshot. If retry() is called
        while this coroutine is still running, _run_id increments and
        this coroutine becomes "stale" — it will stop mutating shared
        state and exit quietly.
        """
        self._run_id += 1
        my_run_id = self._run_id

        self._pause_event.set()
        self.state = StageState.RUNNING
        self._emit("state", self.state.value)

        round_index = 0
        try:
            while True:
                # Pause gate — blocks here if paused, then re-checks stale
                await self._pause_event.wait()
                if self._is_stale(my_run_id):
                    return self.output

                messages = self.build_messages(input_text, round_index)
                call_id = self.get_round_label(round_index) or f"round_{round_index}"
                self._emit("chunk", {"text": call_id, "call_id": call_id, "label": True})

                response = ""

                async for chunk in self.llm_client.stream(messages):
                    await self._pause_event.wait()
                    if self._is_stale(my_run_id):
                        break

                    response += chunk
                    self.output += chunk
                    self._emit("chunk", {"text": chunk, "call_id": call_id})

                if self._is_stale(my_run_id):
                    return self.output

                self.rounds.append({"role": "assistant", "content": response})
                self.process_response(response, round_index)

                if self.is_complete(response, round_index):
                    break
                round_index += 1

            self.output = self.finalize()
            self.state = StageState.COMPLETED
            self._emit("state", self.state.value)
            return self.output

        except asyncio.CancelledError:
            # Task was cancelled externally — don't touch state if stale
            if not self._is_stale(my_run_id):
                self.state = StageState.IDLE
                self._emit("state", self.state.value)
            return self.output

        except Exception as e:
            if not self._is_stale(my_run_id):
                self.state = StageState.FAILED
                self._emit("error", {"message": str(e)})
            raise

    def stop(self):
        """Pause execution at the next chunk boundary."""
        if self.state == StageState.RUNNING:
            self._pause_event.clear()
            self.state = StageState.PAUSED
            self._emit("state", self.state.value)

    def resume(self):
        """Resume from paused state."""
        if self.state == StageState.PAUSED:
            self._pause_event.set()
            self.state = StageState.RUNNING
            self._emit("state", self.state.value)

    def retry(self):
        """Cancel current execution, reset state, ready for re-run.

        Bumps _run_id so any in-flight coroutine becomes stale and
        stops touching shared state immediately.
        """
        self._run_id += 1  # invalidate any running coroutine
        self._pause_event.set()  # unblock if paused so the stale coroutine can exit
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
    # Internal
    # ------------------------------------------------------------------

    def _is_stale(self, my_run_id: int) -> bool:
        """Check if this coroutine has been superseded by a newer run."""
        return my_run_id != self._run_id

    def _emit(self, event_type: str, data):
        """Broadcast an event to all SSE subscribers."""
        self._broadcast({
            "stage": self.name,
            "type": event_type,
            "data": data,
        })

