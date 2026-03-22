"""
Tool schema definitions and execution logic for the Idea Agent.
Merged from idea_agent/tool_schemas.py and idea_agent/agent_tools.py.
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

from agents.idea.literature import search_literature

# ---------------------------------------------------------------------------
# Skills root
# ---------------------------------------------------------------------------

_IDEA_SKILLS_DIR = os.environ.get("MAARS_IDEA_SKILLS_DIR")
IDEA_SKILLS_ROOT = (
    Path(_IDEA_SKILLS_DIR).resolve()
    if _IDEA_SKILLS_DIR
    else Path(__file__).resolve().parent.parent / "skills"
)

# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

IDEA_AGENT_TOOLS = [
    {
        "name": "SearchArxiv",
        "description": "Search arXiv with keywords.",
        "parameters": {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Search keywords",
                },
                "limit": {"type": "integer", "description": "Max papers to return", "default": 10},
                "cat": {
                    "type": "string",
                    "description": "Optional arXiv category, e.g. cs.AI, cs.LG, math.NA",
                },
            },
            "required": ["keywords"],
        },
    },
    {
        "name": "FilterPapers",
        "description": "Select the most relevant papers from the retrieved list by index.",
        "parameters": {
            "type": "object",
            "properties": {
                "papers_summary": {"type": "string", "description": "Full papers list with indices"},
                "idea": {"type": "string", "description": "User's idea for relevance"},
                "indices": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Indices (1-based) of papers to keep, e.g. [1,3,5,7,8]",
                },
            },
            "required": ["papers_summary", "idea", "indices"],
        },
    },
    {
        "name": "FinishIdea",
        "description": "Submit final refined_idea and complete. Call when satisfied with the refined idea.",
        "parameters": {
            "type": "object",
            "properties": {
                "keywords": {"type": "array", "items": {"type": "string"}, "description": "Final keywords used"},
                "papers": {"type": "array", "description": "Final papers list (full objects)"},
                "refined_idea": {"type": "string", "description": "Final refined idea (Markdown)"},
            },
            "required": ["keywords", "papers", "refined_idea"],
        },
    },
    {
        "name": "ListSkills",
        "description": "List available Idea Agent Skills (keyword extraction, paper evaluation, research templates, topic refinement, rag-research-template, literature-grounding, refined-idea quality).",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "LoadSkill",
        "description": "Load an Idea Agent skill's SKILL.md content.",
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
        "description": "Read a file from an Idea Agent skill directory.",
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


def get_idea_agent_tools(api_config: Optional[Dict] = None) -> List[dict]:
    """Return Idea Agent tool list."""
    return list(IDEA_AGENT_TOOLS)


# ---------------------------------------------------------------------------
# Skill helpers
# ---------------------------------------------------------------------------

def _idea_agent_list_skills() -> str:
    """List Idea Agent skills. Returns JSON string of [{name, description}, ...]."""
    return _list_skills(IDEA_SKILLS_ROOT)


def _idea_agent_load_skill(name: str) -> str:
    """Load Idea Agent skill SKILL.md content."""
    return _load_skill(IDEA_SKILLS_ROOT, name)


def _idea_agent_read_skill_file(skill: str, path: str) -> str:
    """Read file from Idea Agent skill directory."""
    return _read_skill_file(IDEA_SKILLS_ROOT, skill, path)


# ---------------------------------------------------------------------------
# Tool executor
# ---------------------------------------------------------------------------

async def execute_idea_agent_tool(
    name: str,
    arguments: str,
    idea_state: Dict[str, Any],
    *,
    on_thinking: Optional[Callable] = None,
    abort_event: Optional[Any] = None,
    api_config: Optional[Dict] = None,
    limit: int = 10,
) -> Tuple[bool, str]:
    """
    Execute an Idea Agent tool. Returns (is_finish, result_str).
    is_finish: True when FinishIdea is called.
    """
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else (arguments or {})
    except json.JSONDecodeError as e:
        return False, f"Error: invalid tool arguments: {e}"

    idea = idea_state.get("idea", "")
    api_config = api_config or {}

    if name == "SearchArxiv":
        keywords = args.get("keywords") or idea_state.get("keywords") or ["research"]
        lim = args.get("limit") or limit
        cat = (args.get("cat") or "").strip() or None
        query = "+".join(str(k).replace(" ", "+") for k in keywords)[:100]
        if not query:
            query = "research"
        source, papers = await search_literature(
            query,
            limit=lim,
            cat=cat,
            source=(api_config or {}).get("literatureSource"),
        )
        idea_state["papers"] = papers
        summary = [
            f"[{i+1}] {p.get('title','')[:80]}..."
            for i, p in enumerate(papers[:15])
        ]
        return False, orjson.dumps(
            {"count": len(papers), "source": source, "titles": summary}, option=orjson.OPT_INDENT_2
        ).decode("utf-8")

    if name == "FilterPapers":
        papers = idea_state.get("papers") or []
        indices = args.get("indices") or []
        if not indices:
            filtered = papers[:8]
        else:
            filtered = []
            for i in indices:
                if 1 <= i <= len(papers):
                    filtered.append(papers[i - 1])
        idea_state["filtered_papers"] = filtered
        return False, orjson.dumps(
            {"count": len(filtered), "indices": indices}, option=orjson.OPT_INDENT_2
        ).decode("utf-8")

    if name == "FinishIdea":
        keywords = args.get("keywords") or idea_state.get("keywords") or []
        papers = args.get("papers") or idea_state.get("papers") or []
        refined = args.get("refined_idea") or idea_state.get("refined_idea") or ""
        return True, orjson.dumps(
            {"keywords": keywords, "papers": papers, "refined_idea": refined},
            option=orjson.OPT_INDENT_2,
        ).decode("utf-8")

    if name == "ListSkills":
        return False, _idea_agent_list_skills()

    if name == "LoadSkill":
        return False, _idea_agent_load_skill(args.get("name", ""))

    if name == "ReadSkillFile":
        return False, _idea_agent_read_skill_file(
            args.get("skill", ""), args.get("path", "")
        )

    return False, f"Error: unknown tool '{name}'"
