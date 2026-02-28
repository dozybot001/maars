"""Shared utilities."""

import json
from typing import Any, Optional


def format_tool_args_preview(tool_name: str, args_str: str, max_len: int = 80) -> Optional[str]:
    """Parse tool args JSON and return a human-readable preview for schedule display."""
    if not args_str or not isinstance(args_str, str):
        return None
    args_str = args_str.strip()
    if not args_str:
        return None
    try:
        obj = json.loads(args_str) if args_str.startswith("{") else {}
    except (json.JSONDecodeError, TypeError):
        return args_str[:max_len] + ("..." if len(args_str) > max_len else "")
    if not isinstance(obj, dict):
        return str(obj)[:max_len]
    # Build preview from key params per tool
    parts = []
    key_params = {
        "ReadArtifact": ["task_id"],
        "ReadFile": ["path"],
        "WriteFile": ["path"],
        "Finish": [],  # output too long
        "LoadSkill": ["name"],
        "ReadSkillFile": ["skill", "path"],
        "RunSkillScript": ["skill", "script"],
        "WebSearch": ["query"],
        "WebFetch": ["url"],
        "CheckAtomicity": ["task_id"],
        "Decompose": ["task_id"],
        "FormatTask": ["task_id"],
        "AddTasks": ["parent_id", "tasks"],
        "UpdateTask": ["task_id"],
    }
    keys = key_params.get(tool_name, list(obj.keys())[:3])
    for k in keys:
        v = obj.get(k)
        if v is None:
            continue
        if k == "tasks" and isinstance(v, list):
            parts.append(f"{len(v)} tasks")
        elif isinstance(v, str) and len(v) > 50:
            parts.append(f"{k}: {v[:47]}...")
        else:
            parts.append(f"{k}: {v}")
    result = ", ".join(parts) if parts else None
    if result and len(result) > max_len:
        result = result[: max_len - 3] + "..."
    return result


def chunk_string(s: str, size: int):
    """Yield string in chunks for simulated streaming."""
    for i in range(0, len(s), size):
        yield s[i : i + size]
