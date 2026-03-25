"""Execute stage: runs atomic tasks with topological ordering, parallelism, and verification."""

from __future__ import annotations

import asyncio
import json

from backend.db import ResearchDB
from backend.pipeline.stage import BaseStage, StageState
from backend.utils import parse_json_fenced

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_AUTO = "This is a fully automated pipeline. No human is in the loop. Do NOT ask questions or request input. Make all decisions autonomously. 全文使用中文撰写。\n\n"

_EXECUTE_SYSTEM = _AUTO + """\
You are a research assistant executing a specific task as part of a larger research project.

Guidelines:
- Be substantive — produce concrete results, not descriptions of what you would do
- If the task is analytical: provide frameworks, specific comparisons, and cite evidence
- If the task is experimental: describe setup, parameters, results, and interpretation
- Structure output with headings and bullet points for clarity
- Reference specific data, figures, or prior work where relevant

Output in markdown."""

_VERIFY_SYSTEM = """\
You are a research quality reviewer. Evaluate whether the task result SUBSTANTIALLY meets the goal.

Criteria:
1. Does it address the core intent of the task? (not literal word-matching — reasonable engineering decisions like sampling representative points instead of exhaustive iteration are acceptable)
2. Does it provide real substance, not just descriptions or plans?
3. Is it well-structured and clearly written?

Be pragmatic, not pedantic. A result that achieves the task's purpose through a slightly different approach should PASS. Only fail results that fundamentally miss the point or fabricate data.

Respond with ONLY a JSON object:
If acceptable: {"pass": true}
If needs improvement: {"pass": false, "review": "What is fundamentally missing or wrong."}"""


def _build_execute_prompt(task: dict, dep_outputs: dict[str, str]) -> list[dict]:
    """Build prompt for task execution, including dependency outputs as context."""
    messages = [{"role": "system", "content": _EXECUTE_SYSTEM}]

    parts = []
    deps = task.get("dependencies", [])

    if dep_outputs:
        # Gemini/Mock: full dep content inline
        parts.append("## Context from completed prerequisite tasks:\n")
        for dep_id, output in dep_outputs.items():
            parts.append(f"### Task [{dep_id}] output:\n{output}\n")
        parts.append("---\n")
    elif deps:
        # Agent mode: dep_outputs empty, list IDs for tool reading
        parts.append(f"## Prerequisite tasks (use read_task_output to read): {', '.join(deps)}\n---\n")

    parts.append(f"## Your task [{task['id']}]:\n{task['description']}")
    messages.append({"role": "user", "content": "\n".join(parts)})
    return messages


def _build_verify_prompt(task: dict, result: str) -> list[dict]:
    return [
        {"role": "system", "content": _VERIFY_SYSTEM},
        {"role": "user", "content": (
            f"Task [{task['id']}]: {task['description']}\n\n"
            f"--- Execution result ---\n{result}"
        )},
    ]


def _build_retry_prompt(task: dict, result: str, review: str, dep_outputs: dict[str, str]) -> list[dict]:
    """Build prompt for re-execution after failed verification."""
    messages = _build_execute_prompt(task, dep_outputs)
    messages.append({"role": "assistant", "content": result})
    messages.append({"role": "user", "content": (
        f"Your previous output was reviewed and needs improvement:\n\n"
        f"{review}\n\nPlease redo the task addressing the above feedback."
    )})
    return messages


# ---------------------------------------------------------------------------
# Topological sort
# ---------------------------------------------------------------------------

def topological_batches(tasks: list[dict]) -> list[list[dict]]:
    """Group tasks into batches by dependency order.
    Each batch contains tasks whose dependencies are all in prior batches.
    Tasks within a batch can run in parallel.
    """
    task_map = {t["id"]: t for t in tasks}
    remaining = set(task_map.keys())
    completed: set[str] = set()
    batches: list[list[dict]] = []

    while remaining:
        # Find tasks whose deps are all completed
        batch_ids = [
            tid for tid in remaining
            if all(d in completed for d in task_map[tid].get("dependencies", []))
        ]
        if not batch_ids:
            # Shouldn't happen in a valid DAG — break to avoid infinite loop
            batch_ids = list(remaining)

        batches.append([task_map[tid] for tid in batch_ids])
        completed.update(batch_ids)
        remaining -= set(batch_ids)

    return batches


# ---------------------------------------------------------------------------
# ExecuteStage
# ---------------------------------------------------------------------------

class ExecuteStage(BaseStage):
    """Executes atomic tasks with parallel batches and verification."""

    def __init__(self, name: str = "execute", **kwargs):
        super().__init__(name=name, **kwargs)
        self._task_results: dict[str, str] = {}

    def load_input(self) -> str:
        # Execute always reads plan.json directly — it needs structured JSON
        # for topological sorting, not a tool call
        return self.db.get_plan_json()

    async def run(self) -> str:
        """Override the base run loop — Execute has its own parallel execution model."""
        self._run_id += 1
        my_run_id = self._run_id

        self._pause_event.set()
        self.state = StageState.RUNNING
        self._emit("state", self.state.value)
        self.output = ""

        # Checkpoint: load previously completed tasks from DB
        self._task_results = {}
        self._load_checkpoint()

        try:
            tasks = json.loads(self.load_input())
            batches = topological_batches(tasks)

            # Emit execution tree for frontend
            self._emit("exec_tree", {
                "batches": [
                    {
                        "batch": i + 1,
                        "tasks": [{"id": t["id"], "description": t["description"]} for t in b],
                    }
                    for i, b in enumerate(batches)
                ]
            })

            for batch_idx, batch in enumerate(batches):
                await self._pause_event.wait()
                if self._is_stale(my_run_id):
                    return self.output

                # Checkpoint resume: skip already-completed tasks
                pending = [t for t in batch if t["id"] not in self._task_results]
                for t in batch:
                    if t["id"] in self._task_results:
                        self._emit("task_state", {"task_id": t["id"], "status": "completed"})
                if not pending:
                    continue

                coros = [self._execute_task(task, my_run_id) for task in pending]
                results = await asyncio.gather(*coros, return_exceptions=True)

                for task, result in zip(pending, results):
                    if self._is_stale(my_run_id):
                        return self.output
                    if isinstance(result, Exception):
                        self._emit("task_state", {"task_id": task["id"], "status": "failed"})
                        self.state = StageState.FAILED
                        self._emit("error", {"message": f"Task {task['id']} failed: {result}"})
                        self._emit("state", self.state.value)
                        return self.output

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
        """Execute a single task: run → verify → optionally retry.
        Each task gets its own LLM client to avoid shared state in parallel.
        """
        task_id = task["id"]
        client = self.llm_client

        # Gather dependency outputs
        # Agent mode: Agent reads deps via tools, pipeline just lists dep IDs
        # Gemini/Mock: pipeline pre-loads dep content into prompt
        dep_outputs = {}
        if not client.has_broadcast:
            for dep_id in task.get("dependencies", []):
                output = self._task_results.get(dep_id, "")
                if not output and self.db:
                    output = self.db.get_task_output(dep_id)
                if output:
                    dep_outputs[dep_id] = output

        # --- Execute ---
        call_id = f"Exec {task_id}"
        self._emit("task_state", {"task_id": task_id, "status": "running"})
        self._emit("chunk", {"text": call_id, "call_id": call_id, "label": True})

        messages = _build_execute_prompt(task, dep_outputs)
        result = await self._stream_llm(client, messages, call_id, my_run_id)
        if self._is_stale(my_run_id):
            return result

        # --- Verify ---
        self._emit("task_state", {"task_id": task_id, "status": "verifying"})

        verify_messages = _build_verify_prompt(task, result)
        verify_response = await self._stream_llm(client, verify_messages, call_id, my_run_id)
        if self._is_stale(my_run_id):
            return result

        passed, review = self._parse_verification(verify_response)

        if not passed:
            # --- Retry once with feedback ---
            self._emit("task_state", {"task_id": task_id, "status": "retrying"})

            retry_messages = _build_retry_prompt(task, result, review, dep_outputs)
            result = await self._stream_llm(client, retry_messages, call_id, my_run_id)
            if self._is_stale(my_run_id):
                return result

            # --- Verify again ---
            self._emit("task_state", {"task_id": task_id, "status": "verifying"})
            verify_messages = _build_verify_prompt(task, result)
            verify_response = await self._stream_llm(client, verify_messages, call_id, my_run_id)
            passed, review = self._parse_verification(verify_response)
            if not passed:
                self._emit("task_state", {"task_id": task_id, "status": "failed"})
                raise RuntimeError(f"Task {task_id} failed verification after retry: {review}")

        self._emit("task_state", {"task_id": task_id, "status": "completed"})

        # Save to DB
        if self.db:
            self.db.save_task_output(task_id, result)
        self._task_results[task_id] = result

        return result

    async def _stream_llm(self, client, messages: list[dict], call_id: str, my_run_id: int) -> str:
        """Stream LLM response, emitting chunks with call_id."""
        result = ""
        async for chunk in client.stream(messages):
            await self._pause_event.wait()
            if self._is_stale(my_run_id):
                break
            result += chunk
            if not client.has_broadcast:
                self._emit("chunk", {"text": chunk, "call_id": call_id})
        return result

    def _parse_verification(self, response: str) -> tuple[bool, str]:
        """Parse verification JSON response."""
        data = parse_json_fenced(response, fallback={"pass": True})
        return data.get("pass", True), data.get("review", "")

    def _build_final_output(self) -> str:
        """Combine all task results and generate Docker reproduction files."""
        # Generate Docker files if any code was executed
        if self.db:
            try:
                from backend.reproduce import generate_reproduce_files
                generate_reproduce_files(self.db)
            except Exception:
                pass  # Non-critical — don't fail the stage

        parts = []
        for task_id in sorted(self._task_results.keys()):
            parts.append(f"## Task [{task_id}]\n\n{self._task_results[task_id]}")
        return "\n\n---\n\n".join(parts)

    def _load_checkpoint(self):
        """Load completed task outputs from DB for checkpoint resume."""
        if not self.db:
            return
        for info in self.db.list_completed_tasks():
            task_id = info["id"]
            output = self.db.get_task_output(task_id)
            if output:
                self._task_results[task_id] = output

    def retry(self):
        super().retry()
        self._task_results.clear()
        # Clear DB task files for clean restart
        if self.db:
            self.db.clear_tasks()
