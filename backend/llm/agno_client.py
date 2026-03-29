"""Agno Agent → LLMClient adapter.

Pure adapter: takes messages (system + user), creates an Agno Agent
with system content as instruction, streams events back.
No baked-in instruction — all prompts come from the pipeline.
"""

import logging
from typing import AsyncIterator

from agno.agent import Agent, RunEvent

from backend.llm.client import LLMClient, StreamEvent

log = logging.getLogger(__name__)


class AgnoClient(LLMClient):

    def __init__(
        self,
        model,  # Agno model instance (Gemini, Claude, OpenAIResponses, etc.)
        tools: list | None = None,
    ):
        self._model = model
        self._tools = tools or []
        self._stop_requested = False

    def describe_capabilities(self) -> str:
        tool_descs = []
        for t in self._tools:
            name = getattr(t, 'name', type(t).__name__)
            tool_descs.append(f"- {name}")
        tools_str = "\n".join(tool_descs) if tool_descs else "(none)"
        return f"AI Agent (Agno) with multi-step reasoning. Model: {self._model.__class__.__name__}\nAvailable tools:\n{tools_str}"

    def request_stop(self):
        """Signal the Agent to stop after the current event."""
        self._stop_requested = True

    def reset(self):
        """Clear stop flag on pipeline restart."""
        self._stop_requested = False

    async def stream(self, messages: list[dict]) -> AsyncIterator[StreamEvent]:
        """Run an Agno Agent and yield StreamEvents."""
        instruction, user_text = self._extract_prompt(messages)
        async for event in self._run_agent(instruction, user_text):
            yield event

    async def _run_agent(self, instruction: str, user_text: str) -> AsyncIterator[StreamEvent]:
        """Create and run an Agno Agent, yielding StreamEvents."""
        agent = Agent(
            model=self._model,
            instructions=instruction,
            tools=self._tools,
            markdown=True,
        )

        step = 0
        self._stop_requested = False

        async for event in agent.arun(user_text, stream=True, stream_events=True):
            if self._stop_requested:
                break

            # --- Content (streaming deltas) ---
            if event.event == RunEvent.run_content:
                if event.content:
                    yield StreamEvent("content", text=str(event.content))

            # --- Reasoning ---
            elif event.event == RunEvent.reasoning_step:
                if event.content:
                    yield StreamEvent("think", text=str(event.content), call_id=f"Think {step}")
                    step += 1

            # --- Tool calls ---
            elif event.event == RunEvent.tool_call_started:
                tool_name = event.tool.tool_name if event.tool else "tool"
                args_str = ""
                if event.tool and event.tool.tool_args:
                    args_str = ", ".join(
                        f"{k}={v}" for k, v in event.tool.tool_args.items()
                    )
                yield StreamEvent(
                    "tool_call",
                    text=f"{tool_name}({args_str})",
                    call_id=f"Tool: {tool_name}",
                )

            elif event.event == RunEvent.tool_call_completed:
                tool_name = event.tool.tool_name if event.tool else "tool"
                result_text = str(event.content) if event.content else "(empty)"
                yield StreamEvent(
                    "tool_result",
                    text=result_text[:500],
                    call_id=f"Tool: {tool_name}",
                )

            # --- Error ---
            elif event.event == RunEvent.run_error:
                error_msg = str(event.content) if event.content else "Unknown agent error"
                raise RuntimeError(f"Agno agent error: {error_msg}")

            # --- Token usage (on completion) ---
            elif event.event == RunEvent.run_completed:
                if event.metrics:
                    yield StreamEvent("tokens", metadata={
                        "input": event.metrics.input_tokens or 0,
                        "output": event.metrics.output_tokens or 0,
                        "total": event.metrics.total_tokens or 0,
                    })

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_prompt(messages: list[dict]) -> tuple[str, str]:
        """Extract instruction (from system messages) and user text."""
        system_parts = []
        user_parts = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "system":
                system_parts.append(content)
            elif role == "assistant":
                user_parts.append(f"[Previous Output]\n{content}")
            elif role == "user":
                user_parts.append(content)

        instruction = "\n\n".join(system_parts)
        user_prompt = "\n\n---\n\n".join(user_parts)
        return instruction, user_prompt
