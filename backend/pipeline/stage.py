"""Stage base class for the pipeline."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from enum import Enum

from agno.agent import Agent, RunEvent
from backend.config import settings

log = logging.getLogger(__name__)


class StageState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class Stage:
    """Lifecycle, SSE broadcasting, and LLM streaming for all pipeline stages.

    Unified SSE event format: {stage, phase?, chunk?, status?, task_id?}
      - With chunk: streaming content, left panel renders
      - Without chunk: done signal, right panel fetches DB
      - With status: task intermediate state (running/verifying/retrying)
    """

    # Class-level rate limiter: ensures minimum gap between consecutive LLM calls
    _rate_gate: asyncio.Lock | None = None
    _rate_last_ts: float = 0

    def __init__(self, name: str, db=None, broadcast=None):
        self.name = name
        self.state = StageState.IDLE
        self.output = ""
        self.db = db
        self._broadcast = broadcast or (lambda event: None)
        self._stop_requested = False
        self._current_phase: str = ""
        self._api_semaphore: asyncio.Semaphore | None = None  # set by orchestrator

    async def run(self) -> str:
        self.state = StageState.RUNNING
        try:
            self.output = await self._execute()
            self.state = StageState.COMPLETED
            self._send()  # done signal
            return self.output
        except asyncio.CancelledError:
            if self.state == StageState.RUNNING:
                self.state = StageState.IDLE
            return self.output
        except Exception as e:
            self.state = StageState.FAILED
            self._send(error=str(e))
            raise

    async def _execute(self) -> str:
        raise NotImplementedError

    def request_stop(self):
        self._stop_requested = True

    def pause(self):
        self.state = StageState.PAUSED
        self._send()

    def prepare_resume(self):
        self.output = ""
        self._stop_requested = False

    def mark_completed(self, output: str):
        self.output = output
        self.state = StageState.COMPLETED

    def configure(self, broadcast, semaphore):
        self._broadcast = broadcast
        self._api_semaphore = semaphore

    def retry(self):
        self.output = ""
        self.state = StageState.IDLE
        self._stop_requested = False
        self._current_phase = ""

    def get_status(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "phase": self._current_phase,
            "output_length": len(self.output),
        }

    # ------------------------------------------------------------------
    # Unified SSE: {stage, phase?, chunk?, status?, task_id?, error?}
    # ------------------------------------------------------------------

    def _send(self, chunk: dict | None = None, **extra):
        event = {"stage": self.name}
        if self._current_phase:
            event["phase"] = self._current_phase
        if chunk:
            event["chunk"] = chunk
            if self.db:
                self.db.append_log(
                    stage=self.name,
                    call_id=chunk.get("call_id", ""),
                    text=chunk.get("text", ""),
                    level=chunk.get("level", 2),
                    task_id=extra.get("task_id"),
                    label=chunk.get("label", False),
                )
        if extra:
            event.update(extra)
        self._broadcast(event)

    # ------------------------------------------------------------------
    # LLM streaming
    # ------------------------------------------------------------------

    async def _rate_limit(self):
        """Ensure minimum gap between consecutive LLM calls (class-wide)."""
        interval = settings.api_request_interval
        if interval <= 0:
            return
        if Stage._rate_gate is None:
            Stage._rate_gate = asyncio.Lock()
        async with Stage._rate_gate:
            wait = Stage._rate_last_ts + interval - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            Stage._rate_last_ts = time.monotonic()

    async def _stream_llm(self, model, tools, instruction: str, user_text: str,
                          call_id: str, content_level: int = 2,
                          timeout: float | None = None, max_retries: int = 3,
                          label: bool = False, label_level: int | None = None,
                          task_id: str = "", _skip_semaphore: bool = False) -> str:
        if timeout is None:
            timeout = float(settings.agent_session_timeout_seconds())
        extra = {"task_id": task_id} if task_id else {}
        await self._rate_limit()
        sem = contextlib.nullcontext() if (_skip_semaphore or not self._api_semaphore) else self._api_semaphore
        async with sem:
            if label:
                lvl = label_level if label_level is not None else content_level
                self._send(chunk={"text": call_id, "call_id": call_id, "label": True, "level": lvl}, **extra)
            for attempt in range(max_retries):
                if self._stop_requested:
                    raise asyncio.CancelledError()
                try:
                    return await self._run_agent(model, tools, instruction, user_text,
                                                 call_id, content_level, timeout, extra)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    log.error("_stream_llm error (attempt %d/%d, call_id=%s): %s: %s",
                              attempt + 1, max_retries, call_id, type(e).__name__, e)
                    err_label = "TIMEOUT" if isinstance(e, TimeoutError) else "ERROR"
                    if attempt >= max_retries - 1:
                        self._send(chunk={
                            "text": f"\n[{err_label}] Failed after {max_retries} attempts: {e}\n",
                            "call_id": call_id, "level": content_level,
                        }, **extra)
                        raise
                    delay = 2 ** attempt * 5
                    self._send(chunk={
                        "text": f"\n[{err_label}] Retry {attempt + 1}/{max_retries - 1} in {delay}s — {e}\n",
                        "call_id": call_id, "level": content_level,
                    }, **extra)
                    await asyncio.sleep(delay)
        return ""

    async def _run_agent(self, model, tools, instruction, user_text,
                         call_id, content_level, timeout, extra) -> str:
        result = ""
        agent = Agent(model=model, instructions=instruction, tools=tools, markdown=True)
        async with asyncio.timeout(timeout):
            async for event in agent.arun(user_text, stream=True, stream_events=True):
                if self._stop_requested:
                    raise asyncio.CancelledError()
                content = self._handle_stream_event(event, call_id, content_level, extra)
                if content:
                    result += content
        return result

    def _handle_stream_event(self, event, call_id, content_level, extra) -> str | None:
        if event.event == RunEvent.run_content:
            if event.content:
                text = str(event.content)
                self._send(chunk={"text": text, "call_id": call_id, "level": content_level}, **extra)
                return text
        elif event.event == RunEvent.reasoning_step:
            if event.content:
                rid = event.call_id or "Thinking"
                self._send(chunk={"text": rid, "call_id": rid, "label": True, "level": content_level}, **extra)
                self._send(chunk={"text": str(event.content), "call_id": rid, "level": content_level}, **extra)
        elif event.event == RunEvent.tool_call_started:
            tool_name = event.tool.tool_name if event.tool else "tool"
            tcid = getattr(event.tool, "tool_call_id", "") or f"{tool_name}_{id(event.tool)}" if event.tool else tool_name
            tool_cid = f"Tool: {tcid}"
            self._send(chunk={"text": f"Tool: {tool_name}", "call_id": tool_cid, "label": True, "level": content_level}, **extra)
            if event.tool and event.tool.tool_args:
                args_str = ", ".join(f"{k}={v}" for k, v in event.tool.tool_args.items())
                self._send(chunk={"text": f"{tool_name}({args_str})", "call_id": tool_cid, "level": content_level}, **extra)
        elif event.event == RunEvent.tool_call_completed:
            tool_name = event.tool.tool_name if event.tool else "tool"
            tcid = getattr(event.tool, "tool_call_id", "") or f"{tool_name}_{id(event.tool)}" if event.tool else tool_name
            cid = f"Tool: {tcid}"
            result_text = str(event.content)[:500] if event.content else ""
            if result_text:
                self._send(chunk={"text": result_text, "call_id": cid, "level": content_level}, **extra)
        elif event.event == RunEvent.run_error:
            error_msg = str(event.content) if event.content else "Unknown agent error"
            raise RuntimeError(f"Agno agent error: {error_msg}")
        elif event.event == RunEvent.run_completed:
            self._record_metrics(event.metrics)
        return None

    def _record_metrics(self, metrics):
        if metrics and self.db:
            meta = self.db.get_meta()
            self.db.update_meta(
                tokens_input=meta.get("tokens_input", 0) + (metrics.input_tokens or 0),
                tokens_output=meta.get("tokens_output", 0) + (metrics.output_tokens or 0),
                tokens_total=meta.get("tokens_total", 0) + (metrics.total_tokens or 0),
            )
