"""Research stage: decompose → execute → evaluate → loop.

Combines task decomposition, parallel execution with verification,
and result evaluation into a single iterative stage.
"""

from __future__ import annotations

import asyncio
import contextvars
import json

from backend.db import ResearchDB
from backend.pipeline.stage import BaseStage, StageState
from backend.pipeline.decompose import decompose
from backend.pipeline.prompts import (
    CALIBRATE_SYSTEM, EVALUATE_SYSTEM, REPLAN_SYSTEM, STRATEGY_SYSTEM,
    build_execute_prompt, build_verify_prompt, build_retry_prompt,
)
from backend.utils import parse_json_fenced

# Per-coroutine task ID tracking for parallel execution.
# When set, ResearchStage._emit() injects task_id into all SSE events
# so the frontend can group chunks by task.
_current_task_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_current_task_id", default=None,
)


class _RedecomposeNeeded(Exception):
    """Signal that a task needs to be broken into subtasks."""
    def __init__(self, task: dict, result: str, review: str):
        self.task = task
        self.result = result
        self.review = review

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------



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
# Pre-flight checks
# ---------------------------------------------------------------------------

def _preflight_docker():
    """Check Docker availability before entering the agent execution loop.
    Raises RuntimeError immediately instead of letting agents retry in circles.
    """
    try:
        import docker
    except ImportError:
        raise RuntimeError("Docker SDK not installed. Run: pip install docker")
    try:
        client = docker.from_env()
        client.ping()
    except Exception as e:
        raise RuntimeError(f"Docker is not running: {e}")


# ---------------------------------------------------------------------------
# Tree helpers (for plan_tree.json sync)
# ---------------------------------------------------------------------------

def _find_node(tree: dict, node_id: str) -> dict | None:
    """DFS search for a node by ID in the plan tree."""
    if tree.get("id") == node_id:
        return tree
    for child in tree.get("children", []):
        found = _find_node(child, node_id)
        if found:
            return found
    return None


def _renumber_subtree(children: list[dict], parent_id: str) -> list[dict]:
    """Rename subtree node IDs: "1" → "{parent_id}_d1", recursively."""
    # Collect all IDs for mapping
    id_map: dict[str, str] = {}

    def collect(nodes: list[dict]):
        for n in nodes:
            id_map[n["id"]] = f"{parent_id}_d{n['id']}"
            collect(n.get("children", []))

    collect(children)

    def rename(node: dict) -> dict:
        return {
            "id": id_map.get(node["id"], node["id"]),
            "description": node["description"],
            "is_atomic": node.get("is_atomic"),
            "dependencies": [id_map.get(d, d) for d in node.get("dependencies", [])],
            "children": [rename(c) for c in node.get("children", [])],
        }

    return [rename(c) for c in children]


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
        self._tree: dict | None = None  # Decomposition tree (source of truth for plan_tree.json)
        self._strategy: str = ""  # Strategy from pre-decompose research
        self._prev_score: float | None = None  # Track score across iterations
        # Redecompose state: partial outputs and parent tracking
        self._partial_outputs: dict[str, str] = {}      # parent_id -> partial output
        self._redecompose_parent: dict[str, str] = {}    # subtask_id -> parent_id

    def _emit(self, event_type: str, data):
        """Override to inject task_id into events during task execution."""
        tid = _current_task_id.get()
        if tid and isinstance(data, dict) and "task_id" not in data:
            data = {**data, "task_id": tid}
        super()._emit(event_type, data)

    def load_input(self) -> str:
        return self.db.get_plan_list()

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
        self._prev_score = self._load_prev_score()
        self._load_checkpoint()

        try:
            idea = self.db.get_refined_idea()

            # ── Phase 0: CALIBRATE atomic definition ──
            self._emit("phase", "calibrate")
            self._atomic_definition = self.db.get_calibration()
            if not self._atomic_definition:
                calibrated = await self._calibrate_atomic_definition(idea, my_run_id)
                if self._is_stale(my_run_id):
                    return self.output
                if calibrated:
                    self._atomic_definition = calibrated
                    self.db.save_calibration(calibrated)
                    self._emit("document", {"name": "calibration", "label": "Calibration", "content": calibrated})

            # ── Phase 1a: STRATEGY — research best approaches ──
            self._emit("phase", "strategy")
            self._strategy = self.db.get_strategy()
            if not self._strategy:
                strategy = await self._research_strategy(idea, my_run_id)
                if self._is_stale(my_run_id):
                    return self.output
                if strategy:
                    self._strategy = strategy
                    self.db.save_strategy(strategy)
                    self._emit("document", {"name": "strategy", "label": "Strategy", "content": strategy})

            # ── Phase 1b: DECOMPOSE (skip if plan already exists — resume case) ──
            self._emit("phase", "decompose")
            existing_plan = self.db.get_plan_list()
            if existing_plan and self._task_results:
                # Resume: plan exists and we have completed tasks — skip decompose
                self._all_tasks = json.loads(existing_plan)
                tree_str = self.db.get_plan_tree()
                if tree_str:
                    self._tree = json.loads(tree_str)
            else:
                # Fresh run or retry: decompose from scratch
                flat_tasks, tree = await decompose(
                    idea=idea,
                    stream_fn=lambda msgs, cid, cl: self._stream_llm(
                        self.llm_client, msgs, cid, my_run_id, content_level=cl,
                    ),
                    max_depth=10,
                    atomic_definition=self._atomic_definition,
                    strategy=self._strategy,
                    emit=lambda t, d: self._emit(t, d),
                    is_stale=lambda: self._is_stale(my_run_id),
                )
                if self._is_stale(my_run_id):
                    return self.output

                self._all_tasks = flat_tasks
                self._tree = tree
                self.db.save_plan(flat_tasks, tree)
                self._emit("tree", tree)

            # ── Phase 2: EXECUTE + EVALUATE loop ──
            self._emit("phase", "execute")
            self._emit("chunk", {"text": "Execute", "call_id": "Execute", "label": True, "level": 2})

            # Pre-flight: check Docker before entering agent loop
            _preflight_docker()

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

                # Evaluate results: system checks score, LLM analyzes improvements
                is_last = iteration >= self._max_iterations - 1
                if is_last:
                    break

                self._emit("phase", "evaluate")

                # Step 1: System check — did the score improve?
                minimize = self.db.get_score_minimize()
                improved, current_score = self._check_score_improved(
                    self._prev_score, minimize,
                )
                if current_score is not None:
                    self._emit("score", {
                        "current": current_score,
                        "previous": self._prev_score,
                        "improved": improved,
                    })
                    self._prev_score = current_score

                if not improved and self._prev_score is not None:
                    # Score plateaued — stop iterating
                    self.db.save_evaluation({"satisfied": True, "score": current_score}, iteration)
                    break

                # Step 2: LLM analysis — what to improve next
                summaries = [
                    {"id": tid, "summary": self._task_summaries.get(tid, "(no summary)")}
                    for tid in sorted(self._task_results.keys())
                ]
                evaluation = await self._evaluate_results(idea, summaries, my_run_id)
                if self._is_stale(my_run_id):
                    return self.output

                evaluation["score"] = current_score
                self.db.save_evaluation(evaluation, iteration)
                self._emit("document", {
                    "name": f"eval_v{iteration}",
                    "label": f"Evaluation (round {iteration})",
                    "content": evaluation.get("feedback", ""),
                    "meta": {"score": current_score, "suggestions": evaluation.get("suggestions", [])},
                })

                # Replan: one LLM call that sees all completed work + feedback
                # and decides what tasks to add. NOT a full re-decompose.
                new_tasks = await self._replan(idea, evaluation, my_run_id)
                if self._is_stale(my_run_id):
                    return self.output

                if not new_tasks:
                    break

                # Renumber new tasks to avoid ID conflicts
                round_num = iteration + 1
                new_tasks = self._renumber_tasks(new_tasks, round_num)
                self._all_tasks.extend(new_tasks)

                # Build replan subtree and sync to tree + disk
                replan_subtree = {
                    "id": f"r{round_num}",
                    "description": f"Replan round {round_num}",
                    "is_atomic": False,
                    "dependencies": [],
                    "children": [
                        {
                            "id": t["id"],
                            "description": t["description"],
                            "is_atomic": True,
                            "dependencies": t.get("dependencies", []),
                            "children": [],
                        }
                        for t in new_tasks
                    ],
                }
                if self._tree:
                    self._tree.setdefault("children", []).append(replan_subtree)
                self.db.save_plan_amendment(new_tasks, round_num, replan_subtree)
                self._emit("tree", self._tree)

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
                            parent_id = result.task["id"]
                            subtask_ids = [t["id"] for t in new_tasks]

                            # Replace parent task with subtasks
                            self._all_tasks = [
                                t for t in self._all_tasks
                                if t["id"] != parent_id
                            ]
                            self._all_tasks.extend(new_tasks)

                            # Repoint downstream dependencies: parent → last subtask(s)
                            # Tasks that depended on the parent now depend on ALL subtasks
                            for t in self._all_tasks:
                                if parent_id in t.get("dependencies", []):
                                    t["dependencies"] = [
                                        d if d != parent_id else None
                                        for d in t["dependencies"]
                                    ]
                                    t["dependencies"] = [
                                        d for d in t["dependencies"] if d is not None
                                    ] + subtask_ids

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
        token = _current_task_id.set(task_id)
        self.db.current_task_id = task_id
        try:
            return await self._execute_task_inner(task, my_run_id)
        finally:
            _current_task_id.reset(token)
            self.db.current_task_id = None

    async def _execute_task_inner(self, task: dict, my_run_id: int) -> str:
        """Inner implementation of _execute_task (with task_id context set)."""
        task_id = task["id"]
        client = self.llm_client

        # Check for parent partial output (from a previous redecompose)
        parent_id = self._redecompose_parent.get(task_id)
        prior_attempt = self._partial_outputs.get(parent_id, "") if parent_id else ""

        # --- Execute ---
        call_id = f"Exec {task_id}"
        self._emit("task_state", {"task_id": task_id, "status": "running"})
        self._emit("chunk", {"text": call_id, "call_id": call_id, "label": True, "level": 3})

        messages = build_execute_prompt(task, prior_attempt)
        result = await self._stream_llm(client, messages, call_id, my_run_id, content_level=4)
        if self._is_stale(my_run_id):
            return result

        # --- Verify ---
        self._emit("task_state", {"task_id": task_id, "status": "verifying"})

        verify_messages = build_verify_prompt(task, result)
        verify_response = await self._stream_llm(client, verify_messages, call_id, my_run_id, content_level=4)
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

        retry_messages = build_retry_prompt(task, result, review)
        result = await self._stream_llm(client, retry_messages, call_id, my_run_id, content_level=4)
        if self._is_stale(my_run_id):
            return result

        # --- Verify again ---
        self._emit("task_state", {"task_id": task_id, "status": "verifying"})
        verify_messages = build_verify_prompt(task, result)
        verify_response = await self._stream_llm(client, verify_messages, call_id, my_run_id, content_level=4)
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
        """Save completed task output and emit status with summary."""
        summary = self._task_summaries.get(task_id, "")
        self._emit("task_state", {"task_id": task_id, "status": "completed", "summary": summary})
        if self.db:
            self.db.save_task_output(task_id, result)
        self._task_results[task_id] = result


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
    # Replan (informed single LLM call, not recursive decompose)
    # ------------------------------------------------------------------

    async def _replan(self, idea: str, evaluation: dict, my_run_id: int) -> list[dict]:
        """One LLM call to decide what tasks to add based on evaluation feedback.

        Unlike decompose (recursive, context-free), replan sees the full picture
        of completed work and makes informed decisions about what's missing.
        """
        feedback = evaluation.get("feedback", "")
        suggestions = evaluation.get("suggestions", [])

        if not feedback and not suggestions:
            return []

        # Build context
        completed_ids = sorted(self._task_results.keys())
        completed_summary = "\n".join(
            f"- Task [{tid}]: {self._task_summaries.get(tid, 'completed')}"
            for tid in completed_ids
        )

        artifacts_dir = self.db.get_artifacts_dir()
        artifacts = []
        if artifacts_dir.exists():
            artifacts = [f.name for f in artifacts_dir.iterdir()
                         if f.is_file() and not f.name.startswith("run_")]

        user_parts = [f"## Research Goal\n{idea}"]
        user_parts.append(f"\n## Completed Tasks\n{completed_summary}")
        if artifacts:
            user_parts.append(f"\n## Available Artifacts\n{', '.join(artifacts)}")
        user_parts.append(f"\n## Evaluation Feedback\n{feedback}")
        if suggestions:
            user_parts.append(
                "\n## Suggestions\n" + "\n".join(f"- {s}" for s in suggestions)
            )

        messages = [
            {"role": "system", "content": REPLAN_SYSTEM},
            {"role": "user", "content": "\n".join(user_parts)},
        ]

        call_id = "Replan"
        self._emit("chunk", {"text": call_id, "call_id": call_id, "label": True, "level": 3})

        response = await self._stream_llm(
            self.llm_client, messages, call_id, my_run_id, content_level=3,
        )

        data = parse_json_fenced(response, fallback={"add": []})
        new_tasks = data.get("add", [])

        # Validate structure
        valid = []
        for t in new_tasks:
            if isinstance(t, dict) and "id" in t and "description" in t:
                valid.append({
                    "id": t["id"],
                    "description": t["description"],
                    "dependencies": t.get("dependencies", []),
                })
        return valid

    def _load_prev_score(self) -> float | None:
        """Load the best score from the latest evaluation file."""
        try:
            return self.db.get_latest_score()
        except RuntimeError:
            return None

    # ------------------------------------------------------------------
    # Strategy research
    # ------------------------------------------------------------------

    async def _research_strategy(self, idea: str, my_run_id: int) -> str:
        """Research best approaches before decomposing."""
        call_id = "Strategy"
        self._emit("chunk", {"text": call_id, "call_id": call_id, "label": True, "level": 2})

        messages = [
            {"role": "system", "content": STRATEGY_SYSTEM},
            {"role": "user", "content": f"## Research Topic\n{idea}"},
        ]

        response = await self._stream_llm(
            self.llm_client, messages, call_id, my_run_id, content_level=3,
        )

        # Extract score direction from strategy response
        direction_data = parse_json_fenced(response, fallback={})
        if "score_direction" in direction_data:
            minimize = direction_data["score_direction"] != "maximize"
            self.db.save_score_direction(minimize)

        return response.strip()

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def _check_score_improved(self, prev_score: float | None,
                              minimize: bool = True) -> tuple[bool, float | None]:
        """Check best_score.json and compare with previous iteration."""
        score_file = self.db.get_artifacts_dir() / "best_score.json"
        if not score_file.exists():
            return False, None
        try:
            data = json.loads(score_file.read_text())
            current = float(data.get("score", 0))
        except (json.JSONDecodeError, ValueError, TypeError):
            return False, None
        if prev_score is None:
            return True, current
        if minimize:
            improved = current < prev_score * 0.995
        else:
            improved = current > prev_score * 1.005
        return improved, current

    async def _evaluate_results(self, idea: str, task_summaries: list[dict],
                                my_run_id: int) -> dict:
        """Analyze completed results and suggest improvements."""
        call_id = "Evaluate"
        self._emit("chunk", {"text": call_id, "call_id": call_id, "label": True, "level": 2})

        summaries_text = "\n".join(
            f"- **Task [{s['id']}]**: {s['summary']}" for s in task_summaries
        )
        messages = [
            {"role": "system", "content": EVALUATE_SYSTEM},
            {"role": "user", "content": (
                f"## Research Goal\n{idea}\n\n"
                f"## Completed Task Summaries\n{summaries_text}\n\n"
                f"Use read_task_output and list_artifacts to investigate actual results. "
                f"Analyze what can be improved and provide specific suggestions."
            )},
        ]

        response = await self._stream_llm(
            self.llm_client, messages, call_id, my_run_id, content_level=3,
        )
        return parse_json_fenced(response, fallback={"feedback": "", "suggestions": []})

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
        self._emit("chunk", {"text": call_id, "call_id": call_id, "label": True, "level": 2})

        messages = [
            {"role": "system", "content": CALIBRATE_SYSTEM},
            {"role": "user", "content": (
                f"## Your Capabilities\n{capabilities}\n\n"
                f"## Research Topic\n{idea}"
            )},
        ]

        response = await self._stream_llm(
            self.llm_client, messages, call_id, my_run_id, content_level=3,
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

        # Suppress "tree" events from redecompose — they would overwrite the main plan tree
        def _redecomp_emit(t, d):
            if t != "tree":
                self._emit(t, d)

        flat_tasks, subtree = await decompose(
            idea=context,
            stream_fn=lambda msgs, cid, cl: self._stream_llm(
                self.llm_client, msgs, cid, my_run_id, content_level=cl,
            ),
            max_depth=3,
            atomic_definition=self._atomic_definition,
            emit=_redecomp_emit,
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

        # Persist updated plan (flat list + tree)
        if self.db:
            updated = [t for t in self._all_tasks if t["id"] != task_id] + renumbered
            # Sync tree: find parent node, mark non-atomic, graft subtask children
            if self._tree:
                parent_node = _find_node(self._tree, task_id)
                if parent_node:
                    parent_node["is_atomic"] = False
                    parent_node["children"] = _renumber_subtree(
                        subtree.get("children", []), task_id,
                    )
                self._emit("tree", self._tree)
            self.db.save_plan(updated, self._tree or {})

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
        self._tree = None
        self._strategy = ""
        self._prev_score = None
        self._partial_outputs.clear()
        self._redecompose_parent.clear()
        if self.db:
            self.db.clear_tasks()
            self.db.clear_plan()
