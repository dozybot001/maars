"""
Tool schema definitions and execution logic for the Task Agent.
Merged from task_agent/agent_tool_defs.py and task_agent/agent_tools.py.
"""

import json
import os
from pathlib import Path
from typing import Any, Optional, Tuple

from agents.task import web as web_tools
from agents.task.finish import run_finish
from agents.task.io import (
    run_list_files as _run_list_files_impl,
    run_read_artifact,
    run_read_file as _run_read_file_impl,
    run_write_file as _run_write_file_impl,
)
from agents.task.command import run_run_command as _run_run_command_impl
from agents.task.skills_tool import (
    run_list_skills as _run_list_skills,
    run_load_skill as _run_load_skill,
    run_read_skill_file as _run_read_skill_file,
    run_run_skill_script as _run_run_skill_script,
)
from agents.task.docker import run_command_in_container

_RUN_SCRIPT_ALLOWED_EXT = (".py", ".sh", ".js")
_RUN_SCRIPT_TIMEOUT = int(os.environ.get("MAARS_RUN_SCRIPT_TIMEOUT", "120"))

_TASK_SKILLS_DIR = os.environ.get("MAARS_TASK_SKILLS_DIR")
SKILLS_ROOT = (
    Path(_TASK_SKILLS_DIR).resolve()
    if _TASK_SKILLS_DIR
    else Path(__file__).resolve().parent.parent / "skills"
)

# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "ReadArtifact",
        "description": "Read output artifact from a dependency task. Use when you need the output of another task that this task depends on.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "Task ID whose output to read (e.g. from dependencies)",
                },
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "ReadFile",
        "description": "Read a file. Use 'sandbox/...' for files in this task's sandbox (e.g. sandbox/result.txt).",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path under sandbox, e.g. sandbox/result.txt or sandbox/data/output.json",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "ListFiles",
        "description": "List files/directories under a path. Use 'sandbox/' to discover available files before ReadFile.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list. Prefer sandbox paths (e.g. sandbox/ or sandbox/data).",
                    "default": "sandbox/",
                },
                "max_entries": {
                    "type": "integer",
                    "description": "Maximum entries to return (default 200, max 500)",
                    "default": 200,
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Maximum traversal depth (default 3, max 8)",
                    "default": 3,
                },
            },
        },
    },
    {
        "name": "WriteFile",
        "description": "Write content to a file in this task's sandbox. Path must be under sandbox (e.g. sandbox/notes.txt). Use for intermediate results.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path under sandbox, e.g. sandbox/data.json or sandbox/notes.txt",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "RunCommand",
        "description": "Run a shell command inside the local Docker execution container using the current task sandbox as the working directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to run inside Docker, e.g. 'python script.py' or 'ls -la'",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Optional timeout in seconds (default 120)",
                    "default": 120,
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "Finish",
        "description": "Submit the final output and complete the task. Call this when output satisfies the output spec. For JSON format pass an object; for Markdown pass a string.",
        "parameters": {
            "type": "object",
            "properties": {
                "output": {
                    "type": "string",
                    "description": "Final output: JSON string or Markdown content. For JSON format, pass a valid JSON string.",
                },
            },
            "required": ["output"],
        },
    },
    {
        "name": "ListSkills",
        "description": "List available Agent Skills (name and description). Use to discover skills before loading one with LoadSkill.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "LoadSkill",
        "description": "Load a skill's SKILL.md full content into context. Call after ListSkills to get the skill name. The content will be available in the next turn.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Skill name (directory name under skills root, e.g. from ListSkills)",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "ReadSkillFile",
        "description": "Read a file from a skill's directory (scripts/, references/, assets/). Use after LoadSkill when you need to read a specific file from the skill.",
        "parameters": {
            "type": "object",
            "properties": {
                "skill": {
                    "type": "string",
                    "description": "Skill name (e.g. docx, pptx)",
                },
                "path": {
                    "type": "string",
                    "description": "Path relative to skill dir, e.g. scripts/office/unpack.py or references/example.md",
                },
            },
            "required": ["skill", "path"],
        },
    },
    {
        "name": "RunSkillScript",
        "description": "Execute a script from a skill. Use for docx/pptx/xlsx validation, conversion, etc. Script runs from skill dir. Use [[sandbox]]/filename in args for sandbox file paths (e.g. [[sandbox]]/output.docx).",
        "parameters": {
            "type": "object",
            "properties": {
                "skill": {
                    "type": "string",
                    "description": "Skill name (e.g. docx, pptx, xlsx)",
                },
                "script": {
                    "type": "string",
                    "description": "Path to script relative to skill dir, e.g. scripts/office/validate.py",
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Command-line args. Use [[sandbox]]/file.docx for sandbox file paths.",
                },
            },
            "required": ["skill", "script"],
        },
    },
    {
        "name": "WebSearch",
        "description": "Search the web for information. Use for research tasks when you need current data, benchmarks, or official documentation. Returns title, URL, and snippet for each result. Prefer WebSearch then WebFetch for key URLs to cite sources.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (e.g. 'FastAPI performance benchmark RPS', 'Django vs Flask comparison 2024')",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max results to return (default 5, max 10)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "WebFetch",
        "description": "Fetch content from a URL. Use after WebSearch to get full page content for citations. Only http/https URLs; no localhost.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Full URL to fetch (e.g. https://fastapi.tiangolo.com)",
                },
            },
            "required": ["url"],
        },
    },
]


# ---------------------------------------------------------------------------
# Wrapper helpers (delegate to task_agent sub-modules)
# ---------------------------------------------------------------------------

def run_list_skills() -> str:
    return _run_list_skills(SKILLS_ROOT)


def run_load_skill(name: str) -> str:
    return _run_load_skill(SKILLS_ROOT, name)


def run_read_skill_file(skill: str, path: str) -> str:
    return _run_read_skill_file(SKILLS_ROOT, skill, path)


async def run_read_file(
    idea_id: str,
    plan_id: str,
    path: str,
    task_id: str = "",
    execution_run_id: str = "",
    docker_container_name: str = "",
) -> str:
    return await _run_read_file_impl(
        idea_id,
        plan_id,
        path,
        task_id,
        execution_run_id,
        docker_container_name,
        command_runner=run_command_in_container,
    )


async def run_write_file(
    idea_id: str,
    plan_id: str,
    path: str,
    content: str,
    task_id: str = "",
    execution_run_id: str = "",
    docker_container_name: str = "",
) -> str:
    return await _run_write_file_impl(
        idea_id,
        plan_id,
        path,
        content,
        task_id,
        execution_run_id,
        docker_container_name,
        command_runner=run_command_in_container,
    )


async def run_list_files(
    idea_id: str,
    plan_id: str,
    path: str,
    task_id: str = "",
    execution_run_id: str = "",
    docker_container_name: str = "",
    max_entries: int = 200,
    max_depth: int = 3,
) -> str:
    return await _run_list_files_impl(
        idea_id,
        plan_id,
        path,
        task_id,
        execution_run_id,
        docker_container_name,
        max_entries,
        max_depth,
        command_runner=run_command_in_container,
    )


async def run_run_command(
    command: str,
    task_id: str,
    *,
    docker_container_name: str = "",
    timeout_seconds: int | None = None,
) -> str:
    return await _run_run_command_impl(
        command,
        task_id,
        docker_container_name=docker_container_name,
        timeout_seconds=timeout_seconds,
        default_timeout_seconds=_RUN_SCRIPT_TIMEOUT,
        command_runner=run_command_in_container,
    )


async def run_run_skill_script(
    skill: str,
    script: str,
    args: list[str],
    idea_id: str,
    plan_id: str,
    task_id: str,
    execution_run_id: str = "",
    docker_container_name: str = "",
) -> str:
    return await _run_run_skill_script(
        skill,
        script,
        args,
        idea_id,
        plan_id,
        task_id,
        skills_root=SKILLS_ROOT,
        run_script_allowed_ext=_RUN_SCRIPT_ALLOWED_EXT,
        run_script_timeout=_RUN_SCRIPT_TIMEOUT,
        execution_run_id=execution_run_id,
        docker_container_name=docker_container_name,
    )


# ---------------------------------------------------------------------------
# Tool executor
# ---------------------------------------------------------------------------

async def execute_tool(
    name: str,
    arguments: str,
    idea_id: str,
    plan_id: str,
    task_id: str,
    *,
    execution_run_id: str = "",
    docker_container_name: str = "",
    output_format: str = "",
) -> Tuple[Optional[Any], str]:
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else (arguments or {})
    except json.JSONDecodeError as e:
        return None, f"Error: invalid tool arguments: {e}"

    if name == "ReadArtifact":
        tid = args.get("task_id", "")
        return None, await run_read_artifact(idea_id, plan_id, tid)

    if name == "ReadFile":
        path = args.get("path", "")
        return None, await run_read_file(
            idea_id,
            plan_id,
            path,
            task_id,
            execution_run_id,
            docker_container_name,
        )

    if name == "ListFiles":
        return None, await run_list_files(
            idea_id,
            plan_id,
            args.get("path", "sandbox/"),
            task_id,
            execution_run_id,
            docker_container_name,
            args.get("max_entries", 200),
            args.get("max_depth", 3),
        )

    if name == "WriteFile":
        path = args.get("path", "")
        content = args.get("content", "")
        return None, await run_write_file(
            idea_id,
            plan_id,
            path,
            content,
            task_id,
            execution_run_id,
            docker_container_name,
        )

    if name == "RunCommand":
        return None, await run_run_command(
            args.get("command", ""),
            task_id,
            docker_container_name=docker_container_name,
            timeout_seconds=args.get("timeout_seconds"),
        )

    if name == "ListSkills":
        return None, run_list_skills()

    if name == "LoadSkill":
        return None, run_load_skill(args.get("name", ""))

    if name == "ReadSkillFile":
        return None, run_read_skill_file(args.get("skill", ""), args.get("path", ""))

    if name == "RunSkillScript":
        script_args = args.get("args") or []
        if isinstance(script_args, str):
            try:
                script_args = json.loads(script_args) if script_args else []
            except json.JSONDecodeError:
                script_args = [script_args]
        return None, await run_run_skill_script(
            args.get("skill", ""),
            args.get("script", ""),
            script_args,
            idea_id,
            plan_id,
            task_id,
            execution_run_id=execution_run_id,
            docker_container_name=docker_container_name,
        )

    if name == "Finish":
        ok, val = run_finish(args.get("output", ""), output_format=output_format)
        if ok:
            return val, ""
        return None, val

    if name == "WebSearch":
        return None, await web_tools.run_web_search(
            args.get("query", ""), args.get("max_results", 5)
        )

    if name == "WebFetch":
        return None, await web_tools.run_web_fetch(args.get("url", ""))

    return None, f"Error: unknown tool '{name}'"
