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
