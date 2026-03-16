"""Database Module.

Storage is SQLite-backed (see `db/sqlite_backend.py`), including settings.
"""

import asyncio
import shutil
from loguru import logger

from . import sqlite_backend
from .db_paths import (
    DB_DIR,
    DEFAULT_IDEA_ID,
    DEFAULT_PLAN_ID,
    SANDBOX_DIR,
    _get_file_path,
    _get_idea_dir,
    _get_plan_dir,
    _get_task_dir,
    _validate_idea_id,
    _validate_plan_id,
    _validate_task_id,
    ensure_execution_task_dirs,
    ensure_sandbox_dir,
    find_execution_run_ids_for_research,
    get_execution_sandbox_root,
    get_execution_src_dir,
    get_execution_step_root_dir,
    get_execution_task_dir,
    get_execution_task_src_dir,
    get_execution_task_step_dir,
    get_sandbox_dir,
    remove_execution_sandbox_root,
)
from .db_settings import get_effective_config, get_settings, save_settings
from .db_research_ops import (
    clear_research_stage_data_for_retry,
    create_research,
    delete_research_cascade,
    delete_task_attempt_memories,
    get_paper,
    get_research,
    list_researches,
    list_task_attempt_memories,
    save_paper,
    save_task_attempt_memory,
    update_research_stage,
)


async def get_task_artifact(idea_id: str, plan_id: str, task_id: str):
    """Read task artifact. Returns dict or None."""
    _validate_idea_id(idea_id)
    _validate_plan_id(plan_id)
    _validate_task_id(task_id)
    return await sqlite_backend.get_task_artifact(idea_id, plan_id, task_id)


async def list_plan_outputs(idea_id: str, plan_id: str) -> dict:
    """Load all task outputs for a plan. Returns {task_id: output_dict}."""
    _validate_idea_id(idea_id)
    _validate_plan_id(plan_id)
    return await sqlite_backend.list_plan_outputs(idea_id, plan_id)


async def save_task_artifact(idea_id: str, plan_id: str, task_id: str, value) -> dict:
    """Write task artifact."""
    _validate_idea_id(idea_id)
    _validate_plan_id(plan_id)
    _validate_task_id(task_id)
    return await sqlite_backend.save_task_artifact(idea_id, plan_id, task_id, value)


async def delete_task_artifact(idea_id: str, plan_id: str, task_id: str) -> bool:
    """Remove task artifact. Returns True if deleted."""
    _validate_idea_id(idea_id)
    _validate_plan_id(plan_id)
    _validate_task_id(task_id)
    return await sqlite_backend.delete_task_artifact(idea_id, plan_id, task_id)


async def save_validation_report(idea_id: str, plan_id: str, task_id: str, report: dict) -> dict:
    """Save task validation report."""
    _validate_idea_id(idea_id)
    _validate_plan_id(plan_id)
    _validate_task_id(task_id)
    return await sqlite_backend.save_validation_report(idea_id, plan_id, task_id, report)


async def _ensure_idea_dir(idea_id: str = DEFAULT_IDEA_ID) -> None:
    # Legacy no-op: kept for backwards imports.
    _validate_idea_id(idea_id)
    return


async def _ensure_plan_dir(idea_id: str, plan_id: str) -> None:
    # Legacy no-op: kept for backwards imports.
    _validate_idea_id(idea_id)
    _validate_plan_id(plan_id)
    return


async def _read_json_file(idea_id: str, plan_id: str, filename: str):
    # Legacy: file-based helpers are no longer used.
    return None


async def _write_json_file(idea_id: str, plan_id: str, filename: str, data: dict) -> dict:
    # Legacy: file-based helpers are no longer used.
    return {"success": False}


# Idea persistence

async def get_idea(idea_id: str = DEFAULT_IDEA_ID):
    """Get idea (Refine output: idea, keywords, papers, etc.)."""
    _validate_idea_id(idea_id)
    return await sqlite_backend.get_idea(idea_id)


async def save_idea(idea_data: dict, idea_id: str = DEFAULT_IDEA_ID) -> dict:
    """Save idea to db/{idea_id}/idea.json."""
    _validate_idea_id(idea_id)
    return await sqlite_backend.save_idea(idea_id, idea_data)


# Plan and execution

async def get_execution(idea_id: str, plan_id: str):
    """Get execution."""
    _validate_idea_id(idea_id)
    _validate_plan_id(plan_id)
    return await sqlite_backend.get_execution(idea_id, plan_id)


async def save_execution(execution: dict, idea_id: str, plan_id: str) -> dict:
    """Save execution."""
    _validate_idea_id(idea_id)
    _validate_plan_id(plan_id)
    return await sqlite_backend.save_execution(idea_id, plan_id, execution)


async def list_idea_ids() -> list:
    """List idea IDs from db/, sorted by idea.json mtime (newest first)."""
    return await sqlite_backend.list_idea_ids()


async def list_plan_ids(idea_id: str) -> list:
    """List plan IDs under an idea, sorted by plan.json mtime (newest first)."""
    _validate_idea_id(idea_id)
    return await sqlite_backend.list_plan_ids(idea_id)


async def list_recent_plans() -> list:
    """List (ideaId, planId) pairs from db/, sorted by plan.json mtime (newest first)."""
    return await sqlite_backend.list_recent_plans()


async def get_plan(idea_id: str, plan_id: str):
    """Get plan (tasks only, no idea)."""
    _validate_idea_id(idea_id)
    _validate_plan_id(plan_id)
    return await sqlite_backend.get_plan(idea_id, plan_id)


async def save_plan(plan: dict, idea_id: str, plan_id: str) -> dict:
    """Save plan."""
    _validate_idea_id(idea_id)
    _validate_plan_id(plan_id)
    return await sqlite_backend.save_plan(idea_id, plan_id, plan)


# AI response persistence (atomicity, decompose, format) - per idea_id + plan_id

_ai_save_locks: dict = {}


def _get_ai_save_lock(idea_id: str, plan_id: str, response_type: str) -> asyncio.Lock:
    key = (idea_id, plan_id, response_type)
    if key not in _ai_save_locks:
        _ai_save_locks[key] = asyncio.Lock()
    return _ai_save_locks[key]


async def _read_ai_response_file(idea_id: str, plan_id: str, response_type: str) -> dict:
    # Legacy: replaced by SQLite storage.
    return await sqlite_backend.get_ai_responses(idea_id, plan_id, response_type)


async def get_ai_responses(idea_id: str, plan_id: str, response_type: str) -> dict:
    """Read AI responses for a plan. response_type: atomicity, decompose, format."""
    if response_type not in ("atomicity", "decompose", "format"):
        return {}
    _validate_idea_id(idea_id)
    _validate_plan_id(plan_id)
    return await sqlite_backend.get_ai_responses(idea_id, plan_id, response_type)


async def _write_ai_response_file(idea_id: str, plan_id: str, response_type: str, data: dict) -> None:
    await sqlite_backend.save_ai_responses_blob(idea_id, plan_id, response_type, data)


async def save_ai_response(idea_id: str, plan_id: str, response_type: str, key: str, entry: dict) -> None:
    """Incrementally save one AI response. entry = {content: ..., reasoning: ...}. Serialized per file."""
    if response_type not in ("atomicity", "decompose", "format"):
        return
    _validate_idea_id(idea_id)
    _validate_plan_id(plan_id)
    lock = _get_ai_save_lock(idea_id, plan_id, response_type)
    async with lock:
        data = await get_ai_responses(idea_id, plan_id, response_type)
        data[key] = entry
        await _write_ai_response_file(idea_id, plan_id, response_type, data)


async def clear_db() -> dict:
    """Clear DB runtime artifacts (ideas/plans/execution/research/papers). Keeps settings."""
    removed = []
    # Clear sqlite data first
    await sqlite_backend.clear_all_data()
    # Best-effort remove legacy folders for a fully clean slate.
    if DB_DIR.exists():
        for p in DB_DIR.iterdir():
            if not p.is_dir() or p.name.startswith("."):
                continue
            try:
                shutil.rmtree(p)
                removed.append(p.name)
            except OSError as e:
                logger.warning("Failed to remove %s: %s", p, e)
    if SANDBOX_DIR.exists() and SANDBOX_DIR.is_dir():
        for p in SANDBOX_DIR.iterdir():
            if not p.is_dir() or p.name.startswith("."):
                continue
            try:
                shutil.rmtree(p)
                removed.append(f"sandbox/{p.name}")
            except OSError as e:
                logger.warning("Failed to remove %s: %s", p, e)
    return {"success": True, "removed": removed}



