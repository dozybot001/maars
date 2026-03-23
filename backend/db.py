"""File-based research database.

Each research session gets a unique folder:
    research/{research_id}/
    ├── idea.md
    ├── refined_idea.md
    ├── plan.json
    ├── plan_tree.json
    └── tasks/
        ├── 1_1.md
        ├── 1_2.md
        └── ...
"""

from pathlib import Path
from datetime import datetime
import json
import re


class ResearchDB:
    """Manages a research session's file storage."""

    def __init__(self, base_dir: str = "research"):
        self._base = Path(base_dir)
        self._root: Path | None = None
        self.research_id: str = ""

    def create_session(self, idea: str = "") -> str:
        """Create a new research folder. Returns the research ID.
        Format: YYYYMMDD-HHMMSS-short-idea-slug
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        slug = self._slugify(idea)
        self.research_id = f"{timestamp}-{slug}" if slug else timestamp
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

    def save_plan(self, plan_json: str, plan_tree: dict | None = None):
        self._ensure_root()
        (self._root / "plan.json").write_text(plan_json, encoding="utf-8")
        if plan_tree:
            (self._root / "plan_tree.json").write_text(
                json.dumps(plan_tree, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    def save_paper(self, text: str):
        self._ensure_root()
        (self._root / "paper.md").write_text(text, encoding="utf-8")

    def save_task_output(self, task_id: str, text: str):
        self._ensure_root()
        safe_id = task_id.replace("/", "_")
        (self._root / "tasks" / f"{safe_id}.md").write_text(text, encoding="utf-8")

    # --- Read ---

    def get_task_output(self, task_id: str) -> str:
        self._ensure_root()
        safe_id = task_id.replace("/", "_")
        path = self._root / "tasks" / f"{safe_id}.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    @staticmethod
    def _slugify(text: str, max_words: int = 5) -> str:
        """Convert text to a short filesystem-safe slug."""
        text = text.lower().strip()
        text = re.sub(r"[^a-z0-9\s]", "", text)
        words = text.split()[:max_words]
        return "-".join(words) if words else ""

    def get_refined_idea(self) -> str:
        self._ensure_root()
        path = self._root / "refined_idea.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""
