"""Write stage: generates a research paper section by section."""

from __future__ import annotations

import json
import re

from backend.db import ResearchDB
from backend.pipeline.stage import BaseStage

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_AUTO = "This is a fully automated pipeline. No human is in the loop. Do NOT ask questions or request input. Make all decisions autonomously.\n\n"

_OUTLINE_SYSTEM = _AUTO + """\
You are a research paper architect. Given a list of completed research tasks and their IDs, design a paper outline.

For each section, specify which task IDs provide the relevant content. A task may appear in multiple sections if relevant.

Respond with ONLY a JSON object:
{"sections": [{"title": "Abstract", "task_ids": ["1_1", "1_2"]}, {"title": "Introduction", "task_ids": ["1_3"]}, ...]}

Include standard academic sections appropriate for the research topic. Common sections:
Abstract, Introduction, Related Work / Literature Review, Methodology / Theoretical Framework, Analysis / Results, Discussion, Conclusion.
Adapt section titles and structure to best fit the specific research."""

_SECTION_SYSTEM = _AUTO + """\
You are a research paper writer. Write one section of a research paper.

Rules:
- Base your writing STRICTLY on the provided task outputs. Do not introduce claims or findings not supported by the completed research tasks.
- Use academic tone and precise language
- Provide proper in-text citations where the task outputs reference specific works
- Ensure logical flow within the section
- Be substantive — each section should make a clear contribution to the paper's argument

Output in markdown."""

_POLISH_SYSTEM = _AUTO + """\
You are a research paper editor. Given a complete draft assembled from individual sections, produce a polished final paper.

Your editing tasks:
- Improve transitions between sections for narrative coherence
- Ensure consistent terminology, notation, and style throughout
- Strengthen the overall argument and logical flow
- Remove redundancies across sections
- Add a proper title at the top if missing
- Ensure the abstract accurately reflects the paper's content
- Do NOT add new content or findings — only improve what exists

Output the complete polished paper in markdown."""


def _build_outline_prompt(tasks: list[dict], refined_idea: str) -> list[dict]:
    task_list = "\n".join(f"- [{t['id']}] {t['description']}" for t in tasks)
    return [
        {"role": "system", "content": _OUTLINE_SYSTEM},
        {"role": "user", "content": (
            f"Research idea:\n{refined_idea}\n\n"
            f"Completed tasks:\n{task_list}"
        )},
    ]


def _build_section_prompt(title: str, task_outputs: dict[str, str], outline_titles: list[str]) -> list[dict]:
    context_parts = []
    for tid, output in task_outputs.items():
        context_parts.append(f"### Task [{tid}] output:\n{output}")
    context = "\n\n".join(context_parts) if context_parts else "(No specific task outputs for this section)"

    return [
        {"role": "system", "content": _SECTION_SYSTEM},
        {"role": "user", "content": (
            f"Paper outline: {', '.join(outline_titles)}\n\n"
            f"Write the section: **{title}**\n\n"
            f"Relevant research outputs:\n{context}"
        )},
    ]


def _build_polish_prompt(draft: str) -> list[dict]:
    return [
        {"role": "system", "content": _POLISH_SYSTEM},
        {"role": "user", "content": draft},
    ]


# ---------------------------------------------------------------------------
# WriteStage
# ---------------------------------------------------------------------------

class WriteStage(BaseStage):
    """Generates a research paper: outline → section-by-section → polish."""

    def __init__(self, name: str = "write", **kwargs):
        super().__init__(name=name, max_rounds=999, **kwargs)
        self._outline: list[dict] = []  # [{"title": ..., "task_ids": [...]}, ...]
        self._sections: dict[str, str] = {}  # title -> content
        self._phase = "outline"  # outline | sections | polish
        self._section_index = 0
        self._tasks_meta: list[dict] = []  # task list from plan
        self._refined_idea: str = ""

    def get_round_label(self, round_index: int) -> str:
        if self._phase == "outline":
            return "Outline"
        if self._phase == "sections" and self._section_index < len(self._outline):
            return f"Write: {self._outline[self._section_index]['title']}"
        if self._phase == "polish":
            return "Polish"
        return ""

    def load_input(self) -> str:
        if self.llm_client and self.llm_client.has_broadcast:
            return (
                "Use list_tasks and read_task_output tools to read completed research outputs. "
                "Use read_refined_idea for context and read_plan_tree for structure. "
                "Write the complete research paper."
            )
        return ""  # Gemini/Mock: build_messages reads DB directly

    def build_messages(self, input_text: str, round_index: int) -> list[dict]:
        if round_index == 0:
            self._tasks_meta = self._load_tasks_from_db()
            self._refined_idea = self.db.get_refined_idea() if self.db else ""
            self._phase = "outline"
            return _build_outline_prompt(self._tasks_meta, self._refined_idea)

        if self._phase == "sections":
            section = self._outline[self._section_index]
            task_outputs = {}
            for tid in section.get("task_ids", []):
                output = self.db.get_task_output(tid) if self.db else ""
                if output:
                    task_outputs[tid] = output
            outline_titles = [s["title"] for s in self._outline]
            return _build_section_prompt(section["title"], task_outputs, outline_titles)

        if self._phase == "polish":
            draft = self._assemble_draft()
            return _build_polish_prompt(draft)

        return []

    def process_response(self, response: str, round_index: int):
        if self._phase == "outline":
            self._outline = self._parse_outline(response)
            self._phase = "sections"
            self._section_index = 0

        elif self._phase == "sections":
            title = self._outline[self._section_index]["title"]
            self._sections[title] = response
            self._section_index += 1
            if self._section_index >= len(self._outline):
                self._phase = "polish"

        elif self._phase == "polish":
            self._phase = "done"

    def is_complete(self, response: str, round_index: int) -> bool:
        return self._phase == "done"

    def finalize(self) -> str:
        result = self.rounds[-1]["content"] if self.rounds else self._assemble_draft()
        if self.db:
            self.db.save_paper(result)
        return result

    def retry(self):
        super().retry()
        self._outline.clear()
        self._sections.clear()
        self._phase = "outline"
        self._section_index = 0
        self._tasks_meta.clear()
        self._refined_idea = ""

    def _assemble_draft(self) -> str:
        parts = []
        for section in self._outline:
            title = section["title"]
            content = self._sections.get(title, "")
            parts.append(f"# {title}\n\n{content}")
        return "\n\n---\n\n".join(parts)

    def _load_tasks_from_db(self) -> list[dict]:
        """Load task list from plan.json in DB."""
        if not self.db:
            return []
        plan_json = self.db.get_plan_json()
        if not plan_json:
            return []
        try:
            tasks = json.loads(plan_json)
            return [{"id": t["id"], "description": t.get("description", t["id"])} for t in tasks]
        except (json.JSONDecodeError, KeyError):
            return []

    def _parse_outline(self, response: str) -> list[dict]:
        """Parse outline JSON from LLM response."""
        text = response.strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1).strip())
                except json.JSONDecodeError:
                    data = {}
            else:
                data = {}

        sections = data.get("sections", [])
        if not sections:
            # Fallback: default academic structure
            all_ids = [t["id"] for t in self._tasks_meta]
            sections = [
                {"title": "Abstract", "task_ids": all_ids},
                {"title": "Introduction", "task_ids": all_ids},
                {"title": "Methodology", "task_ids": all_ids},
                {"title": "Results", "task_ids": all_ids},
                {"title": "Conclusion", "task_ids": all_ids},
            ]
        return sections
