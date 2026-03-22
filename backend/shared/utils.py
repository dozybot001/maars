"""Shared utilities."""

from __future__ import annotations

import re
from typing import Any, Callable, Optional

# Unified callback type for all agents' thinking/streaming output.
# Actual signature: (chunk, task_id=None, operation=None, schedule_info=None)
OnThinking = Optional[Callable[..., Any]]

import json_repair

_CODEBLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```")


def extract_codeblock(text: str) -> Optional[str]:
    """Extract content from a fenced code block (```json...``` or ```...```).

    Returns the inner text stripped, or None if no code block found.
    """
    m = _CODEBLOCK_RE.search(text or "")
    return m.group(1).strip() if m else None


def parse_json_response(text: str) -> Any:
    """Extract JSON from LLM response: strip codeblock fencing, then json_repair."""
    cleaned = extract_codeblock(text) or (text or "").strip()
    return json_repair.loads(cleaned)


def get_idea_text(refined: str | None) -> str:
    """Extract readable text from refined_idea (Markdown string)."""
    if not refined or not isinstance(refined, str):
        return ""
    return refined.strip()


def chunk_string(s: str, size: int):
    """Yield string in chunks for simulated streaming."""
    for i in range(0, len(s), size):
        yield s[i : i + size]


# ── Paper data helpers ───────────────────────────────────────────────

def truncate_text(value: Any, limit: int = 1200) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def maars_plan_to_paper_format(plan: dict) -> dict:
    """Convert MAARS plan shape to writing prompt format."""
    tasks = plan.get("tasks") or []
    return {
        "title": plan.get("idea") or "Untitled",
        "goal": plan.get("idea") or "N/A",
        "steps": [{"description": t.get("description", "")} for t in tasks],
    }


def build_output_digest(outputs: dict) -> list[dict]:
    """Build a compact digest of task outputs for paper generation."""
    import json
    digest = []
    for task_id, out in (outputs or {}).items():
        if isinstance(out, dict):
            content = out.get("content") or out.get("summary") or json.dumps(out, ensure_ascii=False)
        else:
            content = str(out)
        digest.append({
            "task_id": task_id,
            "summary": truncate_text(content, 1000),
        })
    return digest[:24]
