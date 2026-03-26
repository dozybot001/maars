"""Write stage: generates a research paper section by section.

Pipeline: outline → sections → structure → style → format → done
Outputs both paper.md (markdown) and paper.tex (LaTeX IEEE format).
"""

from __future__ import annotations

import json
import re

from backend.db import ResearchDB
from backend.pipeline.stage import BaseStage
from backend.utils import parse_json_fenced

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_AUTO = "This is a fully automated pipeline. No human is in the loop. Do NOT ask questions or request input. Make all decisions autonomously. 全文使用中文撰写。\n\n"

_OUTLINE_SYSTEM = _AUTO + """\
You are a research paper architect. Given a list of completed research tasks and their IDs, design a paper outline.

For each section, specify which task IDs provide the relevant content. A task may appear in multiple sections if relevant.

If images are available, allocate EVERY image to exactly ONE section where it is most relevant. Each image must appear in exactly one section's "images" list.

Respond with ONLY a JSON object:
{"sections": [{"title": "Introduction", "task_ids": ["1_1", "1_2"], "images": []}, {"title": "Results", "task_ids": ["1_3"], "images": ["plot.png"]}, ...]}

Design section titles and structure to best fit THIS specific research. Do NOT default to a generic template — let the content dictate the organization."""

_SECTION_SYSTEM = _AUTO + """\
You are a research paper writer. Write one section of a research paper.

Rules:
- Base your writing STRICTLY on the provided task outputs. Do not introduce claims not supported by the research.
- Use academic tone and precise language
- Provide proper in-text citations where the task outputs reference specific works
- If task outputs include experimental results, data, or figures, reference them explicitly (e.g., "As shown in Figure X", "Table Y summarizes...")
- If images are assigned to this section, include them using markdown image syntax: ![descriptive caption](filename)
- Ensure logical flow within the section

Output in markdown."""

_STRUCTURE_SYSTEM = _AUTO + """\
You are a research paper structural reviewer. Your ONLY job is to ensure cross-section consistency and logical coherence.

Check and fix:
- Numbers, statistics, and thresholds must be consistent across all sections (e.g., if Section 3 says "92% accuracy", Section 5 must not say "89%")
- Terminology must be used consistently (same concept must use the same term throughout)
- Claims in the conclusion must be supported by evidence presented in earlier sections
- Logical flow: each section should build on the previous one without contradictions
- No section should repeat content from another section verbatim

Do NOT change writing style, tone, or academic voice. Do NOT add new content or findings.
Output the complete revised paper in markdown."""

_STYLE_SYSTEM = _AUTO + """\
You are a research paper style editor. Your ONLY job is to polish the academic writing quality.

Your tasks:
- Improve transitions between sections for narrative coherence
- Strengthen academic tone and precise language throughout
- Remove redundancies and tighten prose
- Ensure parallel structure in lists and comparisons
- Add a proper title at the top if missing
- Add a References section at the end listing all cited works (compile from in-text citations)

Do NOT change data, numbers, or factual claims. Do NOT alter the paper's structure or add new findings.
Output the complete polished paper in markdown."""

_FORMAT_SYSTEM = _AUTO + """\
You are a research paper format reviewer. Your ONLY job is to ensure the paper follows proper academic formatting conventions.

Check and fix:
- All figures and tables must be numbered sequentially and referenced in the text (e.g., "Figure 1", "Table 2")
- All citations must use a consistent format (e.g., [Author, Year] or numbered [1])
- Section headings must follow a consistent hierarchy (# for main sections, ## for subsections)
- The References section must list all cited works in a consistent bibliographic format
- Image references ![caption](file) must have descriptive captions
- Mathematical notation and symbols must be consistent

Do NOT change content, style, or structure. Only fix formatting issues.
Output the complete formatted paper in markdown."""


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _build_outline_prompt(tasks: list[dict], refined_idea: str, images: list[str]) -> list[dict]:
    task_list = "\n".join(f"- [{t['id']}] {t['description']}" for t in tasks)
    image_section = ""
    if images:
        image_list = ", ".join(images)
        image_section = f"\n\nAvailable images (allocate each to exactly one section):\n{image_list}"
    return [
        {"role": "system", "content": _OUTLINE_SYSTEM},
        {"role": "user", "content": (
            f"Research idea:\n{refined_idea}\n\n"
            f"Completed tasks:\n{task_list}"
            f"{image_section}"
        )},
    ]


def _build_section_prompt(
    title: str, task_outputs: dict[str, str],
    outline_titles: list[str], images: list[str],
) -> list[dict]:
    context_parts = []
    for tid, output in task_outputs.items():
        context_parts.append(f"### Task [{tid}] output:\n{output}")
    context = "\n\n".join(context_parts) if context_parts else "(No specific task outputs for this section)"

    image_note = ""
    if images:
        image_list = ", ".join(images)
        image_note = f"\n\nAssigned images for this section: {image_list}\nInclude each using: ![descriptive caption](filename)"

    return [
        {"role": "system", "content": _SECTION_SYSTEM},
        {"role": "user", "content": (
            f"Paper outline: {', '.join(outline_titles)}\n\n"
            f"Write the section: **{title}**\n\n"
            f"Relevant research outputs:\n{context}"
            f"{image_note}"
        )},
    ]


def _build_structure_prompt(draft: str) -> list[dict]:
    return [
        {"role": "system", "content": _STRUCTURE_SYSTEM},
        {"role": "user", "content": draft},
    ]


def _build_style_prompt(draft: str) -> list[dict]:
    return [
        {"role": "system", "content": _STYLE_SYSTEM},
        {"role": "user", "content": draft},
    ]


def _build_format_prompt(draft: str) -> list[dict]:
    return [
        {"role": "system", "content": _FORMAT_SYSTEM},
        {"role": "user", "content": draft},
    ]


# ---------------------------------------------------------------------------
# Markdown → LaTeX conversion
# ---------------------------------------------------------------------------

_LATEX_PREAMBLE = r"""\documentclass[conference]{IEEEtran}
\usepackage{cite}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{graphicx}
\usepackage{textcomp}
\usepackage{xcolor}
\usepackage{booktabs}
\usepackage{hyperref}
\usepackage{titlesec}

\titleformat{\section}
  {\normalfont\Large\bfseries}
  {\arabic{section}.}
  {1em}
  {}
\titleformat{\subsection}
  {\normalfont\large\bfseries}
  {\arabic{section}.\arabic{subsection}}
  {1em}
  {}
\titleformat{\subsubsection}
  {\normalfont\normalsize\bfseries}
  {\arabic{section}.\arabic{subsection}.\arabic{subsubsection}}
  {1em}
  {}

\begin{document}
"""


def _md_to_latex(md_text: str) -> str:
    """Convert markdown paper to LaTeX with IEEE conference format."""
    lines = md_text.split("\n")
    out: list[str] = [_LATEX_PREAMBLE]

    # Extract title from first H1
    title = "Research Paper"
    for line in lines:
        m = re.match(r"^#\s+(.+)$", line)
        if m:
            title = m.group(1).strip()
            break

    out.append(f"\\title{{{_latex_escape(title)}}}")
    out.append(r"\author{\IEEEauthorblockN{MAARS Research Pipeline}}")
    out.append(r"\maketitle")
    out.append("")

    in_table = False
    table_rows: list[str] = []
    table_alignments: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Skip the title line (already used)
        if re.match(r"^#\s+", stripped) and _latex_escape(stripped.lstrip("# ").strip()) == _latex_escape(title):
            continue

        # Horizontal rules → skip
        if re.match(r"^-{3,}$", stripped):
            continue

        # Table handling
        if "|" in stripped and not in_table:
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if cells:
                in_table = True
                table_rows = [cells]
                table_alignments = []
                continue

        if in_table:
            if "|" in stripped:
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                # Check if this is the alignment row
                if all(re.match(r"^:?-+:?$", c) for c in cells if c):
                    table_alignments = []
                    for c in cells:
                        if c.startswith(":") and c.endswith(":"):
                            table_alignments.append("c")
                        elif c.endswith(":"):
                            table_alignments.append("r")
                        else:
                            table_alignments.append("l")
                    continue
                table_rows.append(cells)
                continue
            else:
                # End of table
                out.append(_render_latex_table(table_rows, table_alignments))
                in_table = False
                table_rows = []

        # Section headings
        m = re.match(r"^(#{2,4})\s+(.+)$", stripped)
        if m:
            level = len(m.group(1))
            heading = m.group(2).strip()
            # Strip leading numbers like "1. " or "1.2 "
            heading = re.sub(r"^\d+(\.\d+)*\.?\s+", "", heading)
            if level == 2:
                out.append(f"\\section{{{_latex_escape(heading)}}}")
            elif level == 3:
                out.append(f"\\subsection{{{_latex_escape(heading)}}}")
            elif level == 4:
                out.append(f"\\subsubsection{{{_latex_escape(heading)}}}")
            continue

        # H1 that isn't the title → treat as section
        m = re.match(r"^#\s+(.+)$", stripped)
        if m:
            heading = re.sub(r"^\d+(\.\d+)*\.?\s+", "", m.group(1).strip())
            out.append(f"\\section{{{_latex_escape(heading)}}}")
            continue

        # Images: ![caption](file)
        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", stripped)
        if m:
            caption = m.group(1)
            filename = m.group(2)
            out.append(r"\begin{figure}[htbp]")
            out.append(r"\centering")
            out.append(f"\\includegraphics[width=\\linewidth]{{{filename}}}")
            out.append(f"\\caption{{{_latex_escape(caption)}}}")
            out.append(r"\end{figure}")
            continue

        # Bold and italic inline
        converted = _convert_inline(stripped)
        out.append(converted)

    # Flush any remaining table
    if in_table and table_rows:
        out.append(_render_latex_table(table_rows, table_alignments))

    out.append("")
    out.append(r"\end{document}")
    return "\n".join(out)


def _latex_escape(text: str) -> str:
    """Escape special LaTeX characters, preserving already-escaped sequences."""
    # Don't escape if it looks like it already contains LaTeX commands
    if "\\" in text:
        return text
    replacements = [
        ("&", r"\&"), ("%", r"\%"), ("$", r"\$"),
        ("#", r"\#"), ("_", r"\_"), ("{", r"\{"),
        ("}", r"\}"), ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def _convert_inline(text: str) -> str:
    """Convert markdown inline formatting to LaTeX."""
    # Bold: **text** → \textbf{text}
    text = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", text)
    # Italic: *text* → \textit{text}
    text = re.sub(r"\*(.+?)\*", r"\\textit{\1}", text)
    # Inline code: `text` → \texttt{text}
    text = re.sub(r"`(.+?)`", r"\\texttt{\1}", text)
    return text


def _render_latex_table(rows: list[list[str]], alignments: list[str]) -> str:
    """Render a markdown table as LaTeX."""
    if not rows:
        return ""
    ncols = max(len(r) for r in rows)
    if not alignments:
        alignments = ["l"] * ncols
    while len(alignments) < ncols:
        alignments.append("l")

    lines = []
    lines.append(r"\begin{table}[htbp]")
    lines.append(r"\centering")
    lines.append(f"\\begin{{tabular}}{{{' '.join(alignments)}}}")
    lines.append(r"\toprule")

    for i, row in enumerate(rows):
        while len(row) < ncols:
            row.append("")
        cells = " & ".join(_latex_escape(c) for c in row)
        lines.append(f"{cells} \\\\")
        if i == 0:
            lines.append(r"\midrule")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Image discovery
# ---------------------------------------------------------------------------

def _list_artifact_images(db: ResearchDB | None) -> list[str]:
    """List available image files from the artifacts directory."""
    if not db:
        return []
    try:
        artifacts_dir = db.get_artifacts_dir()
    except RuntimeError:
        return []
    images = []
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.svg"):
        images.extend(f.name for f in artifacts_dir.glob(ext))
    return sorted(images)


# ---------------------------------------------------------------------------
# WriteStage
# ---------------------------------------------------------------------------

class WriteStage(BaseStage):
    """Generates a research paper: outline → sections → structure → style → format."""

    def __init__(self, name: str = "write", **kwargs):
        super().__init__(name=name, max_rounds=999, **kwargs)
        self._outline: list[dict] = []  # [{"title": ..., "task_ids": [...], "images": [...]}, ...]
        self._sections: dict[str, str] = {}  # title -> content
        self._phase = "outline"  # outline | sections | structure | style | format | done
        self._section_index = 0
        self._tasks_meta: list[dict] = []  # task list from plan
        self._refined_idea: str = ""
        self._current_draft: str = ""  # full draft for structure/style/format phases

    def get_round_label(self, round_index: int) -> str:
        if self._phase == "outline":
            return "Outline"
        if self._phase == "sections" and self._section_index < len(self._outline):
            return f"Write: {self._outline[self._section_index]['title']}"
        if self._phase == "structure":
            return "Structure"
        if self._phase == "style":
            return "Style"
        if self._phase == "format":
            return "Format"
        return ""

    def load_input(self) -> str:
        if self.llm_client and self.llm_client.has_tools:
            return (
                "Use list_tasks and read_task_output tools to read completed research outputs. "
                "Use read_refined_idea for context and read_plan_tree for structure. "
                "Use list_artifacts to discover available images and include them in the paper. "
                "Write the complete research paper."
            )
        return ""  # Gemini/Mock: build_messages reads DB directly

    def build_messages(self, input_text: str, round_index: int) -> list[dict]:
        if round_index == 0:
            self._tasks_meta = self._load_tasks_from_db()
            self._refined_idea = self.db.get_refined_idea() if self.db else ""
            self._phase = "outline"
            images = _list_artifact_images(self.db)
            return _build_outline_prompt(self._tasks_meta, self._refined_idea, images)

        if self._phase == "sections":
            section = self._outline[self._section_index]
            task_outputs = {}
            for tid in section.get("task_ids", []):
                output = self.db.get_task_output(tid) if self.db else ""
                if output:
                    task_outputs[tid] = output
            outline_titles = [s["title"] for s in self._outline]
            images = section.get("images", [])
            return _build_section_prompt(section["title"], task_outputs, outline_titles, images)

        if self._phase == "structure":
            return _build_structure_prompt(self._current_draft)

        if self._phase == "style":
            return _build_style_prompt(self._current_draft)

        if self._phase == "format":
            return _build_format_prompt(self._current_draft)

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
                self._current_draft = self._assemble_draft()
                self._phase = "structure"

        elif self._phase == "structure":
            self._current_draft = response
            self._phase = "style"

        elif self._phase == "style":
            self._current_draft = response
            self._phase = "format"

        elif self._phase == "format":
            self._current_draft = response
            self._phase = "done"

    def is_complete(self, response: str, round_index: int) -> bool:
        return self._phase == "done"

    def finalize(self) -> str:
        result = self._current_draft or (
            self.rounds[-1]["content"] if self.rounds else self._assemble_draft()
        )
        if self.db:
            self.db.save_paper(result)
            self.db.save_paper_tex(_md_to_latex(result))
        return result

    def retry(self):
        super().retry()
        self._outline.clear()
        self._sections.clear()
        self._phase = "outline"
        self._section_index = 0
        self._tasks_meta.clear()
        self._refined_idea = ""
        self._current_draft = ""

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
        data = parse_json_fenced(response)
        sections = data.get("sections", [])
        if not sections:
            # Fallback: default academic structure
            all_ids = [t["id"] for t in self._tasks_meta]
            sections = [
                {"title": "Abstract", "task_ids": all_ids, "images": []},
                {"title": "Introduction", "task_ids": all_ids, "images": []},
                {"title": "Methodology", "task_ids": all_ids, "images": []},
                {"title": "Results", "task_ids": all_ids, "images": []},
                {"title": "Conclusion", "task_ids": all_ids, "images": []},
            ]
        # Ensure images field exists for each section
        for s in sections:
            if "images" not in s:
                s["images"] = []
        return sections
