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
    CALIBRATE_SYSTEM, EVALUATE_SYSTEM, REPLAN_SYSTEM, REDECOMPOSE_CONTEXT,
    STRATEGY_SYSTEM, build_execute_prompt, build_verify_prompt, build_retry_prompt,
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


def _renumber_subtree(children: list[dict], parent_id: str) -> list[dict]:
    id_map: dict[str, str] = {}
    def collect(nodes):
        for n in nodes:
            id_map[n["id"]] = f"{parent_id}_d{n['id']}"
            collect(n.get("children", []))
    collect(children)
    def rename(node):
        return {
            "id": id_map.get(node["id"], node["id"]),
            "description": node["description"],
            "is_atomic": node.get("is_atomic"),
            "dependencies": [id_map.get(d, d) for d in node.get("dependencies", [])],
            "children": [rename(c) for c in node.get("children", [])],
        }
    return [rename(c) for c in children]


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
        self._redecompose_parent: dict[str, str] = {}
        self._current_task_id: str | None = None

    def _llm(self, instruction, user_text, call_id, content_level=2, timeout=1800, **kwargs):
        task_id = kwargs.pop("task_id", None) or self._current_task_id or ""
        return self._stream_llm(
            self._model, self._tools, instruction, user_text, call_id,
            content_level=content_level, timeout=timeout, task_id=task_id, **kwargs,
        )

    def _describe_capabilities(self) -> str:
        tool_descs = []
        for t in self._tools:
            name = getattr(t, 'name', type(t).__name__)
            tool_descs.append(f"- {name}")
        tools_str = "\n".join(tool_descs) if tool_descs else "(none)"
        return f"AI Agent (Agno) with multi-step reasoning. Model: {self._model.__class__.__name__}\nAvailable tools:\n{tools_str}"

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
        await self._prepare(idea)
        await self._run_iterations(idea)
        if self.state == StageState.FAILED:
            return self.output
        return self._build_final_output()

    # ------------------------------------------------------------------
    # Prepare: calibrate → strategy → decompose
    # ------------------------------------------------------------------

    async def _prepare(self, idea: str):
        self._current_phase = "calibrate"
        self._atomic_definition = self.db.get_calibration()
        if not self._atomic_definition:
            calibrated = await self._calibrate(idea)
            if calibrated:
                self._atomic_definition = calibrated
                self.db.save_calibration(calibrated)
        self._send()  # done: calibration.md saved

        self._check_stop()

        self._current_phase = "strategy"
        self._strategy = self.db.get_strategy()
        if not self._strategy:
            strategy = await self._research_strategy(idea)
            if strategy:
                self._strategy = strategy
                self.db.save_strategy(strategy)
        self._send()  # done: strategy.md saved

        self._check_stop()

        self._current_phase = "decompose"
        existing_plan = self.db.get_plan_list()
        if existing_plan and self._task_results:
            self._all_tasks = existing_plan
            tree = self.db.get_plan_tree()
            if tree:
                self._tree = tree
        else:
            def _on_judge_done(tree):
                self.db.save_tree(tree)
                self._send()

            flat_tasks, tree = await decompose(
                idea=idea,
                stream_fn=lambda inst, ut, cid, cl, **kw: self._llm(inst, ut, cid, content_level=cl, **kw),
                max_depth=10,
                atomic_definition=self._atomic_definition,
                strategy=self._strategy,
                on_judge_done=_on_judge_done,
                is_stale=lambda: False,
            )
            self._all_tasks = flat_tasks
            self._tree = tree
            self.db.save_plan(flat_tasks, tree)
        self._send()  # done: decompose finished

    # ------------------------------------------------------------------
    # Iterate: execute → evaluate → replan loop
    # ------------------------------------------------------------------

    async def _run_iterations(self, idea: str):
        self._current_phase = "execute"
        await asyncio.to_thread(_preflight_docker)

        # Initialize task statuses with batch numbers
        batches = topological_batches(self._all_tasks)
        for batch_idx, batch in enumerate(batches):
            for t in batch:
                if t["id"] not in self._task_results:
                    self.db.update_task_status(t["id"], "pending")
                    self._update_task_batch(t["id"], batch_idx + 1)
        self._send(chunk={"text": "Execute", "call_id": "Execute", "label": True, "level": 2})
        self._send()  # done: plan_list ready with statuses

        self._check_stop()

        start_iteration = self.db.get_iteration()
        for iteration in range(start_iteration, self._max_iterations):
            self._check_stop()

            failed = await self._execute_all_tasks()
            if failed:
                break

            is_last = iteration >= self._max_iterations - 1
            self._current_phase = "evaluate"

            minimize = self.db.get_score_minimize()
            improved, current_score = self._check_score_improved(self._prev_score, minimize)
            if current_score is not None:
                self.db.update_meta(current_score=current_score, previous_score=self._prev_score, improved=improved)
                self._prev_score = current_score

            if is_last:
                self.db.save_evaluation({"satisfied": True, "score": current_score}, iteration)
                break

            if not improved and self._prev_score is not None:
                self.db.save_evaluation({"satisfied": True, "score": current_score}, iteration)
                break

            self._check_stop()

            summaries = [
                {"id": tid, "summary": self._task_summaries.get(tid, "(no summary)")}
                for tid in sorted(self._task_results.keys())
            ]
            evaluation = await self._evaluate_results(idea, summaries)
            evaluation["score"] = current_score
            self.db.save_evaluation(evaluation, iteration)
            self._send()  # done: evaluation saved

            self._check_stop()

            new_tasks = await self._replan(idea, evaluation)
            if not new_tasks:
                break

            round_num = iteration + 1
            new_tasks = self._renumber_tasks(new_tasks, round_num)
            self._all_tasks.extend(new_tasks)

            replan_subtree = {
                "id": f"r{round_num}",
                "description": f"Replan round {round_num}",
                "is_atomic": False,
                "dependencies": [],
                "children": [
                    {"id": t["id"], "description": t["description"], "is_atomic": True,
                     "dependencies": t.get("dependencies", []), "children": []}
                    for t in new_tasks
                ],
            }
            if self._tree:
                self._tree.setdefault("children", []).append(replan_subtree)
            self.db.save_plan_amendment(new_tasks, round_num, replan_subtree)

            self._current_phase = "execute"

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
        task_id = task["id"]
        self._current_task_id = task_id
        self.db.current_task_id = task_id
        try:
            return await self._execute_task_inner(task)
        finally:
            self._current_task_id = None
            self.db.current_task_id = None

    async def _execute_task_inner(self, task: dict) -> tuple[bool, dict, str, str]:
        task_id = task["id"]
        parent_id = self._redecompose_parent.get(task_id)
        prior_attempt = self._partial_outputs.get(parent_id, "") if parent_id else ""

        call_id = f"Exec {task_id}"
        self._send(status="running", task_id=task_id, description=task["description"])
        instruction, user_text = build_execute_prompt(task, prior_attempt)
        result = await self._llm(instruction, user_text, call_id, content_level=4, label=True, label_level=3)

        self._send(status="verifying", task_id=task_id)
        vi, vt = build_verify_prompt(task, result)
        verify_response = await self._llm(vi, vt, call_id, content_level=4)
        passed, review, summary, redecompose = self._parse_verification(verify_response)
        self._task_summaries[task_id] = summary

        if passed:
            self._save_task(task_id, result)
            return (False, task, result, "")
        if redecompose:
            return (True, task, result, review)

        self._send(status="retrying", task_id=task_id)
        ri, rt = build_retry_prompt(task, result, review)
        result = await self._llm(ri, rt, call_id, content_level=4)

        self._send(status="verifying", task_id=task_id)
        vi, vt = build_verify_prompt(task, result)
        verify_response = await self._llm(vi, vt, call_id, content_level=4)
        passed, review, summary, redecompose = self._parse_verification(verify_response)
        self._task_summaries[task_id] = summary

        if passed:
            self._save_task(task_id, result)
            return (False, task, result, "")
        if redecompose:
            return (True, task, result, review)

        self.db.update_task_status(task_id, "failed")
        raise RuntimeError(f"Task {task_id} failed verification after retry: {review}")

    def _save_task(self, task_id: str, result: str):
        summary = self._task_summaries.get(task_id, "")
        if self.db:
            self.db.save_task_output(task_id, result)
            self.db.update_task_status(task_id, "completed", summary)
        self._task_results[task_id] = result
        self._send(task_id=task_id)  # done: task output saved

    def _parse_verification(self, response: str) -> tuple[bool, str, str, bool]:
        data = parse_json_fenced(response, fallback={"pass": True})
        return (
            data.get("pass", True),
            data.get("review", ""),
            data.get("summary", ""),
            data.get("redecompose", False),
        )

    # ------------------------------------------------------------------
    # Replan
    # ------------------------------------------------------------------

    async def _replan(self, idea: str, evaluation: dict) -> list[dict]:
        feedback = evaluation.get("feedback", "")
        suggestions = evaluation.get("suggestions", [])
        if not feedback and not suggestions:
            return []
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
            user_parts.append("\n## Suggestions\n" + "\n".join(f"- {s}" for s in suggestions))
        call_id = "Replan"
        self._send(chunk={"text": call_id, "call_id": call_id, "label": True, "level": 3})
        response = await self._llm(REPLAN_SYSTEM, "\n".join(user_parts), call_id, content_level=3)
        data = parse_json_fenced(response, fallback={"add": []})
        valid = []
        for t in data.get("add", []):
            if isinstance(t, dict) and "id" in t and "description" in t:
                valid.append({"id": t["id"], "description": t["description"],
                              "dependencies": t.get("dependencies", [])})
        return valid

    def _load_prev_score(self) -> float | None:
        try:
            return self.db.get_latest_score()
        except RuntimeError:
            return None

    async def _research_strategy(self, idea: str) -> str:
        call_id = "Strategy"
        self._send(chunk={"text": call_id, "call_id": call_id, "label": True, "level": 2})
        response = await self._llm(STRATEGY_SYSTEM, f"## Research Topic\n{idea}", call_id, content_level=3)
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

    async def _evaluate_results(self, idea: str, task_summaries: list[dict]) -> dict:
        call_id = "Evaluate"
        self._send(chunk={"text": call_id, "call_id": call_id, "label": True, "level": 2})
        summaries_text = "\n".join(
            f"- **Task [{s['id']}]**: {s['summary']}" for s in task_summaries
        )
        user_text = (
            f"## Research Goal\n{idea}\n\n"
            f"## Completed Task Summaries\n{summaries_text}\n\n"
            f"Use read_task_output and list_artifacts to investigate actual results. "
            f"Analyze what can be improved and provide specific suggestions."
        )
        response = await self._llm(EVALUATE_SYSTEM, user_text, call_id, content_level=3)
        return parse_json_fenced(response, fallback={"feedback": "", "suggestions": []})

    async def _calibrate(self, idea: str) -> str:
        capabilities = self._describe_capabilities()
        call_id = "Calibrate"
        self._send(chunk={"text": call_id, "call_id": call_id, "label": True, "level": 2})
        user_text = f"## Your Capabilities\n{capabilities}\n\n## Research Topic\n{idea}"
        response = await self._llm(CALIBRATE_SYSTEM, user_text, call_id, content_level=3)
        return response.strip()

    # ------------------------------------------------------------------
    # Redecompose
    # ------------------------------------------------------------------

    async def _redecompose_task(self, task: dict, result: str, review: str) -> list[dict]:
        task_id = task["id"]
        self._send(status="decomposing", task_id=task_id)
        self._partial_outputs[task_id] = result
        context = REDECOMPOSE_CONTEXT.format(
            task_id=task_id, description=task["description"],
            result=result, review=review,
        )

        def _on_redecomp_done(tree):
            self.db.save_tree(tree)
            saved = self._current_phase
            self._current_phase = "decompose"
            self._send()
            self._current_phase = saved

        flat_tasks, subtree = await decompose(
            idea=context,
            stream_fn=lambda inst, ut, cid, cl, **kw: self._llm(inst, ut, cid, content_level=cl, **kw),
            max_depth=3,
            atomic_definition=self._atomic_definition,
            on_judge_done=_on_redecomp_done,
            is_stale=lambda: False,
        )
        if not flat_tasks:
            return []

        parent_deps = task.get("dependencies", [])
        id_map = {t["id"]: f"{task_id}_d{t['id']}" for t in flat_tasks}
        renumbered = []
        for t in flat_tasks:
            new_id = id_map[t["id"]]
            internal_deps = [id_map.get(d, d) for d in t.get("dependencies", [])]
            new_deps = internal_deps if internal_deps else list(parent_deps)
            renumbered.append({"id": new_id, "description": t["description"], "dependencies": new_deps})
            self._redecompose_parent[new_id] = task_id

        if self.db:
            updated = [t for t in self._all_tasks if t["id"] != task_id] + renumbered
            if self._tree:
                parent_node = _find_node(self._tree, task_id)
                if parent_node:
                    parent_node["is_atomic"] = False
                    parent_node["children"] = _renumber_subtree(subtree.get("children", []), task_id)
            self.db.save_plan(updated, self._tree or {})
            saved = self._current_phase
            self._current_phase = "decompose"
            self._send()
            self._current_phase = saved
            self._send()  # execute done: plan_list updated

        return renumbered

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
