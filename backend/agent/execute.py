"""Execute stage using ADK Agent — runs each task with an independent agent.

Each task gets: execute → verify → optional retry (once).
"""

import asyncio
import json
import re

from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from backend.db import ResearchDB
from backend.pipeline.stage import BaseStage, StageState
from backend.pipeline.execute import topological_batches

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_EXECUTE_INSTRUCTION = """\
You are a research assistant executing a specific task in a fully automated LLM pipeline (MAARS).
No human is in the loop. Make all decisions autonomously.

Available tools:
- Google Search + arXiv search: Find real papers, data, and evidence
- fetch: Retrieve content from any URL
- code_execute: Run Python in Docker for formal experiments (outputs persist as artifacts)
- list_artifacts: See experiment outputs produced so far
- Built-in code execution: Quick calculations without Docker

When a task requires data analysis, experiments, or visualization:
- Use code_execute — scripts and outputs are preserved for reproducibility
- Write results to files (CSV, PNG, etc.) in /workspace/output/

Be substantive — aim for depth and insight, not generic summaries.
Use concrete examples, evidence, and analytical frameworks.
Cite real sources where possible.
Output in markdown."""

_VERIFY_INSTRUCTION = """\
You are a research quality reviewer. Evaluate whether a task result:
1. Directly addresses the task requirements
2. Provides sufficient depth and specificity (not just generic statements)
3. Is well-structured and clearly written
4. Contains concrete evidence, examples, or reasoning (not just assertions)

Respond with ONLY a JSON object (no markdown fencing, no extra text):
If acceptable: {"pass": true}
If needs improvement: {"pass": false, "review": "Specific feedback on what to fix."}"""


# ---------------------------------------------------------------------------
# ExecuteAgentStage
# ---------------------------------------------------------------------------

class ExecuteAgentStage(BaseStage):
    """Agent-based task execution with parallel batches and verification."""

    def __init__(self, name: str = "execute", db: ResearchDB | None = None,
                 tools: list = None, model: str = "gemini-2.0-flash",
                 code_executor=None, **kwargs):
        super().__init__(name=name, **kwargs)
        self.db = db
        self._tools = tools or []
        self._model = model
        self._code_executor = code_executor
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

    # ------------------------------------------------------------------
    # Single task lifecycle: execute → verify → retry
    # ------------------------------------------------------------------

    async def _execute_task(self, task: dict, my_run_id: int) -> str:
        """Execute → verify → optionally retry once."""
        task_id = task["id"]
        dep_context = self._build_dep_context(task)
        prompt = self._build_task_prompt(task, dep_context)

        # --- Execute ---
        self._emit("task_state", {"task_id": task_id, "status": "running"})
        call_id = f"Exec {task_id}"
        self._emit("chunk", {"text": call_id, "call_id": call_id, "label": True})

        agent = Agent(
            name=f"exec_{task_id}",
            model=self._model,
            instruction=_EXECUTE_INSTRUCTION,
            tools=self._tools,
            code_executor=self._code_executor,
        )
        result = await self._run_agent(agent, prompt, call_id, my_run_id)
        if self._is_stale(my_run_id):
            return result

        # --- Verify ---
        self._emit("task_state", {"task_id": task_id, "status": "verifying"})
        passed, review = await self._verify_task(task, result, my_run_id)
        if self._is_stale(my_run_id):
            return result

        if not passed:
            # --- Retry once with feedback ---
            self._emit("task_state", {"task_id": task_id, "status": "running"})
            retry_prompt = (
                f"{prompt}\n\n"
                f"Your previous output was reviewed and needs improvement:\n\n"
                f"{review}\n\nPlease redo the task addressing the above feedback."
            )
            agent = Agent(
                name=f"retry_{task_id}",
                model=self._model,
                instruction=_EXECUTE_INSTRUCTION,
                tools=self._tools,
                code_executor=self._code_executor,
            )
            result = await self._run_agent(agent, retry_prompt, call_id, my_run_id)

        self._emit("task_state", {"task_id": task_id, "status": "completed"})

        if self.db:
            self.db.save_task_output(task_id, result)
        self._task_results[task_id] = result
        return result

    async def _verify_task(self, task: dict, result: str, my_run_id: int) -> tuple[bool, str]:
        """Run a reviewer agent to verify task output quality."""
        reviewer = Agent(
            name=f"verify_{task['id']}",
            model=self._model,
            instruction=_VERIFY_INSTRUCTION,
        )
        prompt = (
            f"Task [{task['id']}]: {task['description']}\n\n"
            f"--- Execution result ---\n{result}"
        )
        call_id = f"Verify {task['id']}"
        self._emit("chunk", {"text": call_id, "call_id": call_id, "label": True})

        response = await self._run_agent(reviewer, prompt, call_id, my_run_id)
        return _parse_verification(response)

    # ------------------------------------------------------------------
    # ADK agent runner (shared helper)
    # ------------------------------------------------------------------

    async def _run_agent(self, agent: Agent, prompt: str, call_id: str, my_run_id: int) -> str:
        """Run an ADK agent, streaming events with given call_id.

        Returns the agent's final text output.
        """
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

        final_text = ""
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

        return final_text

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_dep_context(self, task: dict) -> str:
        """Gather dependency outputs as context string."""
        parts = []
        for dep_id in task.get("dependencies", []):
            output = self._task_results.get(dep_id, "")
            if not output and self.db:
                output = self.db.get_task_output(dep_id)
            if output:
                parts.append(f"### Task [{dep_id}] output:\n{output}")
        return "\n\n".join(parts)

    def _build_task_prompt(self, task: dict, dep_context: str) -> str:
        """Build the execution prompt for a task."""
        prompt = f"## Your task [{task['id']}]:\n{task['description']}"
        if dep_context:
            prompt = f"## Context from prerequisite tasks:\n{dep_context}\n---\n{prompt}"
        return prompt

    def _build_final_output(self) -> str:
        parts = []
        for task_id in sorted(self._task_results.keys()):
            parts.append(f"## Task [{task_id}]\n\n{self._task_results[task_id]}")
        return "\n\n---\n\n".join(parts)

    def retry(self):
        super().retry()
        self._task_results.clear()


# ---------------------------------------------------------------------------
# Verification JSON parser
# ---------------------------------------------------------------------------

def _parse_verification(response: str) -> tuple[bool, str]:
    """Parse verification JSON response. Falls back to pass on parse failure."""
    text = response.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                return True, ""
        else:
            return True, ""
    return data.get("pass", True), data.get("review", "")
