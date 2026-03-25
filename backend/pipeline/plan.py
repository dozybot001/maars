from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field

from backend.pipeline.stage import BaseStage, StageState

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Task:
    id: str
    description: str
    dependencies: list[str] = field(default_factory=list)  # sibling-level IDs
    is_atomic: bool | None = None  # None = not yet judged
    children: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a research project planner. Your job is to decompose tasks into smaller subtasks.

IMPORTANT CONTEXT: This is the PLAN stage of a 4-stage automated research pipeline: Refine → Plan → Execute → Write.
- You are in the PLAN stage: decompose the research into executable atomic tasks.
- The EXECUTE stage will run each atomic task (with tools: search, code execution, etc.).
- A separate WRITE stage will synthesize all task outputs into the final research paper.
- Therefore: do NOT create "write paper" or "compile report" tasks. Only create research/analysis/experiment tasks. The final synthesis is handled by the Write stage, not here.
- No human is in the loop. Make all decisions autonomously.

Given a task, decide:
1. Is it **atomic**? A task is atomic if a single focused LLM call can produce a reliable, complete, self-contained text result for it (e.g., "analyze X", "compare A and B", "summarize findings on Y").
2. If NOT atomic, decompose it into subtasks with dependencies.

Rules:
- Dependencies are ONLY between sibling subtasks (same level).
- A subtask can only depend on earlier siblings (no circular dependencies).
- Subtask IDs are simple integers starting from 1: "1", "2", "3", ...
- Each decomposition should produce 3-7 subtasks. Prefer fewer, coarser tasks over many fine-grained ones.
- Task descriptions should be specific and actionable: state clearly what output is expected.
- Do NOT create "write the paper" or "compile final report" tasks — that is the Write stage's job.
- Tasks CAN involve literature search, data analysis, code experiments — the Execute stage has tools for these.
- MAXIMIZE PARALLELISM: Only add a dependency when a task truly CANNOT start without the other's output. Independent tasks MUST have empty dependencies so they can run in parallel. Do NOT chain tasks sequentially unless there is a real data dependency.

Respond with ONLY a JSON object (no markdown fencing, no extra text):

If atomic:
{"is_atomic": true}

If not atomic (note: tasks 1,2,3 are independent and parallel; only task 4 depends on 1 and 2):
{"is_atomic": false, "subtasks": [{"id": "1", "description": "...", "dependencies": []}, {"id": "2", "description": "...", "dependencies": []}, {"id": "3", "description": "...", "dependencies": []}, {"id": "4", "description": "...", "dependencies": ["1", "2"]}]}"""


def _build_user_prompt(task: Task, context: str) -> str:
    parts = [f"Research idea context:\n{context}\n"]
    if task.id == "0":
        parts.append("Decompose this research idea into major tasks.")
    else:
        parts.append(f"Task [{task.id}]: {task.description}")
        parts.append("Judge whether this task is atomic. If not, decompose it.")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# PlanStage
# ---------------------------------------------------------------------------

class PlanStage(BaseStage):
    """Recursively decomposes a research idea into atomic tasks with a dependency DAG.
    Same-level tasks are processed in parallel batches.
    """

    def __init__(self, name: str = "plan", max_depth: int = 3, **kwargs):
        super().__init__(name=name, **kwargs)
        self.max_depth = max_depth
        self._tasks: dict[str, Task] = {}
        self._pending: list[str] = []
        self._context: str = ""

    def load_input(self) -> str:
        if self.llm_client and self.llm_client.has_broadcast:
            return "Use read_refined_idea tool to get the research context, then decompose it into tasks."
        return self.db.get_refined_idea()

    async def run(self) -> str:
        """Override: batch-parallel decomposition loop."""
        self._run_id += 1
        my_run_id = self._run_id

        self._pause_event.set()
        self.state = StageState.RUNNING
        self._emit("state", self.state.value)
        self.output = ""

        try:
            input_text = self.load_input()
            self._context = input_text
            root = Task(id="0", description=input_text)
            self._tasks["0"] = root
            self._pending = ["0"]

            while self._pending:
                await self._pause_event.wait()
                if self._is_stale(my_run_id):
                    return self.output

                # Take current batch
                batch = list(self._pending)
                self._pending.clear()

                # Process all in parallel
                coros = [self._process_task(tid, my_run_id) for tid in batch]
                await asyncio.gather(*coros)

                if self._is_stale(my_run_id):
                    return self.output

                # Push updated tree to frontend
                self._emit("tree", self._serialize_tree())

            self.output = self._finalize_output()
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

    def _task_depth(self, task_id: str) -> int:
        """Depth of a task: '0'→0, '1'→1, '1_2'→2, '1_2_3'→3."""
        if task_id == "0":
            return 0
        return len(task_id.split("_"))

    async def _process_task(self, task_id: str, my_run_id: int):
        """Process a single task: call LLM, parse result, update tree."""
        task = self._tasks[task_id]

        # Depth limit: auto-mark as atomic
        if self._task_depth(task_id) >= self.max_depth:
            task.is_atomic = True
            return

        client = self.llm_client

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(task, self._context)},
        ]

        call_id = "Decompose" if task_id == "0" else f"Judge {task_id}"
        self._emit("chunk", {"text": call_id, "call_id": call_id, "label": True})

        response = ""
        async for chunk in client.stream(messages):
            await self._pause_event.wait()
            if self._is_stale(my_run_id):
                return
            response += chunk
            self._emit("chunk", {"text": chunk, "call_id": call_id})

        data = _parse_json(response)

        if data.get("is_atomic", True):
            subtasks = data.get("subtasks", [])
            if not subtasks or not all("id" in st and "description" in st for st in subtasks):
                task.is_atomic = True
                return

        task.is_atomic = False
        for st in data["subtasks"]:
            child_id = st["id"] if task_id == "0" else f"{task_id}_{st['id']}"
            child_deps = [
                d if task_id == "0" else f"{task_id}_{d}"
                for d in st.get("dependencies", [])
            ]
            child = Task(
                id=child_id,
                description=st["description"],
                dependencies=child_deps,
            )
            self._tasks[child_id] = child
            task.children.append(child_id)
            self._pending.append(child_id)

    def _finalize_output(self) -> str:
        """Resolve dependencies, save to DB, return flat atomic task list as JSON."""
        atomic_tasks = {
            tid: t for tid, t in self._tasks.items()
            if t.is_atomic
        }
        resolved = _resolve_dependencies(self._tasks, atomic_tasks)
        output = [
            {
                "id": tid,
                "description": atomic_tasks[tid].description,
                "dependencies": deps,
            }
            for tid, deps in resolved.items()
        ]
        json_str = json.dumps(output, indent=2, ensure_ascii=False)
        if self.db:
            self.db.save_plan(json_str, self._serialize_tree())
        return json_str

    def get_artifacts(self) -> dict | None:
        return self._serialize_tree()

    def retry(self):
        super().retry()
        self._tasks.clear()
        self._pending.clear()
        self._context = ""

    def _serialize_tree(self) -> dict:
        """Serialize task tree from root for frontend rendering."""
        def build_node(task_id: str) -> dict | None:
            task = self._tasks.get(task_id)
            if not task:
                return None
            return {
                "id": task.id,
                "description": task.description,
                "dependencies": task.dependencies,
                "is_atomic": task.is_atomic,
                "children": [build_node(cid) for cid in task.children],
            }
        return build_node("0") or {}


# ---------------------------------------------------------------------------
# Dependency resolution: inherit + expand
# ---------------------------------------------------------------------------

def _resolve_dependencies(
    all_tasks: dict[str, Task],
    atomic_tasks: dict[str, Task],
) -> dict[str, list[str]]:
    """Two-step dependency resolution:
    1. Inherit: walk up ancestor chain, collect all ancestor dependencies
    2. Expand: replace non-atomic deps with their atomic descendants
    """
    resolved: dict[str, list[str]] = {}

    for tid in atomic_tasks:
        collected: set[str] = set()
        for ancestor_id in _ancestor_chain(tid):
            ancestor = all_tasks.get(ancestor_id)
            if ancestor:
                collected.update(ancestor.dependencies)
        collected.update(all_tasks[tid].dependencies)

        expanded: set[str] = set()
        for dep_id in collected:
            if dep_id in atomic_tasks:
                expanded.add(dep_id)
            else:
                expanded.update(_get_atomic_descendants(all_tasks, dep_id, atomic_tasks))

        expanded.discard(tid)
        resolved[tid] = sorted(expanded)

    return resolved


def _ancestor_chain(task_id: str) -> list[str]:
    """Return ancestor IDs from immediate parent up to root.
    '2_1_3' -> ['2_1', '2', '0']
    """
    parts = task_id.split("_")
    ancestors = []
    for i in range(len(parts) - 1, 0, -1):
        ancestors.append("_".join(parts[:i]))
    ancestors.append("0")
    return ancestors


def _get_atomic_descendants(
    all_tasks: dict[str, Task],
    task_id: str,
    atomic_tasks: dict[str, Task],
) -> set[str]:
    """Recursively find all atomic descendants of a task."""
    result: set[str] = set()
    task = all_tasks.get(task_id)
    if not task:
        return result
    if task_id in atomic_tasks:
        result.add(task_id)
        return result
    for child_id in task.children:
        result.update(_get_atomic_descendants(all_tasks, child_id, atomic_tasks))
    return result


# ---------------------------------------------------------------------------
# JSON parsing helper
# ---------------------------------------------------------------------------

def _parse_json(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown fencing."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    return {"is_atomic": True}
