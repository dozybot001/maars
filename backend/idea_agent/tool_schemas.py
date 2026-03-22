"""
Tool schema definitions for the Idea Agent.
Flat dict format: {"name", "description", "parameters"}.
"""

from typing import Dict, List, Optional


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
    """返回 Idea Agent 工具列表。"""
    return list(IDEA_AGENT_TOOLS)
