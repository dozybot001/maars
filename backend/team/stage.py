"""TeamStage — shared base for multi-agent stages using Agno Team coordinate mode.

Provides the generic execution loop (run) and event mapping (_handle_event).
Subclasses only define: _create_team(), _finalize(), load_input(), and two config attrs.
"""

import asyncio
import logging

from backend.pipeline.stage import Stage, StageState

log = logging.getLogger(__name__)


class TeamStage(Stage):
    """Base class for stages that execute via Agno Team coordinate mode.

    Subclasses must set:
        _member_map     — dict mapping member_id substrings to display labels
        _capture_member — label of the member whose content becomes stage output

    Subclasses must override:
        _create_team()  — build and return the Agno Team
        _finalize()     — persist output to DB and emit document event
        load_input()    — return the input string for the Team
    """

    _member_map: dict[str, str] = {}
    _capture_member: str = ""

    def __init__(self, name: str, model=None, db=None, **kwargs):
        super().__init__(name=name, db=db, **kwargs)
        self._model = model

    def load_input(self) -> str:
        raise NotImplementedError

    def _create_team(self):
        raise NotImplementedError

    def _finalize(self) -> str:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run(self) -> str:
        """Execute the stage: create Team → stream events → capture output → finalize."""
        self._run_id += 1
        my_run_id = self._run_id
        self.state = StageState.RUNNING
        self._emit("state", self.state.value)

        try:
            team = self._create_team()
            input_text = self.load_input()

            self._emit("chunk", {
                "text": self.name.capitalize(),
                "call_id": self.name.capitalize(),
                "label": True, "level": 1,
            })

            state = {"output_content": "", "current_member": None}

            async with asyncio.timeout(3600):
                async for event in await team.arun(
                    input_text, stream=True, stream_events=True,
                ):
                    if self._is_stale(my_run_id):
                        return self.output
                    evt = getattr(event, "event", "")
                    self._handle_event(evt, event, state)

            self.output = state["output_content"]
            if not self.output:
                log.warning("%s: no content captured from primary member", self.name)

            self.output = self._finalize()
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

    # ------------------------------------------------------------------
    # Event mapping: Agno Team/Member events → MAARS SSE
    # ------------------------------------------------------------------

    def _resolve_member(self, member_id: str) -> str:
        """Match a member_id to its display label via _member_map."""
        for key, label in self._member_map.items():
            if key in member_id:
                return label
        return member_id or "Member"

    def _handle_event(self, evt: str, event, state: dict):
        """Map a single Agno streaming event to MAARS SSE emissions.

        ``state`` keys: ``output_content`` (captured text), ``current_member`` (active label).
        """

        # --- Team-level: leader delegates to a member ---
        if evt == "TeamToolCallStarted":
            tool = getattr(event, "tool", None)
            if tool and getattr(tool, "tool_name", "") == "delegate_task_to_member":
                args = getattr(tool, "tool_args", {}) or {}
                member_id = args.get("member_id", "")
                label = self._resolve_member(member_id)
                # Reset capture buffer when primary member starts a new delegation
                if label == self._capture_member:
                    state["output_content"] = ""
                state["current_member"] = label
                self._emit("chunk", {
                    "text": label, "call_id": label,
                    "label": True, "level": 2,
                })

        # --- Team-level: delegation completed ---
        elif evt == "TeamToolCallCompleted":
            pass

        # --- Team-level: leader's own content (synthesis) ---
        elif evt == "TeamRunContent":
            content = getattr(event, "content", None)
            if content:
                self._emit("chunk", {
                    "text": str(content), "call_id": "Summary",
                    "level": 2,
                })

        # --- Team-level: run completed with metrics ---
        elif evt == "TeamRunCompleted":
            metrics = getattr(event, "metrics", None)
            if metrics:
                self._emit("tokens", {
                    "input": getattr(metrics, "input_tokens", 0) or 0,
                    "output": getattr(metrics, "output_tokens", 0) or 0,
                    "total": getattr(metrics, "total_tokens", 0) or 0,
                })

        # --- Team/member error ---
        elif evt in ("TeamRunError", "RunError"):
            error_msg = str(getattr(event, "content", "")) or "Unknown error"
            raise RuntimeError(f"{self.name} team error: {error_msg}")

        # --- Member: streaming content ---
        elif evt == "RunContent":
            content = getattr(event, "content", None)
            if content:
                text = str(content)
                member = state["current_member"] or self.name.capitalize()
                self._emit("chunk", {
                    "text": text, "call_id": member, "level": 3,
                })
                if member == self._capture_member:
                    state["output_content"] += text

        # --- Member: tool call started ---
        elif evt == "ToolCallStarted":
            tool = getattr(event, "tool", None)
            if tool:
                tool_name = getattr(tool, "tool_name", "tool") or "tool"
                args = getattr(tool, "tool_args", {}) or {}
                args_str = ", ".join(f"{k}={v}" for k, v in args.items()) if args else ""
                self._emit("chunk", {
                    "text": f"Tool: {tool_name}",
                    "call_id": f"Tool: {tool_name}",
                    "label": True, "level": 3,
                })
                if args_str:
                    self._emit("chunk", {
                        "text": f"{tool_name}({args_str})",
                        "call_id": f"Tool: {tool_name}",
                        "level": 3,
                    })

        # --- Member: tool call completed ---
        elif evt == "ToolCallCompleted":
            tool = getattr(event, "tool", None)
            if tool:
                tool_name = getattr(tool, "tool_name", "tool") or "tool"
                result_text = str(getattr(event, "content", ""))[:500]
                if result_text:
                    self._emit("chunk", {
                        "text": result_text,
                        "call_id": f"Tool: {tool_name}",
                        "level": 3,
                    })

        # --- Member: reasoning ---
        elif evt == "ReasoningStep":
            content = getattr(event, "content", None)
            if content:
                self._emit("chunk", {
                    "text": str(content),
                    "call_id": "Thinking",
                    "label": True, "level": 3,
                })

        # --- Member: run completed (token metrics) ---
        elif evt == "RunCompleted":
            metrics = getattr(event, "metrics", None)
            if metrics:
                self._emit("tokens", {
                    "input": getattr(metrics, "input_tokens", 0) or 0,
                    "output": getattr(metrics, "output_tokens", 0) or 0,
                    "total": getattr(metrics, "total_tokens", 0) or 0,
                })
