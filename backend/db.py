"""File-based research database.

Each research session gets a unique folder under results/.
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime
import json
import re
import time


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _read_json(path: Path, default=None):
    text = _read(path)
    if not text:
        return default if default is not None else {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return default if default is not None else {}


def _write_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


class ResearchDB:
    """Manages a research session's file storage."""

    def __init__(self, base_dir: str = "results"):
        self._base = Path(base_dir)
        self._root: Path | None = None
        self.research_id: str = ""
        self.current_task_id: str | None = None

    def create_session(self, idea: str = "") -> str:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        slug = re.sub(r"[^a-z0-9\s]", "", idea.lower().strip()).split()[:5]
        slug_str = "-".join(slug) if slug else ""
        self.research_id = f"{timestamp}-{slug_str}" if slug_str else timestamp
        self._root = self._base / self.research_id
        self._root.mkdir(parents=True, exist_ok=True)
        (self._root / "tasks").mkdir(exist_ok=True)
        return self.research_id

    def _ensure_root(self):
        if not self._root:
            raise RuntimeError("No active research session. Call create_session() first.")

    # --- Write ---

    def save_idea(self, text: str):
        self._ensure_root()
        (self._root / "idea.md").write_text(text, encoding="utf-8")

    def save_refined_idea(self, text: str):
        self._ensure_root()
        (self._root / "refined_idea.md").write_text(text, encoding="utf-8")

    def save_plan(self, tree: dict, flat_tasks: list[dict] | None = None):
        """Save tree (source of truth) and derive/update flat task list.

        If flat_tasks is provided, it replaces the list entirely (first decompose).
        Otherwise the existing list is kept (tree-only update during decompose progress).
        """
        self._ensure_root()
        _write_json(self._root / "plan_tree.json", tree)
        if flat_tasks is not None:
            _write_json(self._root / "plan_list.json", flat_tasks)

    def save_paper(self, text: str):
        self._ensure_root()
        (self._root / "paper.md").write_text(text, encoding="utf-8")

    def save_task_output(self, task_id: str, text: str):
        self._ensure_root()
        safe_id = task_id.replace("/", "_")
        (self._root / "tasks" / f"{safe_id}.md").write_text(text, encoding="utf-8")

    def save_calibration(self, text: str):
        self._ensure_root()
        (self._root / "calibration.md").write_text(text, encoding="utf-8")

    def save_strategy(self, text: str):
        self._ensure_root()
        (self._root / "strategy.md").write_text(text, encoding="utf-8")

    def save_score_direction(self, minimize: bool):
        self._ensure_root()
        meta = _read_json(self._root / "meta.json")
        meta["score_direction"] = "minimize" if minimize else "maximize"
        _write_json(self._root / "meta.json", meta)

    def save_evaluation(self, data: dict, iteration: int):
        self._ensure_root()
        eval_dir = self._root / "evaluations"
        eval_dir.mkdir(exist_ok=True)
        _write_json(eval_dir / f"eval_v{iteration}.json", data)
        # Also save readable markdown for frontend display
        parts = []
        if data.get("feedback"):
            parts.append(f"## Feedback\n\n{data['feedback']}")
        if data.get("suggestions"):
            items = "\n".join(f"- {s}" for s in data["suggestions"])
            parts.append(f"## Suggestions\n\n{items}")
        if data.get("score") is not None:
            parts.append(f"## Score\n\n{data['score']}")
        if data.get("satisfied"):
            parts.append("*Pipeline satisfied — no further iterations needed.*")
        if parts:
            (self._root / "evaluation.md").write_text(
                "\n\n".join(parts), encoding="utf-8"
            )

    def append_tasks(self, tasks: list[dict]):
        """Append new atomic tasks to plan_list.json (derived cache)."""
        self._ensure_root()
        plan_path = self._root / "plan_list.json"
        existing = _read_json(plan_path, default=[])
        existing.extend(tasks)
        _write_json(plan_path, existing)

    def save_script(self, code: str, language: str = "python") -> tuple[Path, str]:
        self._ensure_root()
        task_dir = self.get_artifacts_dir(self.current_task_id)
        ext = ".py" if language == "python" else ".r"
        existing = sorted(task_dir.glob(f"*{ext}"))
        seq = len(existing) + 1
        name = f"{seq:03d}{ext}"
        path = task_dir / name
        path.write_text(code, encoding="utf-8")
        return path, name

    def save_reproduce_files(self, dockerfile: str, run_sh: str, compose: str):
        self._ensure_root()
        reproduce_dir = self._root / "reproduce"
        reproduce_dir.mkdir(exist_ok=True)
        (reproduce_dir / "Dockerfile").write_text(dockerfile, encoding="utf-8")
        (reproduce_dir / "run.sh").write_text(run_sh, encoding="utf-8")
        (reproduce_dir / "docker-compose.yml").write_text(compose, encoding="utf-8")

    def append_log(self, stage: str, call_id: str, text: str, level: int,
                   task_id: str | None = None, label: bool = False):
        """Append a streaming chunk to log.jsonl."""
        self._ensure_root()
        entry = {"ts": time.time(), "stage": stage, "call_id": call_id,
                 "text": text, "level": level}
        if task_id:
            entry["task_id"] = task_id
        if label:
            entry["label"] = True
        with open(self._root / "log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def append_execution_log(self, task_id: str, script: str,
                             language: str = "python", requirements: str = ""):
        """Append a Docker code execution record to execution_log.jsonl."""
        self._ensure_root()
        entry = {"ts": time.time(), "task_id": task_id, "script": script,
                 "language": language, "requirements": requirements}
        with open(self._root / "execution_log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def update_task_status(self, task_id: str, status: str, summary: str = ""):
        """Update a task's status (and optional summary) in plan_list.json."""
        self._ensure_root()
        plan_path = self._root / "plan_list.json"
        tasks = _read_json(plan_path, default=[])
        for t in tasks:
            if t["id"] == task_id:
                t["status"] = status
                if summary:
                    t["summary"] = summary
                break
        _write_json(plan_path, tasks)

    def bulk_update_tasks(self, updates: dict[str, dict]):
        """Batch-update fields on multiple tasks. updates = {task_id: {field: value, ...}}."""
        self._ensure_root()
        plan_path = self._root / "plan_list.json"
        tasks = _read_json(plan_path, default=[])
        for t in tasks:
            fields = updates.get(t["id"])
            if fields:
                t.update(fields)
        _write_json(plan_path, tasks)

    def update_meta(self, **kwargs):
        self._ensure_root()
        meta = _read_json(self._root / "meta.json")
        meta.update(kwargs)
        _write_json(self._root / "meta.json", meta)

    # --- Read ---

    def get_idea(self) -> str:
        self._ensure_root()
        return _read(self._root / "idea.md")

    def get_refined_idea(self) -> str:
        self._ensure_root()
        return _read(self._root / "refined_idea.md")

    def get_calibration(self) -> str:
        self._ensure_root()
        return _read(self._root / "calibration.md")

    def get_strategy(self) -> str:
        self._ensure_root()
        return _read(self._root / "strategy.md")

    def get_plan_list(self) -> list[dict]:
        self._ensure_root()
        return _read_json(self._root / "plan_list.json", default=[])

    def get_plan_tree(self) -> dict:
        self._ensure_root()
        return _read_json(self._root / "plan_tree.json", default={})

    def get_log(self, offset: int = 0, stage: str = "") -> tuple[list[dict], int]:
        self._ensure_root()
        path = self._root / "log.jsonl"
        if not path.exists():
            return [], 0
        lines = path.read_text(encoding="utf-8").splitlines()
        entries = []
        for line in lines[offset:]:
            try:
                entry = json.loads(line)
                if stage and entry.get("stage") != stage:
                    continue
                entries.append(entry)
            except json.JSONDecodeError:
                continue
        return entries, len(lines)

    def get_execution_log(self) -> list[dict]:
        self._ensure_root()
        path = self._root / "execution_log.jsonl"
        if not path.exists():
            return []
        entries = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries

    def get_meta(self) -> dict:
        self._ensure_root()
        return _read_json(self._root / "meta.json")

    def get_document(self, name: str) -> str:
        self._ensure_root()
        return _read(self._root / f"{name}.md")

    def get_task_output(self, task_id: str) -> str:
        self._ensure_root()
        safe_id = task_id.replace("/", "_")
        return _read(self._root / "tasks" / f"{safe_id}.md")

    def get_score_minimize(self) -> bool:
        self._ensure_root()
        meta = _read_json(self._root / "meta.json")
        return meta.get("score_direction", "minimize") == "minimize"

    def get_iteration(self) -> int:
        self._ensure_root()
        eval_dir = self._root / "evaluations"
        if not eval_dir.exists():
            return 0
        return len(list(eval_dir.glob("eval_v*.json")))

    def get_latest_score(self) -> float | None:
        self._ensure_root()
        eval_dir = self._root / "evaluations"
        if not eval_dir.exists():
            return None
        files = sorted(eval_dir.glob("eval_v*.json"))
        if not files:
            return None
        data = _read_json(files[-1])
        score = data.get("score")
        return float(score) if score is not None else None

    def load_evaluations(self) -> list[dict]:
        """Load all previous evaluation JSONs, sorted by iteration."""
        self._ensure_root()
        eval_dir = self._root / "evaluations"
        if not eval_dir.exists():
            return []
        results = []
        for f in sorted(eval_dir.glob("eval_v*.json")):
            data = _read_json(f)
            if data:
                results.append(data)
        return results

    def list_completed_tasks(self) -> list[dict]:
        self._ensure_root()
        tasks_dir = self._root / "tasks"
        if not tasks_dir.exists():
            return []
        return [{"id": f.stem, "size_bytes": f.stat().st_size}
                for f in sorted(tasks_dir.glob("*.md"))]

    def get_tasks_dir(self) -> Path:
        self._ensure_root()
        return self._root / "tasks"

    def get_artifacts_dir(self, task_id: str | None = None) -> Path:
        self._ensure_root()
        artifacts = self._root / "artifacts"
        artifacts.mkdir(exist_ok=True)
        if task_id:
            safe_id = task_id.replace("/", "_")
            task_dir = artifacts / safe_id
            task_dir.mkdir(exist_ok=True)
            return task_dir
        return artifacts

    def clear_tasks(self):
        self._ensure_root()
        tasks_dir = self._root / "tasks"
        if tasks_dir.exists():
            for f in tasks_dir.glob("*.md"):
                f.unlink()

    def clear_plan(self):
        self._ensure_root()
        for name in ("plan_list.json", "plan_tree.json"):
            path = self._root / name
            if path.exists():
                path.unlink()
        eval_dir = self._root / "evaluations"
        if eval_dir.exists():
            for f in eval_dir.glob("*.json"):
                f.unlink()

    def promote_best_score(self):
        if not self.current_task_id:
            return
        task_dir = self.get_artifacts_dir(self.current_task_id)
        task_score_path = task_dir / "best_score.json"
        task_data = _read_json(task_score_path)
        if not task_data:
            return
        try:
            task_score = float(task_data.get("score", 0))
        except (ValueError, TypeError):
            return
        artifacts_root = self.get_artifacts_dir()
        task_content = task_score_path.read_text(encoding="utf-8")
        minimize = self.get_score_minimize()
        (artifacts_root / "latest_score.json").write_text(task_content, encoding="utf-8")
        best_data = _read_json(artifacts_root / "best_score.json")
        if best_data:
            try:
                best_score = float(best_data.get("score", 0))
                is_better = task_score < best_score if minimize else task_score > best_score
                if not is_better:
                    return
            except (ValueError, TypeError):
                pass
        (artifacts_root / "best_score.json").write_text(task_content, encoding="utf-8")
