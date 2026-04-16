"""File-based research database.

Each research session gets a unique folder under results/.
"""

from __future__ import annotations

import contextvars
from pathlib import Path
from datetime import datetime
import json
import re
import threading
import time

_current_task_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_task_id", default=None,
)


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
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


class ResearchDB:
    """Manages a research session's file storage."""

    def __init__(self, base_dir: str = "results"):
        self._base = Path(base_dir)
        self._root: Path | None = None
        self.research_id: str = ""
        self._meta_lock = threading.Lock()

    @property
    def current_task_id(self) -> str | None:
        return _current_task_id_var.get()

    @current_task_id.setter
    def current_task_id(self, value: str | None):
        _current_task_id_var.set(value)

    def create_session(self, idea: str = "") -> str:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        slug = re.sub(r"[^a-z0-9\s]", "", idea.lower().strip()).split()[:5]
        slug_str = "-".join(slug) if slug else ""
        self.research_id = f"{timestamp}-{slug_str}" if slug_str else timestamp
        self._root = self._base / self.research_id
        self._root.mkdir(parents=True, exist_ok=True)
        (self._root / "tasks").mkdir(exist_ok=True)
        return self.research_id

    def attach_session(self, research_id: str):
        root = self._base / research_id
        if not root.exists() or not root.is_dir():
            raise RuntimeError(f"Research session '{research_id}' not found.")
        self.research_id = research_id
        self._root = root

    def _ensure_root(self):
        if not self._root:
            raise RuntimeError("No active research session. Call create_session() first.")

    @property
    def session_dir(self) -> Path:
        self._ensure_root()
        return self._root

    # --- Internal helpers ---

    def _get_text(self, subpath: str) -> str:
        self._ensure_root()
        return _read(self._root / subpath)

    def _get_json(self, subpath: str, default=None):
        self._ensure_root()
        return _read_json(self._root / subpath, default=default)

    def _save_text(self, subpath: str, text: str):
        self._ensure_root()
        path = self._root / subpath
        path.parent.mkdir(exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _save_json(self, subpath: str, data):
        self._ensure_root()
        path = self._root / subpath
        path.parent.mkdir(exist_ok=True)
        _write_json(path, data)

    # --- Write ---

    def save_idea(self, text: str):
        self._save_text("idea.md", text)

    def save_refined_idea(self, text: str):
        self._save_text("refined_idea.md", text)

    def save_plan(self, tree: dict, flat_tasks: list[dict] | None = None):
        self._save_json("plan_tree.json", tree)
        if flat_tasks is not None:
            self._save_json("plan_list.json", flat_tasks)

    def save_paper(self, text: str):
        self._save_text("paper.md", text)

    def save_paper_final(self, text: str):
        self._save_text("paper_final.md", text)

    def save_task_output(self, task_id: str, text: str):
        safe_id = task_id.replace("/", "_")
        self._save_text(f"tasks/{safe_id}.md", text)

    def save_calibration(self, text: str):
        self._save_text("calibration.md", text)

    def save_strategy(self, text: str, iteration: int = 0):
        self._save_text(f"strategy/round_{iteration}.md", text)

    def save_score_direction(self, minimize: bool):
        self._ensure_root()
        with self._meta_lock:
            meta = _read_json(self._root / "meta.json")
            meta["score_direction"] = "minimize" if minimize else "maximize"
            _write_json(self._root / "meta.json", meta)

    def save_evaluation(self, data: dict, iteration: int):
        self._save_json(f"evaluations/round_{iteration}.json", data)
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
            self._save_text(f"evaluations/round_{iteration}.md", "\n\n".join(parts))

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
        self._save_text("reproduce/Dockerfile", dockerfile)
        self._save_text("reproduce/run.sh", run_sh)
        self._save_text("reproduce/docker-compose.yml", compose)

    def save_results_summary(self, data: dict, markdown: str = ""):
        self._save_json("results_summary.json", data)
        if markdown:
            self._save_text("results_summary.md", markdown)

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

    def update_meta(self, **kwargs):
        self._ensure_root()
        with self._meta_lock:
            meta = _read_json(self._root / "meta.json")
            meta.update(kwargs)
            _write_json(self._root / "meta.json", meta)

    # --- Read ---

    def get_idea(self) -> str:
        return self._get_text("idea.md")

    def get_refined_idea(self) -> str:
        return self._get_text("refined_idea.md")

    def get_calibration(self) -> str:
        return self._get_text("calibration.md")

    def get_strategy(self) -> str:
        """Read the latest strategy version."""
        self._ensure_root()
        strategy_dir = self._root / "strategy"
        if not strategy_dir.exists():
            return ""
        versions = sorted(strategy_dir.glob("round_*.md"))
        return _read(versions[-1]) if versions else ""

    def list_documents(self, prefix: str) -> list[str]:
        """List all versioned documents in a subdirectory (e.g. 'strategy' → ['strategy/v0', 'strategy/v1'])."""
        self._ensure_root()
        subdir = self._root / prefix
        if not subdir.is_dir():
            return []
        return [f"{prefix}/{f.stem}" for f in sorted(subdir.glob("round_*.md"))]

    def get_plan_list(self) -> list[dict]:
        return self._get_json("plan_list.json", default=[])

    def get_plan_tree(self) -> dict:
        return self._get_json("plan_tree.json", default={})

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
        return self._get_json("meta.json")

    def get_document(self, name: str) -> str:
        return self._get_text(f"{name}.md")

    def get_task_output(self, task_id: str) -> str:
        safe_id = task_id.replace("/", "_")
        return self._get_text(f"tasks/{safe_id}.md")

    def get_results_summary(self) -> str:
        data = self._get_json("results_summary.json", default={})
        return json.dumps(data, indent=2, ensure_ascii=False) if data else ""

    def get_results_summary_json(self) -> dict:
        return self._get_json("results_summary.json", default={})

    def get_score_minimize(self) -> bool:
        return self._get_json("meta.json").get("score_direction", "minimize") == "minimize"

    def get_strategy_for(self, iteration: int) -> str:
        return self._get_text(f"strategy/round_{iteration}.md")

    def get_evaluation(self, iteration: int) -> dict:
        return self._get_json(f"evaluations/round_{iteration}.json", default={})

    def get_iteration(self) -> int:
        self._ensure_root()
        eval_dir = self._root / "evaluations"
        if not eval_dir.exists():
            return 0
        count = 0
        for f in sorted(eval_dir.glob("round_*.json")):
            if _read_json(f):
                count += 1
        return count

    def load_evaluations(self) -> list[dict]:
        """Load all previous evaluation JSONs, sorted by iteration."""
        self._ensure_root()
        eval_dir = self._root / "evaluations"
        if not eval_dir.exists():
            return []
        results = []
        for f in sorted(eval_dir.glob("round_*.json")):
            data = _read_json(f)
            if data:
                results.append(data)
        return results

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

    # --- Round-based read/write (used by TeamStage iterations) ---

    def load_round_md(self, dirname: str, iteration: int) -> str:
        return self._get_text(f"{dirname}/round_{iteration}.md")

    def load_round_json(self, dirname: str, iteration: int) -> dict | None:
        """Returns None (not {}) when file is missing, so callers can distinguish."""
        self._ensure_root()
        path = self._root / dirname / f"round_{iteration}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            return None

    def save_round_md(self, dirname: str, text: str, iteration: int):
        self._save_text(f"{dirname}/round_{iteration}.md", text)

    def save_round_json(self, dirname: str, data: dict, iteration: int):
        self._save_json(f"{dirname}/round_{iteration}.json", data)

    def clear_stage_outputs(self, stage_name: str):
        import shutil
        self._ensure_root()
        stage_dirs = {
            "refine": ("proposals", "critiques"),
            "research": ("tasks", "evaluations", "strategy", "artifacts", "reproduce"),
            "write": ("drafts", "reviews"),
            "polish": (),
        }
        stage_files = {
            "refine": ("refined_idea.md",),
            "research": (
                "calibration.md", "plan_tree.json", "plan_list.json",
                "results_summary.json", "results_summary.md", "execution_log.jsonl",
            ),
            "write": ("paper.md",),
            "polish": ("paper_final.md",),
        }
        for dirname in stage_dirs.get(stage_name, ()):
            path = self._root / dirname
            if path.exists():
                shutil.rmtree(path)
        for filename in stage_files.get(stage_name, ()):
            path = self._root / filename
            if path.exists():
                path.unlink()
        # Clear stage-specific log entries
        log_path = self._root / "log.jsonl"
        if log_path.exists():
            kept_lines = []
            for line in log_path.read_text(encoding="utf-8").splitlines():
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    kept_lines.append(line)
                    continue
                if entry.get("stage") == stage_name:
                    continue
                kept_lines.append(line)
            text = ("\n".join(kept_lines) + "\n") if kept_lines else ""
            log_path.write_text(text, encoding="utf-8")

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
