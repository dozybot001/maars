"""Base AgentStage: wraps a Google ADK Agent into our BaseStage interface."""

import asyncio

from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from backend.pipeline.stage import BaseStage, StageState


class AgentStage(BaseStage):
    """Runs an ADK Agent as a pipeline stage.

    Maps the Agent's ReAct event stream to our chunk/call_id mechanism:
      [Think]   → agent reasoning text
      [Tool]    → tool call name + args
      [Result]  → tool result
    """

    def __init__(self, name: str, instruction: str, tools: list = None,
                 model: str = "gemini-2.0-flash", **kwargs):
        super().__init__(name=name, **kwargs)
        self._instruction = instruction
        self._tools = tools or []
        self._model = model

    def _create_agent(self) -> Agent:
        """Create a fresh ADK Agent. Called at the start of each run."""
        return Agent(
            name=f"maars_{self.name}",
            model=self._model,
            instruction=self._instruction,
            tools=self._tools,
        )

    async def run(self, input_text: str) -> str:
        """Execute the ADK agent and stream ReAct events."""
        self._run_id += 1
        my_run_id = self._run_id

        self._pause_event.set()
        self.state = StageState.RUNNING
        self._emit("state", self.state.value)
        self.output = ""

        try:
            agent = self._create_agent()
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
                parts=[types.Part(text=input_text)],
            )

            step_counter = 0
            final_text = ""

            async for event in runner.run_async(
                user_id="maars_user",
                session_id=session.id,
                new_message=message,
            ):
                await self._pause_event.wait()
                if self._is_stale(my_run_id):
                    return self.output

                # --- Think: model text output ---
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            call_id = f"Think {step_counter}"
                            if event.partial:
                                # Streaming chunk — append to current think block
                                self._emit("chunk", {"text": part.text, "call_id": call_id})
                            else:
                                # Complete think step
                                self._emit("chunk", {"text": call_id, "call_id": call_id, "label": True})
                                self._emit("chunk", {"text": part.text, "call_id": call_id})
                                step_counter += 1
                            final_text = part.text

                # --- Tool calls ---
                function_calls = event.get_function_calls()
                if function_calls:
                    for fc in function_calls:
                        call_id = f"Tool: {fc.name}"
                        self._emit("chunk", {"text": call_id, "call_id": call_id, "label": True})
                        args_str = ", ".join(f"{k}={v}" for k, v in (fc.args or {}).items())
                        self._emit("chunk", {"text": f"{fc.name}({args_str})", "call_id": call_id})
                        step_counter += 1

                # --- Tool results ---
                function_responses = event.get_function_responses()
                if function_responses:
                    for fr in function_responses:
                        call_id = f"Result: {fr.name}"
                        self._emit("chunk", {"text": call_id, "call_id": call_id, "label": True})
                        result_text = str(fr.response) if fr.response else "(empty)"
                        self._emit("chunk", {"text": result_text[:200], "call_id": call_id})

            self.output = self.finalize_agent(final_text)
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
            raise

    def finalize_agent(self, final_text: str) -> str:
        """Process the agent's final output. Override for structured parsing."""
        return final_text

    def retry(self):
        super().retry()
