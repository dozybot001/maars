"""Task title helpers.

Provide a compact, human-friendly title for task nodes while keeping full
description/objective in detail views.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable


_SPACE_RE = re.compile(r"\s+")
_LEADING_MARK_RE = re.compile(r"^[\-\*\d\.)\s]+")
_SPLIT_RE = re.compile(r"[\n\.;:!?]+")
_ZH_RE = re.compile(r"[\u4e00-\u9fff]")


def _truncate_title(text: str, *, zh_max: int = 20, en_max_words: int = 12) -> str:
    """Truncate a title string for display: Chinese by char count, English by word count."""
    if _ZH_RE.search(text):
        if len(text) > zh_max:
            return text[:zh_max].rstrip("，。；：、 ") + "…"
        return text
    words = text.split()
    if len(words) > en_max_words:
        return " ".join(words[:en_max_words]) + "…"
    return text


def derive_task_title(description: str, *, max_len: int = 48) -> str:
    """Derive a compact title from a longer task description."""
    text = str(description or "").strip()
    if not text:
        return ""
    text = _SPACE_RE.sub(" ", text)
    text = _LEADING_MARK_RE.sub("", text).strip()
    if not text:
        return ""

    head = _SPLIT_RE.split(text, maxsplit=1)[0].strip() or text
    truncated = _truncate_title(head, zh_max=12, en_max_words=8)
    if truncated != head:
        return truncated

    if len(head) <= max_len:
        return head
    return head[: max_len - 1].rstrip() + "…"


def ensure_task_title(task: Dict) -> Dict:
    """Fill `task['title']` in place when absent, or truncate provided title for display."""
    if not isinstance(task, dict):
        return task

    existing_title = str(task.get("title") or "").strip()
    if existing_title:
        task["title"] = _truncate_title(existing_title)
    else:
        source = str(task.get("description") or task.get("objective") or "")
        task["title"] = derive_task_title(source)

    return task


def ensure_task_titles(tasks: Iterable[Dict]) -> None:
    """Fill missing title for each task dict in place."""
    for task in tasks or []:
        ensure_task_title(task)
