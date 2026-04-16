"""Research stage: decompose → execute → evaluate → loop."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from pathlib import Path

from backend.config import settings
from backend.sandbox.gpu_probe import gpu_disclosure_markdown

log = logging.getLogger(__name__)
from backend.pipeline.stage import Stage, StageState
from backend.pipeline.decompose import decompose
from backend.pipeline.prompts import (
    CALIBRATE_SYSTEM, EVALUATE_SYSTEM,
    STRATEGY_SYSTEM, build_execute_prompt, build_verify_prompt, build_retry_prompt,
    build_evaluate_user, build_strategy_update_user,
)
from backend.utils import parse_json_fenced


def topological_batches(tasks: list[dict], precompleted: set[str] | None = None) -> list[list[dict]]:
    task_map = {t["id"]: t for t in tasks}
    remaining = set(task_map.keys())
    completed: set[str] = set(precompleted or set())
    batches: list[list[dict]] = []
    while remaining:
        batch_ids = [
            tid for tid in remaining
            if all(d in completed for d in task_map[tid].get("dependencies", []))
        ]
        if not batch_ids:
            log.warning("Dependency cycle detected among tasks %s — forcing execution", remaining)
            batch_ids = list(remaining)
        batches.append([task_map[tid] for tid in batch_ids])
        completed.update(batch_ids)
        remaining -= set(batch_ids)
    return batches


def _preflight_docker():
    try:
        import docker
    except ImportError:
        raise RuntimeError("Research requires Docker: install the SDK with `pip install docker`")
    try:
        client = docker.from_env()
        client.ping()
    except Exception as e:
        raise RuntimeError(
            f"Research requires Docker daemon to be running and reachable: {e}"
        )


def _find_node(tree: dict, node_id: str) -> dict | None:
    if tree.get("id") == node_id:
        return tree
    for child in tree.get("children", []):
        found = _find_node(child, node_id)
        if found:
            return found
    return None


# Pre-installed packages in Docker sandbox — keep in sync with Dockerfile.sandbox
SANDBOX_PREINSTALLED = (
    "numpy, pandas, matplotlib, scipy, scikit-learn, "
    "torch, torchvision, xgboost, lightgbm, catboost, "
    "statsmodels, seaborn, networkx, sympy"
)


class ResearchStage(Stage):

    def __init__(self, name: str = "research", model=None, tools=None,
                 max_iterations: int = 1, db=None):
        super().__init__(name=name, db=db)
        self._model = model
        self._tools = tools or []
        self._task_results: dict[str, str] = {}
        self._task_summaries: dict[str, str] = {}
        self._max_iterations = max_iterations
        self._all_tasks: list[dict] = []
        self._tree: dict | None = None
        self._strategy: str = ""
        self._atomic_definition: str = ""
        self._prev_score: float | None = None
        self._partial_outputs: dict[str, str] = {}
        self._current_task_id: str | None = None

    def _llm(self, instruction, user_text, call_id, content_level=2, timeout=None, **kwargs):
        if timeout is None:
            timeout = settings.agent_session_timeout_seconds()
        task_id = kwargs.pop("task_id", None) or self._current_task_id or ""
        skip_sem = kwargs.pop("_skip_semaphore", False)
        tools = kwargs.pop("tools", self._tools)
        return self._stream_llm(
            self._model, tools, instruction, user_text, call_id,
            content_level=content_level, timeout=timeout, task_id=task_id,
            _skip_semaphore=skip_sem, **kwargs,
        )

    def _build_capability_profile(self) -> str:
        """Deterministic capability profile built from config + tools."""
        _code_exec_desc = (
            "Execute Python in Docker sandbox. Returns stdout, stderr, exit_code, generated file list. "
            "stdout truncated to 5000 chars."
        )
        if settings.docker_sandbox_gpu:
            _code_exec_desc += (
                " NVIDIA GPU is passed into the sandbox; capability profile lists probed "
                "device name, VRAM, compute capability, and driver when available."
            )
        _TOOL_DESCS = {
            'code_execute': _code_exec_desc,
            'list_artifacts': 'List files in current task artifacts directory.',
            'read_task_output': 'Read markdown output of a completed sibling task.',
            'list_tasks': 'List all completed tasks with IDs and sizes.',
            'read_refined_idea': 'Read the refined research idea.',
            'read_plan_tree': 'Read the full decomposition tree.',
            'read_results_summary': 'Read the canonical deterministic summary of completed results.',
            'ArxivTools': 'Search academic papers on arXiv.',
            'WikipediaTools': 'Search Wikipedia articles.',
        }
        lines = [
            "## Execution Environment",
            "",
            "### Docker Sandbox",
            f"- Timeout per code_execute: {settings.docker_sandbox_timeout}s",
            f"- Timeout per agent turn (LLM + all tool calls): "
            f"{settings.agent_session_timeout_seconds()}s",
            f"- Memory: {settings.docker_sandbox_memory}",
            f"- CPU: {settings.docker_sandbox_cpu} cores",
            *gpu_disclosure_markdown().split("\n"),
            f"- Network: {'enabled' if settings.docker_sandbox_network else 'disabled'}",
            f"- Pre-installed packages: {SANDBOX_PREINSTALLED}",
            "",
            "### Execution Model",
            "- Each task = ONE independent agent session (single system prompt + user message)",
            "- Agent can make MULTIPLE tool calls within one session",
            "- All code_execute calls share one persistent container — installed packages persist across calls and tasks",
            "- /workspace/output/ is the current task's artifact directory; other tasks' files are at /workspace/artifacts/<id>/",
            "- Tasks share data ONLY via artifact files — no direct communication",
            "",
            "### Available Tools",
        ]
        for t in self._tools:
            name = getattr(t, 'name', type(t).__name__)
            desc = _TOOL_DESCS.get(name, getattr(t, '__doc__', '') or '')
            lines.append(f"- **{name}**: {desc}" if desc else f"- {name}")
        return "\n".join(lines)

    def _describe_dataset(self) -> str:
        """Describe dataset files if available."""
        if not settings.dataset_dir:
            return ""
        dataset_path = Path(settings.dataset_dir)
        if not dataset_path.exists():
            return ""
        files = []
        for f in sorted(dataset_path.iterdir()):
            if f.is_file():
                size = f.stat().st_size
                if size >= 1024 * 1024:
                    s = f"{size / 1024 / 1024:.1f}MB"
                elif size >= 1024:
                    s = f"{size / 1024:.1f}KB"
                else:
                    s = f"{size}B"
                files.append(f"- {f.name} ({s})")
        if not files:
            return ""
        return "## Dataset\nFiles at /workspace/data/:\n" + "\n".join(files)

    def _check_stop(self):
        if self._stop_requested:
            raise asyncio.CancelledError()

    async def _execute(self) -> str:
        await asyncio.to_thread(_preflight_docker)

        self.output = ""
        idea = self.db.get_refined_idea()

        await self._calibrate_once(idea)
        await self._run_loop(idea)

        if self.state == StageState.FAILED:
            raise RuntimeError("Research stage failed: one or more tasks could not be completed")
        return self._build_final_output()

    # ------------------------------------------------------------------
    # Calibrate (one-time)
    # ------------------------------------------------------------------

    async def _calibrate_once(self, idea: str):
        self._current_phase = "calibrate"
        self._send(chunk={"text": "Calibrate", "call_id": "Calibrate", "label": True, "level": 2})
        self._atomic_definition = self.db.get_calibration()
        if not self._atomic_definition:
            calibrated = await self._calibrate(idea)
            if calibrated:
                self._atomic_definition = calibrated
                self.db.save_calibration(calibrated)
        self._send()  # done: calibration.md saved
        self._check_stop()

    # ------------------------------------------------------------------
    # Main loop: strategy → decompose → execute → evaluate → repeat
    # ------------------------------------------------------------------

    async def _run_loop(self, idea: str):
        iteration = self.db.get_iteration()

        # If the last completed evaluation was satisfied, nothing to do
        if iteration > 0:
            last_eval = self.db.get_evaluation(iteration - 1)
            if last_eval and not last_eval.get("strategy_update", "").strip():
                return

        while True:
            round_label = f"round {iteration}"
            is_final = iteration >= self._max_iterations - 1

            # Strategy — load from disk or generate
            self._current_phase = "strategy"
            strategy_tag = f"Strategy · {round_label}"
            self._send(chunk={"text": strategy_tag, "call_id": strategy_tag, "label": True, "level": 2})
            existing_strategy = self.db.get_strategy_for(iteration)
            if existing_strategy:
                self._strategy = existing_strategy
            elif iteration > 0:
                prev_eval = self.db.get_evaluation(iteration - 1)
                self._strategy = await self._update_strategy(idea, prev_eval)
                self.db.save_strategy(self._strategy, iteration)
            else:
                strategy = await self._research_strategy(idea)
                if strategy:
                    self._strategy = strategy
                    self.db.save_strategy(strategy, iteration)
            self._send()
            self._check_stop()

            # Decompose — reuse existing plan or generate
            self._current_phase = "decompose"
            decompose_tag = f"Decompose · {round_label}"
            self._send(chunk={"text": decompose_tag, "call_id": decompose_tag, "label": True, "level": 2})
            existing_plan = self.db.get_plan_list()
            if existing_plan:
                self._all_tasks = existing_plan
                self._tree = self.db.get_plan_tree() or self._tree
            has_pending = any(
                t["id"] not in self._task_results for t in self._all_tasks
            ) if self._all_tasks else False
            if not self._all_tasks:
                await self._decompose_fresh(idea)
            elif not has_pending and iteration > 0:
                round_id = f"r{iteration}"
                if not self._tree or not any(
                    c.get("id") == round_id
                    for c in self._tree.get("children", [])
                ):
                    await self._decompose_round(idea, iteration)
            self._send()
            self._check_stop()

            # Execute
            self._current_phase = "execute"
            self._init_task_batches()
            execute_tag = f"Execute · {round_label}"
            self._send(chunk={"text": execute_tag, "call_id": execute_tag, "label": True, "level": 2})
            self._send()

            self._check_stop()

            failed = await self._execute_all_tasks()
            if failed:
                break

            # Evaluate
            self._current_phase = "evaluate"
            evaluate_tag = f"Evaluate · {round_label}"
            self._send(chunk={"text": evaluate_tag, "call_id": evaluate_tag, "label": True, "level": 2})
            minimize = self.db.get_score_minimize()
            improved, current_score = self._check_score_improved(self._prev_score, minimize)
            prev_score_snapshot = self._prev_score
            if current_score is not None:
                self.db.update_meta(current_score=current_score, previous_score=self._prev_score, improved=improved)
                self._prev_score = current_score

            self._check_stop()

            summaries = [
                {"id": tid, "summary": self._task_summaries.get(tid, "(no summary)")}
                for tid in sorted(self._task_results.keys())
            ]
            evaluation = await self._evaluate_results(
                idea, summaries, current_score, prev_score_snapshot,
                minimize, iteration, is_final,
            )
            evaluation["score"] = current_score
            strategy_update = evaluation.get("strategy_update", "").strip()

            if not strategy_update:
                evaluation["satisfied"] = True
            self.db.save_evaluation(evaluation, iteration)
            self._send()

            if not strategy_update:
                break

            self._check_stop()
            iteration += 1
            if iteration >= self._max_iterations:
                log.warning("Reached max iterations (%d), stopping research loop",
                            self._max_iterations)
                break

    # ------------------------------------------------------------------
    # Decompose helpers
    # ------------------------------------------------------------------

    async def _decompose_fresh(self, idea: str):
        """First-pass decompose from research idea."""
        def _on_done(tree):
            self.db.save_plan(tree)  # tree progress, list written at end
            self._send()

        flat_tasks, tree = await decompose(
            idea=idea,
            stream_fn=lambda inst, ut, cid, cl, **kw: self._llm(inst, ut, cid, content_level=cl, **kw),
            max_depth=10,
            atomic_definition=self._atomic_definition,
            strategy=self._strategy,
            on_judge_done=_on_done,
            is_stale=lambda: False,
        )
        self._all_tasks = flat_tasks
        self._tree = tree
        self._persist_plan()

    async def _decompose_round(self, idea: str, round_num: int):
        """Iteration decompose with enriched context."""
        iteration_context = self._build_iteration_context(idea)
        round_id = f"r{round_num}"

        def _on_done(subtree):
            # Real-time: append/replace round subtree in main tree and save
            if self._tree:
                children = self._tree.setdefault("children", [])
                for i, c in enumerate(children):
                    if c.get("id") == round_id:
                        children[i] = subtree
                        break
                else:
                    children.append(subtree)
                self.db.save_plan(self._tree)
            self._send()

        new_flat, subtree = await decompose(
            idea=f"Round {round_num}",
            stream_fn=lambda inst, ut, cid, cl, **kw: self._llm(
                inst, ut, cid, content_level=cl, **kw),
            max_depth=10,
            atomic_definition=self._atomic_definition,
            strategy=self._strategy,
            on_judge_done=_on_done,
            is_stale=lambda: False,
            context=iteration_context,
            root_id=round_id,
        )

        if not new_flat:
            return

        self._all_tasks.extend(new_flat)
        self._persist_plan()

        self._send()  # done: decompose round finished

    def _init_task_batches(self):
        """Recompute pending-task batches after completed work and persist them."""
        completed_ids = set(self._task_results.keys())
        completed_batch_max = max(
            (int(t.get("batch", 0) or 0) for t in self._all_tasks if t["id"] in completed_ids),
            default=0,
        )
        pending_tasks = [t for t in self._all_tasks if t["id"] not in completed_ids]
        batches = topological_batches(pending_tasks, precompleted=completed_ids)
        updates = {}
        for batch_idx, batch in enumerate(batches):
            for t in batch:
                updates[t["id"]] = {
                    "status": "pending",
                    "batch": completed_batch_max + batch_idx + 1,
                }
        if updates:
            for t in self._all_tasks:
                fields = updates.get(t["id"])
                if fields:
                    t.update(fields)
            self._persist_plan()

    # ------------------------------------------------------------------
    # Task execution
    # ------------------------------------------------------------------

    async def _execute_all_tasks(self) -> bool:
        while True:
            batches = topological_batches(self._all_tasks)
            had_redecompose = False

            for batch in batches:
                pending = [t for t in batch if t["id"] not in self._task_results]
                if not pending:
                    continue

                results = await asyncio.gather(
                    *[self._execute_task(task) for task in pending],
                    return_exceptions=True,
                )

                for task, result in zip(pending, results):
                    if isinstance(result, Exception):
                        self._update_task(task["id"], status="failed")
                        self.state = StageState.FAILED
                        self._send(error=f"Task {task['id']} failed: {result}")
                        return True

                    needs_redecompose, _, exec_result, review = result
                    if needs_redecompose:
                        new_tasks = await self._redecompose_task(task, exec_result, review)
                        if new_tasks:
                            parent_id = task["id"]
                            subtask_ids = [t["id"] for t in new_tasks]
                            self._all_tasks = [t for t in self._all_tasks if t["id"] != parent_id]
                            self._all_tasks.extend(new_tasks)
                            for t in self._all_tasks:
                                if parent_id in t.get("dependencies", []):
                                    t["dependencies"] = [
                                        d for d in t["dependencies"] if d != parent_id
                                    ] + subtask_ids
                            self._persist_plan()
                            had_redecompose = True
                        else:
                            self._update_task(task["id"], status="failed")
                            self.state = StageState.FAILED
                            self._send(error=f"Task {task['id']}: redecompose produced no subtasks")
                            return True

                if had_redecompose:
                    break

            if not had_redecompose:
                break

        return False

    async def _execute_task(self, task: dict) -> tuple[bool, dict, str, str]:
        task_id = task["id"]
        # Derive parent from ID; _partial_outputs only has entries for redecomposed parents
        parts = task_id.rsplit("_", 1)
        parent_id = parts[0] if len(parts) > 1 else None
        prior_attempt = self._partial_outputs.get(parent_id, "") if parent_id else ""

        call_id = f"Exec {task_id}"

        async with (self._api_semaphore or contextlib.nullcontext()):
            self._current_task_id = task_id
            self.db.current_task_id = task_id
            self._send(status="running", task_id=task_id, description=task["description"])
            try:
                return await self._run_task_cycle(task, task_id, call_id, prior_attempt)
            finally:
                self._current_task_id = None
                self.db.current_task_id = None

    async def _run_task_cycle(self, task, task_id, call_id, prior_attempt):
        dep_summaries = {
            d: self._task_summaries[d]
            for d in task.get("dependencies", [])
            if d in self._task_summaries
        }
        instruction, user_text = build_execute_prompt(task, prior_attempt, dep_summaries)
        result = await self._llm(instruction, user_text, call_id, content_level=4, label=True, label_level=3, _skip_semaphore=True)
        self._update_summary(task_id, result)

        passed, review, redecompose = await self._verify_task(task, result, task_id, call_id)
        if passed:
            self._save_task(task_id, result)
            return (False, task, result, "")
        if redecompose:
            return (True, task, result, review)

        # Retry once
        self._send(status="retrying", task_id=task_id)
        ri, rt = build_retry_prompt(task, result, review, dep_summaries,
                                     prior_attempt=prior_attempt)
        result = await self._llm(ri, rt, call_id, content_level=4, _skip_semaphore=True)
        self._update_summary(task_id, result)

        passed, review, redecompose = await self._verify_task(task, result, task_id, call_id)
        if passed:
            self._save_task(task_id, result)
            return (False, task, result, "")
        if redecompose:
            return (True, task, result, review)

        raise RuntimeError(f"Task {task_id} failed verification after retry: {review}")

    async def _verify_task(self, task, result, task_id, call_id) -> tuple[bool, str, bool]:
        self._send(status="verifying", task_id=task_id)
        vi, vt = build_verify_prompt(task, result)
        for _parse_attempt in range(2):
            response = await self._llm(vi, vt, call_id, content_level=4, _skip_semaphore=True, tools=[])
            data = parse_json_fenced(response)
            if "pass" in data:
                return data.get("pass", False), data.get("review", ""), data.get("redecompose", False)
        log.warning("Task %s: verify JSON parse failed after retry, treating as not passed", task_id)
        return False, "", False

    def _update_summary(self, task_id: str, result: str):
        summary = self._extract_summary(result)
        if summary:
            self._task_summaries[task_id] = summary

    def _save_task(self, task_id: str, result: str):
        summary = self._task_summaries.get(task_id, "")
        if not summary:
            log.warning("Task %s completed without SUMMARY line — downstream context will be degraded", task_id)
            summary = f"(Task {task_id} completed, no summary provided)"
        self._task_results[task_id] = result
        self._update_task(task_id, status="completed", summary=summary)
        if self.db:
            self.db.save_task_output(task_id, result)
            self.db.promote_best_score()
        self._send(task_id=task_id)  # done: task output saved

    @staticmethod
    def _extract_summary(result: str) -> str:
        """Extract SUMMARY: line from execute result."""
        for line in reversed(result.strip().splitlines()):
            stripped = line.strip()
            if stripped.upper().startswith("SUMMARY:"):
                return stripped[len("SUMMARY:"):].strip()
        return ""

    # ------------------------------------------------------------------
    # Evaluate & Strategy
    # ------------------------------------------------------------------

    async def _research_strategy(self, idea: str) -> str:
        call_id = "Strategy"
        parts = [self._build_capability_profile()]
        dataset = self._describe_dataset()
        if dataset:
            parts.append(dataset)
        if self._atomic_definition:
            parts.append(f"## Atomic Task Definition (from Calibrate)\n{self._atomic_definition}")
        parts.append(f"## Research Topic\n{idea}")
        response = await self._llm(STRATEGY_SYSTEM, "\n\n".join(parts), call_id, content_level=3)
        direction_data = parse_json_fenced(response, fallback={})
        if "score_direction" in direction_data:
            minimize = direction_data["score_direction"] != "maximize"
            self.db.save_score_direction(minimize)
        return response.strip()

    def _check_score_improved(self, prev_score, minimize=True):
        score_file = self.db.get_artifacts_dir() / "latest_score.json"
        if not score_file.exists():
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

    async def _evaluate_results(
        self,
        idea: str,
        task_summaries: list[dict],
        current_score: float | None,
        prev_score: float | None,
        minimize: bool,
        iteration: int,
        is_final: bool = False,
    ) -> dict:
        call_id = "Evaluate"
        summaries_text = "\n".join(
            f"- **Task [{s['id']}]**: {s['summary']}" for s in task_summaries
        )
        prior_evals = self.db.load_evaluations() if iteration > 0 else []
        capabilities = self._build_capability_profile()
        user_text = build_evaluate_user(
            idea=idea,
            summaries_text=summaries_text,
            current_score=current_score,
            prev_score=prev_score,
            minimize=minimize,
            capabilities=capabilities,
            strategy=self._strategy or "",
            prior_evaluations=prior_evals,
            is_final=is_final,
        )
        for _parse_attempt in range(2):
            response = await self._llm(EVALUATE_SYSTEM, user_text, call_id, content_level=3)
            data = parse_json_fenced(response)
            if "feedback" in data or "suggestions" in data:
                return data
        log.warning("Evaluate JSON parse failed after retry")
        return {"feedback": "", "suggestions": []}

    async def _update_strategy(self, idea: str, evaluation: dict) -> str:
        call_id = "Strategy"
        user_text = build_strategy_update_user(
            idea=idea,
            old_strategy=self._strategy or "",
            evaluation=evaluation,
            capabilities=self._build_capability_profile(),
            dataset=self._describe_dataset(),
        )
        response = await self._llm(STRATEGY_SYSTEM, user_text, call_id, content_level=3)
        direction_data = parse_json_fenced(response, fallback={})
        if "score_direction" in direction_data:
            minimize = direction_data["score_direction"] != "maximize"
            self.db.save_score_direction(minimize)
        return response.strip()

    def _build_iteration_context(self, idea: str) -> str:
        parts = [f"## Research Goal\n{idea}"]
        completed_ids = sorted(self._task_results.keys())
        if completed_ids:
            summary_lines = [
                f"- Task [{tid}]: {self._task_summaries.get(tid, 'completed')}"
                for tid in completed_ids
            ]
            parts.append("\n## Completed Work (do NOT redo these)\n"
                         + "\n".join(summary_lines))
        artifacts_dir = self.db.get_artifacts_dir()
        if artifacts_dir.exists():
            artifact_names = [
                f.name for f in artifacts_dir.iterdir()
                if f.is_file() and not f.name.startswith("run_")
            ]
            if artifact_names:
                parts.append(f"\n## Available Artifacts\n{', '.join(artifact_names)}")
        return "\n".join(parts)

    async def _calibrate(self, idea: str) -> str:
        profile = self._build_capability_profile()
        dataset = self._describe_dataset()
        call_id = "Calibrate"
        parts = [profile]
        if dataset:
            parts.append(dataset)
        parts.append(f"## Research Topic\n{idea}")
        response = await self._llm(CALIBRATE_SYSTEM, "\n\n".join(parts), call_id, content_level=3)
        return response.strip()

    # ------------------------------------------------------------------
    # Redecompose
    # ------------------------------------------------------------------

    def _get_task_siblings(self, task_id: str) -> list[dict]:
        """Get sibling tasks from the decomposition tree."""
        if not self._tree:
            return []
        def find_parent(node, target_id):
            for child in node.get("children", []):
                if child.get("id") == target_id:
                    return node
                found = find_parent(child, target_id)
                if found:
                    return found
            return None
        parent = find_parent(self._tree, task_id)
        if not parent:
            return []
        return [
            {"id": c["id"], "description": c["description"]}
            for c in parent.get("children", [])
            if c.get("id") != task_id
        ]

    async def _redecompose_task(self, task: dict, result: str, review: str) -> list[dict]:
        task_id = task["id"]
        self._send(status="decomposing", task_id=task_id)
        self._partial_outputs[task_id] = result

        if settings.is_chinese():
            enriched_desc = (
                f"{task['description']}\n\n"
                f"--- 此任务曾尝试执行但验证未通过 ---\n"
                f"审查反馈：{review}\n"
                f"已有结果中合格的部分不需要重做，聚焦于缺失或需要不同方法的部分。"
            )
        else:
            enriched_desc = (
                f"{task['description']}\n\n"
                f"--- This task was attempted but failed verification ---\n"
                f"Review: {review}\n"
                f"Do not redo parts that are already adequate — focus on what is missing."
            )

        def _on_done(tree):
            if self._tree:
                node = _find_node(self._tree, task_id)
                if node:
                    node.update(tree)
                self.db.save_plan(self._tree)
            saved = self._current_phase
            self._current_phase = "decompose"
            self._send()
            self._current_phase = saved

        flat_tasks, subtree = await decompose(
            idea=enriched_desc,
            stream_fn=lambda inst, ut, cid, cl, **kw: self._llm(inst, ut, cid, content_level=cl, **kw),
            max_depth=10,
            atomic_definition=self._atomic_definition,
            strategy=self._strategy,
            on_judge_done=_on_done,
            is_stale=lambda: False,
            context=self.db.get_refined_idea(),
            root_siblings=self._get_task_siblings(task_id),
            root_id=task_id,
        )
        if not flat_tasks:
            return []

        # Caller (_execute_all_tasks) updates _all_tasks and calls _persist_plan
        self._current_phase = "execute"
        self._send()
        return flat_tasks

    # ------------------------------------------------------------------
    # Final output
    # ------------------------------------------------------------------

    def _build_final_output(self) -> str:
        if self.db:
            try:
                from backend.pipeline.results_summary import build_results_summary
                data, markdown = build_results_summary(self.db)
                self.db.save_results_summary(data, markdown)
            except Exception:
                log.exception("Failed to generate results summary")
            try:
                from backend.reproduce import generate_reproduce_files
                generate_reproduce_files(self.db)
            except Exception:
                pass
        parts = []
        for task_id in sorted(self._task_results.keys()):
            parts.append(f"## Task [{task_id}]\n\n{self._task_results[task_id]}")
        return "\n\n---\n\n".join(parts)

    # ------------------------------------------------------------------
    # Plan persistence — _all_tasks is the in-memory source of truth
    # ------------------------------------------------------------------

    def _persist_plan(self):
        """Write current in-memory plan (tree + task list) to disk."""
        if self.db:
            self.db.save_plan(self._tree or {}, self._all_tasks)

    def _update_task(self, task_id: str, **fields):
        """Update a task's fields in _all_tasks and sync to disk."""
        for t in self._all_tasks:
            if t["id"] == task_id:
                t.update(fields)
                break
        self._persist_plan()

    def retry(self):
        super().retry()
        self._task_results.clear()
        self._task_summaries.clear()
        self._all_tasks.clear()
        self._tree = None
        self._strategy = ""
        self._prev_score = None
        self._partial_outputs.clear()
