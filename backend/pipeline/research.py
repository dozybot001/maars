"""Research stage: decompose → execute → evaluate → loop."""

from __future__ import annotations

import asyncio
import json
import logging

from backend.config import settings

log = logging.getLogger(__name__)
from backend.db import ResearchDB
from backend.pipeline.stage import Stage, StageState
from backend.pipeline.decompose import decompose
from backend.pipeline.prompts import (
    CALIBRATE_SYSTEM, EVALUATE_SYSTEM,
    STRATEGY_SYSTEM, build_execute_prompt, build_verify_prompt, build_retry_prompt,
    build_evaluate_user, build_strategy_update_user,
)
from backend.utils import parse_json_fenced


def topological_batches(tasks: list[dict]) -> list[list[dict]]:
    task_map = {t["id"]: t for t in tasks}
    remaining = set(task_map.keys())
    completed: set[str] = set()
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
        raise RuntimeError("Docker SDK not installed. Run: pip install docker")
    try:
        client = docker.from_env()
        client.ping()
    except Exception as e:
        raise RuntimeError(f"Docker is not running: {e}")


def _find_node(tree: dict, node_id: str) -> dict | None:
    if tree.get("id") == node_id:
        return tree
    for child in tree.get("children", []):
        found = _find_node(child, node_id)
        if found:
            return found
    return None



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

    def _llm(self, instruction, user_text, call_id, content_level=2, timeout=1800, **kwargs):
        task_id = kwargs.pop("task_id", None) or self._current_task_id or ""
        skip_sem = kwargs.pop("_skip_semaphore", False)
        return self._stream_llm(
            self._model, self._tools, instruction, user_text, call_id,
            content_level=content_level, timeout=timeout, task_id=task_id,
            _skip_semaphore=skip_sem, **kwargs,
        )

    def _build_capability_profile(self) -> str:
        """Deterministic capability profile built from config + tools."""
        _TOOL_DESCS = {
            'code_execute': 'Execute Python in Docker sandbox. Returns stdout, stderr, exit_code, generated file list. stdout truncated to 5000 chars.',
            'list_artifacts': 'List files in current task artifacts directory.',
            'read_task_output': 'Read markdown output of a completed sibling task.',
            'list_tasks': 'List all completed tasks with IDs and sizes.',
            'read_refined_idea': 'Read the refined research idea.',
            'read_plan_tree': 'Read the full decomposition tree.',
            'DuckDuckGoTools': 'Web search via DuckDuckGo.',
            'ArxivTools': 'Search academic papers on arXiv.',
            'WikipediaTools': 'Search Wikipedia articles.',
        }
        lines = [
            "## Execution Environment",
            "",
            "### Docker Sandbox",
            f"- Timeout per code_execute: {settings.docker_sandbox_timeout}s",
            f"- Memory: {settings.docker_sandbox_memory}",
            f"- CPU: {settings.docker_sandbox_cpu} cores",
            f"- Network: {'enabled' if settings.docker_sandbox_network else 'disabled'}",
            "",
            "### Execution Model",
            "- Each task = ONE independent agent session (single system prompt + user message)",
            "- Agent can make MULTIPLE tool calls within one session",
            "- Each code_execute runs in a fresh container; files persist in /workspace/output/ within the same task",
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
        from pathlib import Path
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
        self.output = ""
        self._task_results = {}
        self._task_summaries = {}
        self._prev_score = self._load_prev_score()
        self._load_checkpoint()
        idea = self.db.get_refined_idea()

        await self._calibrate_once(idea)
        await self._run_loop(idea)

        if self.state == StageState.FAILED:
            return self.output
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
        await asyncio.to_thread(_preflight_docker)

        iteration = self.db.get_iteration()
        evaluation = None  # None = first pass; has data = subsequent pass

        while True:
            round_label = f"round {iteration + 1}"
            is_final = iteration >= self._max_iterations - 1

            # Strategy
            self._current_phase = "strategy"
            strategy_tag = f"Strategy · {round_label}"
            self._send(chunk={"text": strategy_tag, "call_id": strategy_tag, "label": True, "level": 2})
            if evaluation:
                new_strategy = await self._update_strategy(idea, evaluation)
                self._strategy = new_strategy
                self.db.save_strategy(new_strategy)
            else:
                self._strategy = self.db.get_strategy()
                if not self._strategy:
                    strategy = await self._research_strategy(idea)
                    if strategy:
                        self._strategy = strategy
                        self.db.save_strategy(strategy)
            self._send()
            self._check_stop()

            # Decompose
            self._current_phase = "decompose"
            decompose_tag = f"Decompose · {round_label}"
            self._send(chunk={"text": decompose_tag, "call_id": decompose_tag, "label": True, "level": 2})
            if evaluation:
                await self._decompose_round(idea, iteration + 1)
            else:
                existing_plan = self.db.get_plan_list()
                if existing_plan and self._task_results:
                    self._all_tasks = existing_plan
                    tree = self.db.get_plan_tree()
                    if tree:
                        self._tree = tree
                else:
                    await self._decompose_fresh(idea)
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
            _, current_score = self._check_score_improved(self._prev_score, minimize)
            prev_score_snapshot = self._prev_score
            if current_score is not None:
                self.db.update_meta(current_score=current_score, previous_score=self._prev_score)
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

    # ------------------------------------------------------------------
    # Decompose helpers
    # ------------------------------------------------------------------

    async def _decompose_fresh(self, idea: str):
        """First-pass decompose from research idea."""
        def _on_done(tree):
            self.db.save_tree(tree)
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
        self.db.save_plan(flat_tasks, tree)

    async def _decompose_round(self, idea: str, round_num: int):
        """Iteration decompose with enriched context."""
        iteration_context = self._build_iteration_context(idea)

        def _on_done(tree):
            # Don't save to DB — this is the new round's partial tree, not the full tree.
            # Full tree is saved after round_subtree is appended to self._tree.
            self._send()

        new_flat, _ = await decompose(
            idea=iteration_context,
            stream_fn=lambda inst, ut, cid, cl, **kw: self._llm(
                inst, ut, cid, content_level=cl, **kw),
            max_depth=10,
            atomic_definition=self._atomic_definition,
            strategy=self._strategy,
            on_judge_done=_on_done,
            is_stale=lambda: False,
        )

        if not new_flat:
            return

        new_flat = self._renumber_tasks(new_flat, round_num)
        self._all_tasks.extend(new_flat)

        round_subtree = {
            "id": f"r{round_num}",
            "description": f"Round {round_num}",
            "is_atomic": False,
            "dependencies": [],
            "children": [
                {"id": t["id"], "description": t["description"], "is_atomic": True,
                 "dependencies": t.get("dependencies", []), "children": []}
                for t in new_flat
            ],
        }
        if self._tree:
            self._tree.setdefault("children", []).append(round_subtree)
            self.db.save_tree(self._tree)
        self.db.save_plan_amendment(new_flat)

        # Assign batch numbers and pending status
        new_batches = topological_batches(new_flat)
        max_batch = max(
            (t.get("batch", 0)
             for t in self.db.get_plan_list()
             if t["id"] not in [nt["id"] for nt in new_flat]),
            default=0,
        )
        for batch_idx, batch in enumerate(new_batches):
            for t in batch:
                self.db.update_task_status(t["id"], "pending")
                self._update_task_batch(t["id"], max_batch + batch_idx + 1)

        self._send()  # done: decompose round finished

    def _init_task_batches(self):
        """Set batch numbers and pending status for unexecuted tasks."""
        batches = topological_batches(self._all_tasks)
        for batch_idx, batch in enumerate(batches):
            for t in batch:
                if t["id"] not in self._task_results:
                    self.db.update_task_status(t["id"], "pending")
                    self._update_task_batch(t["id"], batch_idx + 1)

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
                        self.db.update_task_status(task["id"], "failed")
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
                            had_redecompose = True
                        else:
                            self.db.update_task_status(task["id"], "failed")
                            self.state = StageState.FAILED
                            self._send(error=f"Task {task['id']}: redecompose produced no subtasks")
                            return True

                if had_redecompose:
                    break

            if not had_redecompose:
                break

        return False

    async def _execute_task(self, task: dict) -> tuple[bool, dict, str, str]:
        return await self._execute_task_inner(task)

    async def _execute_task_inner(self, task: dict) -> tuple[bool, dict, str, str]:
        task_id = task["id"]
        # Derive parent from ID; _partial_outputs only has entries for redecomposed parents
        parts = task_id.rsplit("_", 1)
        parent_id = parts[0] if len(parts) > 1 else None
        prior_attempt = self._partial_outputs.get(parent_id, "") if parent_id else ""

        call_id = f"Exec {task_id}"

        from backend.pipeline.stage import _get_api_semaphore
        async with _get_api_semaphore():
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

        # Summary comes from execute, not verify
        summary = self._extract_summary(result)
        if summary:
            self._task_summaries[task_id] = summary

        self._send(status="verifying", task_id=task_id)
        vi, vt = build_verify_prompt(task, result)
        verify_response = await self._llm(vi, vt, call_id, content_level=4, _skip_semaphore=True)
        passed, review, redecompose = self._parse_verification(verify_response)

        if passed:
            self._save_task(task_id, result)
            return (False, task, result, "")
        if redecompose:
            return (True, task, result, review)

        self._send(status="retrying", task_id=task_id)
        ri, rt = build_retry_prompt(task, result, review, dep_summaries)
        result = await self._llm(ri, rt, call_id, content_level=4, _skip_semaphore=True)

        retry_summary = self._extract_summary(result)
        if retry_summary:
            self._task_summaries[task_id] = retry_summary

        self._send(status="verifying", task_id=task_id)
        vi, vt = build_verify_prompt(task, result)
        verify_response = await self._llm(vi, vt, call_id, content_level=4, _skip_semaphore=True)
        passed, review, redecompose = self._parse_verification(verify_response)

        if passed:
            self._save_task(task_id, result)
            return (False, task, result, "")
        if redecompose:
            return (True, task, result, review)

        self.db.update_task_status(task_id, "failed")
        raise RuntimeError(f"Task {task_id} failed verification after retry: {review}")

    def _save_task(self, task_id: str, result: str):
        summary = self._task_summaries.get(task_id, "")
        if not summary:
            log.warning("Task %s completed without SUMMARY line — downstream context will be degraded", task_id)
            summary = f"(Task {task_id} completed, no summary provided)"
        if self.db:
            self.db.save_task_output(task_id, result)
            self.db.update_task_status(task_id, "completed", summary)
        self._task_results[task_id] = result
        self._send(task_id=task_id)  # done: task output saved

    @staticmethod
    def _extract_summary(result: str) -> str:
        """Extract SUMMARY: line from execute result."""
        for line in reversed(result.strip().splitlines()):
            stripped = line.strip()
            if stripped.upper().startswith("SUMMARY:"):
                return stripped[len("SUMMARY:"):].strip()
        return ""

    def _parse_verification(self, response: str) -> tuple[bool, str, bool]:
        data = parse_json_fenced(response, fallback={"pass": False})
        return (
            data.get("pass", False),
            data.get("review", ""),
            data.get("redecompose", False),
        )

    # ------------------------------------------------------------------
    # Evaluate & Strategy
    # ------------------------------------------------------------------

    def _load_prev_score(self) -> float | None:
        try:
            return self.db.get_latest_score()
        except RuntimeError:
            return None

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
        response = await self._llm(EVALUATE_SYSTEM, user_text, call_id, content_level=3)
        return parse_json_fenced(response, fallback={"feedback": "", "suggestions": []})

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

        if settings.output_language.lower().startswith("ch"):
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
                self.db.save_tree(self._tree)
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

        if self.db:
            updated = [t for t in self._all_tasks if t["id"] != task_id] + flat_tasks
            self.db.save_plan(updated, self._tree or {})
            self._current_phase = "execute"
            self._send()

        return flat_tasks

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_task_batch(self, task_id: str, batch: int):
        """Set batch number for a task in plan_list.json."""
        plan_path = self.db._root / "plan_list.json"
        from backend.db import _read_json, _write_json
        tasks = _read_json(plan_path, default=[])
        for t in tasks:
            if t["id"] == task_id:
                t["batch"] = batch
                break
        _write_json(plan_path, tasks)

    def _renumber_tasks(self, tasks: list[dict], round_num: int) -> list[dict]:
        prefix = f"r{round_num}_"
        id_map = {t["id"]: f"{prefix}{t['id']}" for t in tasks}
        renumbered = []
        for task in tasks:
            new_deps = [id_map.get(dep, dep) for dep in task.get("dependencies", [])]
            renumbered.append({"id": id_map[task["id"]], "description": task["description"], "dependencies": new_deps})
        return renumbered

    def _build_final_output(self) -> str:
        if self.db:
            try:
                from backend.reproduce import generate_reproduce_files
                generate_reproduce_files(self.db)
            except Exception:
                pass
        parts = []
        for task_id in sorted(self._task_results.keys()):
            parts.append(f"## Task [{task_id}]\n\n{self._task_results[task_id]}")
        return "\n\n---\n\n".join(parts)

    def _load_checkpoint(self):
        if not self.db:
            return
        for info in self.db.list_completed_tasks():
            task_id = info["id"]
            output = self.db.get_task_output(task_id)
            if output:
                self._task_results[task_id] = output
        # Warm summary cache from plan_list.json
        for task in self.db.get_plan_list():
            tid = task.get("id", "")
            summary = task.get("summary", "")
            if tid and summary and tid in self._task_results:
                self._task_summaries[tid] = summary

    def retry(self):
        super().retry()
        self._task_results.clear()
        self._task_summaries.clear()
        self._all_tasks.clear()
        self._tree = None
        self._strategy = ""
        self._prev_score = None
        self._partial_outputs.clear()
        if self.db:
            self.db.clear_tasks()
            self.db.clear_plan()
