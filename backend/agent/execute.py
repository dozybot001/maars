"""Execute stage using ADK Agent — runs each task with an independent agent."""

import asyncio
import json

from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from backend.db import ResearchDB
from backend.pipeline.stage import BaseStage, StageState
from backend.pipeline.execute import topological_batches

_EXECUTE_INSTRUCTION = """\
You are a research assistant executing a specific task in a fully automated LLM pipeline (MAARS).
No human is in the loop. Make all decisions autonomously.

You have NO access to internet, databases, or code execution beyond your provided tools.
Produce a thorough, well-structured text result based on your knowledge and reasoning.

Be substantive — aim for depth and insight, not generic summaries.
Use concrete examples, evidence, and analytical frameworks.
Output in markdown."""


class ExecuteAgentStage(BaseStage):
    """Agent-based task execution with parallel batches."""

    def __init__(self, name: str = "execute", db: ResearchDB | None = None,
                 tools: list = None, model: str = "gemini-2.0-flash", **kwargs):
        super().__init__(name=name, **kwargs)
        self.db = db
        self._tools = tools or []
        self._model = model
        self._task_results: dict[str, str] = {}

    async def run(self, input_text: str) -> str:
        """Execute tasks in topological batches, each task gets its own agent."""
        self._run_id += 1
        my_run_id = self._run_id

        self._pause_event.set()
        self.state = StageState.RUNNING
        self._emit("state", self.state.value)
        self.output = ""
        self._task_results = {}

        try:
            tasks = json.loads(input_text)
            batches = topological_batches(tasks)

            self._emit("exec_tree", {
                "batches": [
                    {"batch": i + 1, "tasks": [{"id": t["id"], "description": t["description"]} for t in b]}
                    for i, b in enumerate(batches)
                ]
            })

            for batch in batches:
                await self._pause_event.wait()
                if self._is_stale(my_run_id):
                    return self.output

                coros = [self._execute_task(task, my_run_id) for task in batch]
                results = await asyncio.gather(*coros, return_exceptions=True)

                for task, result in zip(batch, results):
                    if self._is_stale(my_run_id):
                        return self.output
                    if isinstance(result, Exception):
                        self._emit("task_state", {"task_id": task["id"], "status": "failed"})

            self.output = self._build_final_output()
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

    async def _execute_task(self, task: dict, my_run_id: int) -> str:
        """Run a single task with its own agent."""
        task_id = task["id"]
        self._emit("task_state", {"task_id": task_id, "status": "running"})

        # Build context from dependencies
        dep_context = ""
        for dep_id in task.get("dependencies", []):
            output = self._task_results.get(dep_id, "")
            if not output and self.db:
                output = self.db.get_task_output(dep_id)
            if output:
                dep_context += f"\n### Task [{dep_id}] output:\n{output}\n"

        prompt = f"## Your task [{task_id}]:\n{task['description']}"
        if dep_context:
            prompt = f"## Context from prerequisite tasks:\n{dep_context}\n---\n{prompt}"

        # Create and run agent
        agent = Agent(
            name=f"exec_{task_id}",
            model=self._model,
            instruction=_EXECUTE_INSTRUCTION,
            tools=self._tools,
        )

        runner = Runner(
            app_name="maars",
            agent=agent,
            session_service=InMemorySessionService(),
        )

        session = await runner.session_service.create_session(
            app_name="maars", user_id="maars_user",
        )

        message = types.Content(
            role="user",
            parts=[types.Part(text=prompt)],
        )

        call_id = f"Exec {task_id}"
        self._emit("chunk", {"text": call_id, "call_id": call_id, "label": True})

        final_text = ""
        step = 0

        async for event in runner.run_async(
            user_id="maars_user",
            session_id=session.id,
            new_message=message,
        ):
            await self._pause_event.wait()
            if self._is_stale(my_run_id):
                return final_text

            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        self._emit("chunk", {"text": part.text, "call_id": call_id})
                        final_text = part.text

            if event.get_function_calls():
                for fc in event.get_function_calls():
                    args_str = ", ".join(f"{k}={v}" for k, v in (fc.args or {}).items())
                    self._emit("chunk", {"text": f"\n[{fc.name}({args_str})]\n", "call_id": call_id})

        self._emit("task_state", {"task_id": task_id, "status": "completed"})

        if self.db:
            self.db.save_task_output(task_id, final_text)
        self._task_results[task_id] = final_text

        return final_text

    def _build_final_output(self) -> str:
        parts = []
        for task_id in sorted(self._task_results.keys()):
            parts.append(f"## Task [{task_id}]\n\n{self._task_results[task_id]}")
        return "\n\n---\n\n".join(parts)

    def retry(self):
        super().retry()
        self._task_results.clear()
