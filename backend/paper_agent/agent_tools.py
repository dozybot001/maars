"""
Agent tools for Paper Agent: FinishPaper, ListSkills, LoadSkill, ReadSkillFile.
Used when paperAgentMode=True (pure agent mode — the LLM writes content directly).
"""

import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

import orjson
from loguru import logger

from shared.skill_utils import (
    list_skills as _list_skills,
    load_skill as _load_skill,
    read_skill_file as _read_skill_file,
)

_PAPER_SKILLS_DIR = os.environ.get("MAARS_PAPER_SKILLS_DIR")
PAPER_SKILLS_ROOT = (
    Path(_PAPER_SKILLS_DIR).resolve()
    if _PAPER_SKILLS_DIR
    else Path(__file__).resolve().parent / "skills"
)


def _paper_agent_list_skills() -> str:
    return _list_skills(PAPER_SKILLS_ROOT)


def _paper_agent_load_skill(name: str) -> str:
    return _load_skill(PAPER_SKILLS_ROOT, name)


def _paper_agent_read_skill_file(skill: str, path: str) -> str:
    return _read_skill_file(PAPER_SKILLS_ROOT, skill, path)


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
