"""ADK Agent → LLMClient adapter.

Wraps Google ADK Agent's ReAct loop into the LLMClient.stream() interface.
- stream() yields StreamEvents for Think/Tool/Result/Content/Tokens
- Pipeline handles all broadcasting — client never touches SSE
- tools=[] degrades to a simple LLM call (used for Plan, Verify)
- If MCP tools cause a runtime failure, retries once without MCP tools.
"""

import logging
from typing import AsyncIterator

from google.adk import Runner
from google.adk.runners import RunConfig
from google.adk.agents.run_config import StreamingMode
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.genai import types

from backend.agent.factory import create_agent
from backend.llm.client import LLMClient, StreamEvent

log = logging.getLogger(__name__)


class AgentClient(LLMClient):

    has_tools = True  # Agent reads dependencies via tools

    def __init__(
        self,
        instruction: str,
        model: str = "gemini-2.0-flash",
        tools: list | None = None,
    ):
        self._instruction = instruction
        self._model = model
        self._tools = tools or []
        self._stop_requested = False

    def request_stop(self):
        """Signal the Agent to stop after the current event."""
        self._stop_requested = True

    def reset(self):
        """Clear stop flag on pipeline restart."""
        self._stop_requested = False

    async def stream(self, messages: list[dict]) -> AsyncIterator[StreamEvent]:
        """Run an ADK Agent and yield StreamEvents.

        If MCP tools cause a runtime error (e.g. timeout), retries once
        with MCP tools removed so the Agent can still complete using
        remaining tools (google_search, code_execute, etc.).
        """
        merged_instruction, user_text = self._build_agent_prompt(messages)

        try:
            async for event in self._run_agent(merged_instruction, user_text, self._tools):
                yield event
        except Exception as e:
            # Filter out MCP tools and retry once
            non_mcp_tools = [t for t in self._tools if not isinstance(t, McpToolset)]
            if len(non_mcp_tools) < len(self._tools):
                log.warning("Agent failed with MCP tools (%s), retrying without MCP", e)
                yield StreamEvent("think", text="Retrying without MCP tools", call_id="Retry")
                async for event in self._run_agent(merged_instruction, user_text, non_mcp_tools):
                    yield event
            else:
                raise

    async def _run_agent(self, instruction: str, user_text: str, tools: list) -> AsyncIterator[StreamEvent]:
        """Create and run an ADK Agent, yielding StreamEvents."""
        agent = create_agent(
            name="maars_agent",
            instruction=instruction,
            tools=tools,
            model=self._model,
        )

        runner = Runner(
            app_name="maars",
            agent=agent,
            session_service=InMemorySessionService(),
        )
        session = await runner.session_service.create_session(
            app_name="maars",
            user_id="maars_user",
        )
        message = types.Content(
            role="user",
            parts=[types.Part(text=user_text)],
        )

        final_text = ""
        step = 0
        streaming = False
        self._stop_requested = False

        async for event in runner.run_async(
            user_id="maars_user",
            session_id=session.id,
            new_message=message,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        ):
            # Check stop flag — finish current event, then break
            if self._stop_requested:
                break

            # Token usage
            if event.usage_metadata:
                yield StreamEvent("tokens", metadata={
                    "input": event.usage_metadata.prompt_token_count or 0,
                    "output": event.usage_metadata.candidates_token_count or 0,
                    "total": event.usage_metadata.total_token_count or 0,
                })

            # --- Think ---
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        if event.partial:
                            if not streaming:
                                streaming = True
                            yield StreamEvent("think", text=part.text, call_id=f"Think {step}")
                        else:
                            if not streaming:
                                yield StreamEvent("think", text=part.text, call_id=f"Think {step}")
                            final_text = part.text
                            step += 1
                            streaming = False

            # --- Tool calls ---
            function_calls = event.get_function_calls()
            if function_calls:
                for fc in function_calls:
                    args_str = ", ".join(
                        f"{k}={v}" for k, v in (fc.args or {}).items()
                    )
                    yield StreamEvent(
                        "tool_call",
                        text=f"{fc.name}({args_str})",
                        call_id=f"Tool: {fc.name}",
                    )

            # --- Tool results ---
            function_responses = event.get_function_responses()
            if function_responses:
                for fr in function_responses:
                    result_text = str(fr.response) if fr.response else "(empty)"
                    yield StreamEvent(
                        "tool_result",
                        text=result_text[:500],
                        call_id=f"Result: {fr.name}",
                    )

        if final_text:
            yield StreamEvent("content", text=final_text)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_agent_prompt(self, messages: list[dict]) -> tuple[str, str]:
        """Build agent instruction and user prompt from message history."""
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

        merged_instruction = self._instruction
        if system_parts:
            pipeline_prompt = "\n\n".join(system_parts)
            merged_instruction = f"{self._instruction}\n\n{pipeline_prompt}" if self._instruction else pipeline_prompt

        user_prompt = "\n\n---\n\n".join(user_parts)
        return merged_instruction, user_prompt
