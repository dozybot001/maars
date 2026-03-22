"""
Tool schema definitions and execution logic for the Paper Agent.
Merged from paper_agent/tool_schemas.py and paper_agent/agent_tools.py.
"""

import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import orjson
from loguru import logger

from agents.skill_utils import (
    list_skills as _list_skills,
    load_skill as _load_skill,
    read_skill_file as _read_skill_file,
)

# ---------------------------------------------------------------------------
# Skills root
# ---------------------------------------------------------------------------

_PAPER_SKILLS_DIR = os.environ.get("MAARS_PAPER_SKILLS_DIR")
PAPER_SKILLS_ROOT = (
    Path(_PAPER_SKILLS_DIR).resolve()
    if _PAPER_SKILLS_DIR
    else Path(__file__).resolve().parent.parent / "skills"
)

# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

PAPER_AGENT_TOOLS = [
    {
        "name": "FinishPaper",
        "description": "Submit the final assembled paper and complete. Call last.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Final paper content"},
            },
            "required": ["content"],
        },
    },
    {
        "name": "ListSkills",
        "description": "List available Paper Agent skills.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "LoadSkill",
        "description": "Load a Paper Agent skill's SKILL.md content.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Skill name"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "ReadSkillFile",
        "description": "Read a file from a Paper Agent skill directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "skill": {"type": "string", "description": "Skill name"},
                "path": {"type": "string", "description": "Path relative to skill dir"},
            },
            "required": ["skill", "path"],
        },
    },
]


def get_paper_agent_tools(api_config: Optional[Dict] = None) -> List[dict]:
    """Return Paper Agent tool list."""
    return list(PAPER_AGENT_TOOLS)


# ---------------------------------------------------------------------------
# Skill helpers
# ---------------------------------------------------------------------------

def _paper_agent_list_skills() -> str:
    return _list_skills(PAPER_SKILLS_ROOT)


def _paper_agent_load_skill(name: str) -> str:
    return _load_skill(PAPER_SKILLS_ROOT, name)


def _paper_agent_read_skill_file(skill: str, path: str) -> str:
    return _read_skill_file(PAPER_SKILLS_ROOT, skill, path)


# ---------------------------------------------------------------------------
# Tool executor
# ---------------------------------------------------------------------------

async def execute_paper_agent_tool(
    name: str,
    arguments: str,
    paper_state: Dict[str, Any],
    *,
    on_thinking: Optional[Callable] = None,
    abort_event: Optional[Any] = None,
    api_config: Optional[Dict] = None,
) -> Tuple[bool, str]:
    """
    Execute a Paper Agent tool. Returns (is_finish, result_str).
    is_finish: True when FinishPaper is called.
    """
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else (arguments or {})
    except json.JSONDecodeError as e:
        return False, f"Error: invalid tool arguments: {e}"

    if name == "FinishPaper":
        content = args.get("content", "")
        return True, orjson.dumps({"content": content}).decode("utf-8")

    if name == "ListSkills":
        return False, _paper_agent_list_skills()

    if name == "LoadSkill":
        return False, _paper_agent_load_skill(args.get("name", ""))

    if name == "ReadSkillFile":
        return False, _paper_agent_read_skill_file(
            args.get("skill", ""), args.get("path", "")
        )

    return False, f"Error: unknown tool '{name}'"
