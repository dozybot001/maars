"""
Tool schema definitions for the Paper Agent.
Flat dict format: {"name", "description", "parameters"}.
"""

from typing import Dict, List, Optional


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
    """返回 Paper Agent 工具列表。"""
    return list(PAPER_AGENT_TOOLS)
