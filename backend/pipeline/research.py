"""Research stage: decompose → execute → evaluate → loop.

Combines task decomposition, parallel execution with verification,
and result evaluation into a single iterative stage.
"""

from __future__ import annotations

import asyncio
import json

from backend.db import ResearchDB
from backend.pipeline.stage import BaseStage, StageState
from backend.pipeline.decompose import decompose
from backend.pipeline.evaluate import evaluate_results
from backend.utils import parse_json_fenced


class _RedecomposeNeeded(Exception):
    """Signal that a task needs to be broken into subtasks."""
    def __init__(self, task: dict, result: str, review: str):
        self.task = task
        self.result = result
        self.review = review

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
If acceptable: {"pass": true, "summary": "One-sentence summary of what was accomplished and key findings"}
If minor issues (format, missing details, insufficient depth — but approach is correct):
  {"pass": false, "redecompose": false, "review": "What needs fixing.", "summary": "One-sentence summary"}
If fundamentally too complex or wrong approach:
  {"pass": false, "redecompose": true, "review": "Why this needs to be broken down.", "summary": "One-sentence summary"}

Set "redecompose" to true ONLY when:
- The task covers multiple distinct sub-goals and the result is shallow on each
- The result shows the task scope exceeds what a single execution can handle
- The methodology is fundamentally wrong, not just incomplete"""


_CALIBRATE_SYSTEM = _AUTO + """\
You are calibrating task decomposition for a research pipeline.
Assess your own capabilities and define what constitutes an "atomic task" — one you can reliably complete in a SINGLE execution session.

If you have tools available, you may briefly test them to verify they work (e.g., one quick search). But keep testing minimal — focus on defining boundaries.

Output ONLY a concise ATOMIC DEFINITION block (3-5 sentences) that will be injected verbatim into a task planner's system prompt. Include:
1. What you can accomplish in a single session given your capabilities
2. Concrete examples of atomic tasks for this research domain
3. Concrete examples of tasks that are TOO LARGE and must be decomposed
Be specific to this research topic — not generic advice."""


def _build_execute_prompt(task: dict, dep_outputs: dict[str, str],
                          prior_attempt: str = "") -> list[dict]:
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

    if prior_attempt:
        parts.append(
            "## Prior attempt on parent task (reference only — focus on YOUR specific subtask):\n"
            f"{prior_attempt}\n---\n"
        )

    parts.append(f"## Your task [{task['id']}]:\n{task['description']}")

    # Tool-use reminder at the end of user message (closest to generation,
    # most likely to be followed). Only for tool-capable clients.
    parts.append(
        "\n---\n"
        "REMINDER: If this task involves code/experiments, you MUST call "
        "code_execute to run real code. Do NOT just describe code — execute it. "
        "Use list_artifacts to verify generated files."
    )

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
# ResearchStage
# ---------------------------------------------------------------------------

class ResearchStage(BaseStage):
    """Decomposes, executes, and evaluates research tasks in an iterative loop."""

    def __init__(self, name: str = "research", max_iterations: int = 1,
                 atomic_definition: str = "", **kwargs):
        super().__init__(name=name, **kwargs)
        self._task_results: dict[str, str] = {}
        self._task_summaries: dict[str, str] = {}
        self._max_iterations = max_iterations
        self._atomic_definition = atomic_definition
        self._all_tasks: list[dict] = []
        # Redecompose state: partial outputs and parent tracking
        self._partial_outputs: dict[str, str] = {}      # parent_id -> partial output
        self._redecompose_parent: dict[str, str] = {}    # subtask_id -> parent_id

    def load_input(self) -> str:
        return self.db.get_plan_json()

    async def run(self) -> str:
        """Decompose → execute → evaluate → loop."""
        self._run_id += 1
        my_run_id = self._run_id

        self.state = StageState.RUNNING
        self._emit("state", self.state.value)
        self.output = ""

        # Checkpoint: load previously completed tasks from DB
        self._task_results = {}
        self._task_summaries = {}
        self._load_checkpoint()

        try:
            idea = self.db.get_refined_idea()

            # ── Phase 0: CALIBRATE atomic definition ──
            if not self._atomic_definition:
                calibrated = await self._calibrate_atomic_definition(idea, my_run_id)
                if self._is_stale(my_run_id):
                    return self.output
                if calibrated:
                    self._atomic_definition = calibrated

            # ── Phase 1: DECOMPOSE (skip if plan already exists — resume case) ──
            existing_plan = self.db.get_plan_json()
            if existing_plan and self._task_results:
                # Resume: plan exists and we have completed tasks — skip decompose
                self._all_tasks = json.loads(existing_plan)
            else:
                # Fresh run or retry: decompose from scratch
                flat_tasks, tree = await decompose(
                    idea=idea,
                    llm_client=self.llm_client,
                    max_depth=10,
                    atomic_definition=self._atomic_definition,
                    stream_callback=lambda t, d: self._emit(t, d),
                    is_stale=lambda: self._is_stale(my_run_id),
                )
                if self._is_stale(my_run_id):
                    return self.output

                self._all_tasks = flat_tasks
                self.db.save_plan(
                    json.dumps(flat_tasks, indent=2, ensure_ascii=False), tree
                )
                self._emit("tree", tree)

            # ── Phase 2: EXECUTE + EVALUATE loop ──
            start_iteration = self.db.get_iteration()
            for iteration in range(start_iteration, self._max_iterations):
                if self._is_stale(my_run_id):
                    return self.output

                # Execute all pending tasks
                failed = await self._execute_all_tasks(my_run_id)
                if self._is_stale(my_run_id):
                    return self.output
                if failed:
                    break

                # Last iteration: skip evaluation
                if iteration >= self._max_iterations - 1:
                    break

                # Evaluate results
                summaries = [
                    {"id": tid, "summary": self._task_summaries.get(tid, "(no summary)")}
                    for tid in sorted(self._task_results.keys())
                ]
                evaluation = await evaluate_results(
                    idea=idea,
                    task_summaries=summaries,
                    llm_client=self.llm_client,
                    stream_callback=lambda t, d: self._emit(t, d),
                    is_stale=lambda: self._is_stale(my_run_id),
                )
                if self._is_stale(my_run_id):
                    return self.output

                self.db.save_evaluation(evaluation, iteration)

                if evaluation.get("satisfied", True):
                    break

                # Decompose again with feedback
                feedback_text = evaluation.get("feedback", "")
                suggestions = evaluation.get("suggestions", [])
                if suggestions:
                    feedback_text += "\n\nSpecific suggestions:\n" + "\n".join(
                        f"- {s}" for s in suggestions
                    )

                new_tasks, _ = await decompose(
                    idea=feedback_text,
                    llm_client=self.llm_client,
                    atomic_definition=self._atomic_definition,
                    stream_callback=lambda t, d: self._emit(t, d),
                    is_stale=lambda: self._is_stale(my_run_id),
                )
                if self._is_stale(my_run_id):
                    return self.output

                if not new_tasks:
                    break

                # Renumber new tasks to avoid ID conflicts
                new_tasks = self._renumber_tasks(new_tasks, iteration + 1)
                self._all_tasks.extend(new_tasks)
                self.db.save_plan_amendment(new_tasks, iteration + 1)

            # ── Phase 3: FINALIZE ──
            if self.state == StageState.FAILED:
                # A task hard-failed during execution — don't mark as completed
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
                self._emit("state", self.state.value)
            raise

    # ------------------------------------------------------------------
    # Task execution
    # ------------------------------------------------------------------

    async def _execute_all_tasks(self, my_run_id: int) -> bool:
        """Execute all pending tasks in topological batches.
        Returns True if any task had a hard failure.

        When a task triggers redecompose, it is replaced by subtasks
        and the batch loop restarts with an updated task list.
        """
        while True:
            batches = topological_batches(self._all_tasks)

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

            had_redecompose = False

            for batch in batches:
                if self._is_stale(my_run_id):
                    return False

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
                        return False
                    if isinstance(result, _RedecomposeNeeded):
                        new_tasks = await self._redecompose_task(result, my_run_id)
                        if self._is_stale(my_run_id):
                            return False
                        if new_tasks:
                            # Replace original task with subtasks
                            self._all_tasks = [
                                t for t in self._all_tasks
                                if t["id"] != result.task["id"]
                            ]
                            self._all_tasks.extend(new_tasks)
                            had_redecompose = True
                        else:
                            self._emit("task_state", {"task_id": task["id"], "status": "failed"})
                            self.state = StageState.FAILED
                            self._emit("error", {"message": f"Task {task['id']}: redecompose produced no subtasks"})
                            self._emit("state", self.state.value)
                            return True
                    elif isinstance(result, Exception):
                        self._emit("task_state", {"task_id": task["id"], "status": "failed"})
                        self.state = StageState.FAILED
                        self._emit("error", {"message": f"Task {task['id']} failed: {result}"})
                        self._emit("state", self.state.value)
                        return True

                if had_redecompose:
                    break  # Re-batch with updated task list

            if not had_redecompose:
                break  # All tasks completed

        return False

    async def _execute_task(self, task: dict, my_run_id: int) -> str:
        """Execute a single task: run → verify → retry or redecompose."""
        task_id = task["id"]
        client = self.llm_client

        # Gather dependency outputs
        dep_outputs = {}
        if not client.has_tools:
            for dep_id in task.get("dependencies", []):
                output = self._task_results.get(dep_id, "")
                if not output and self.db:
                    output = self.db.get_task_output(dep_id)
                if output:
                    dep_outputs[dep_id] = output

        # Check for parent partial output (from a previous redecompose)
        parent_id = self._redecompose_parent.get(task_id)
        prior_attempt = self._partial_outputs.get(parent_id, "") if parent_id else ""

        # --- Execute ---
        call_id = f"Exec {task_id}"
        self._emit("task_state", {"task_id": task_id, "status": "running"})
        self._emit("chunk", {"text": call_id, "call_id": call_id, "label": True})

        messages = _build_execute_prompt(task, dep_outputs, prior_attempt)
        result = await self._stream_llm(client, messages, call_id, my_run_id)
        if self._is_stale(my_run_id):
            return result

        # --- Verify ---
        self._emit("task_state", {"task_id": task_id, "status": "verifying"})

        verify_messages = _build_verify_prompt(task, result)
        verify_response = await self._stream_llm(client, verify_messages, call_id, my_run_id)
        if self._is_stale(my_run_id):
            return result

        passed, review, summary, redecompose = self._parse_verification(verify_response)
        self._task_summaries[task_id] = summary

        if passed:
            self._save_task(task_id, result)
            return result

        # Fundamental problem → redecompose immediately (skip retry)
        if redecompose:
            raise _RedecomposeNeeded(task, result, review)

        # Minor issue → retry once with feedback
        self._emit("task_state", {"task_id": task_id, "status": "retrying"})

        retry_messages = _build_retry_prompt(task, result, review, dep_outputs)
        result = await self._stream_llm(client, retry_messages, call_id, my_run_id)
        if self._is_stale(my_run_id):
            return result

        # --- Verify again ---
        self._emit("task_state", {"task_id": task_id, "status": "verifying"})
        verify_messages = _build_verify_prompt(task, result)
        verify_response = await self._stream_llm(client, verify_messages, call_id, my_run_id)
        passed, review, summary, redecompose = self._parse_verification(verify_response)
        self._task_summaries[task_id] = summary

        if passed:
            self._save_task(task_id, result)
            return result

        # Retry failed — redecompose if indicated, otherwise hard fail
        if redecompose:
            raise _RedecomposeNeeded(task, result, review)

        self._emit("task_state", {"task_id": task_id, "status": "failed"})
        raise RuntimeError(f"Task {task_id} failed verification after retry: {review}")

    def _save_task(self, task_id: str, result: str):
        """Save completed task output and emit status."""
        self._emit("task_state", {"task_id": task_id, "status": "completed"})
        if self.db:
            self.db.save_task_output(task_id, result)
        self._task_results[task_id] = result

    async def _stream_llm(self, client, messages: list[dict], call_id: str, my_run_id: int) -> str:
        """Stream LLM response, dispatching all events uniformly."""
        result = ""
        async for event in client.stream(messages):
            if self._is_stale(my_run_id):
                break
            result += self._dispatch_stream(event, call_id)
        return result

    def _parse_verification(self, response: str) -> tuple[bool, str, str, bool]:
        """Parse verification JSON response. Returns (passed, review, summary, redecompose)."""
        data = parse_json_fenced(response, fallback={"pass": True})
        return (
            data.get("pass", True),
            data.get("review", ""),
            data.get("summary", ""),
            data.get("redecompose", False),
        )

    # ------------------------------------------------------------------
    # Calibration
    # ------------------------------------------------------------------

    async def _calibrate_atomic_definition(self, idea: str, my_run_id: int) -> str:
        """Run one LLM/agent call to self-assess capability boundaries.

        In agent mode this is a full agent session (with tools) — the agent
        can test its tools to gauge what it can handle as a single task.
        In text-only mode this is a simple LLM call.
        """
        capabilities = self.llm_client.describe_capabilities()

        call_id = "Calibrate"
        self._emit("chunk", {"text": call_id, "call_id": call_id, "label": True})

        messages = [
            {"role": "system", "content": _CALIBRATE_SYSTEM},
            {"role": "user", "content": (
                f"## Your Capabilities\n{capabilities}\n\n"
                f"## Research Topic\n{idea}"
            )},
        ]

        response = await self._stream_llm(
            self.llm_client, messages, call_id, my_run_id,
        )
        return response.strip()

    # ------------------------------------------------------------------
    # Redecompose
    # ------------------------------------------------------------------

    async def _redecompose_task(self, err: _RedecomposeNeeded, my_run_id: int) -> list[dict]:
        """Break a failed task into subtasks, passing partial output as context.

        Returns renumbered subtasks ready to insert into _all_tasks,
        or empty list if decompose produced nothing.
        """
        task = err.task
        task_id = task["id"]

        self._emit("task_state", {"task_id": task_id, "status": "decomposing"})

        # Save partial output so subtasks can reference it
        self._partial_outputs[task_id] = err.result

        # Build rich context for decomposition
        context = (
            f"## 原始任务 [{task_id}]\n{task['description']}\n\n"
            f"## 已有执行结果（不充分，需要拆分）\n{err.result}\n\n"
            f"## 审查反馈\n{err.review}\n\n"
            f"请将此任务拆分为可独立执行的子任务。"
            f"已有结果中质量合格的部分不需要重做，聚焦于缺失或需要不同方法的部分。"
        )

        flat_tasks, _ = await decompose(
            idea=context,
            llm_client=self.llm_client,
            max_depth=3,
            atomic_definition=self._atomic_definition,
            stream_callback=lambda t, d: self._emit(t, d),
            is_stale=lambda: self._is_stale(my_run_id),
        )

        if self._is_stale(my_run_id) or not flat_tasks:
            return []

        # Renumber subtasks under parent: "2_1" → "2_1_d1", "2_1_d2"
        parent_deps = task.get("dependencies", [])
        id_map = {t["id"]: f"{task_id}_d{t['id']}" for t in flat_tasks}

        renumbered = []
        for t in flat_tasks:
            new_id = id_map[t["id"]]
            # Map internal deps; root subtasks (no internal deps) inherit parent deps
            internal_deps = [id_map.get(d, d) for d in t.get("dependencies", [])]
            new_deps = internal_deps if internal_deps else list(parent_deps)

            renumbered.append({
                "id": new_id,
                "description": t["description"],
                "dependencies": new_deps,
            })
            # Track parent so subtasks can access partial output
            self._redecompose_parent[new_id] = task_id

        # Persist updated plan
        if self.db:
            updated = [t for t in self._all_tasks if t["id"] != task_id] + renumbered
            self.db.save_plan(
                json.dumps(updated, indent=2, ensure_ascii=False), None
            )

        return renumbered

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _renumber_tasks(self, tasks: list[dict], round_num: int) -> list[dict]:
        """Prefix task IDs with r{round}_ to avoid conflicts with original plan."""
        prefix = f"r{round_num}_"
        id_map = {}
        renumbered = []

        for task in tasks:
            old_id = task["id"]
            new_id = f"{prefix}{old_id}"
            id_map[old_id] = new_id

        for task in tasks:
            new_deps = []
            for dep in task.get("dependencies", []):
                # Map to new ID if it's a sibling; keep original if it's a pre-existing task
                new_deps.append(id_map.get(dep, dep))
            renumbered.append({
                "id": id_map[task["id"]],
                "description": task["description"],
                "dependencies": new_deps,
            })

        return renumbered

    def _build_final_output(self) -> str:
        """Combine all task results and generate Docker reproduction files."""
        if self.db:
            try:
                from backend.reproduce import generate_reproduce_files
                generate_reproduce_files(self.db)
            except Exception:
                pass  # Non-critical

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
        self._task_summaries.clear()
        self._all_tasks.clear()
        self._partial_outputs.clear()
        self._redecompose_parent.clear()
        if self.db:
            self.db.clear_tasks()
            self.db.clear_plan()
