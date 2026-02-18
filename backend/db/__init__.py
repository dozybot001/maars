"""
Database Module
File-based storage: db/{plan_id}/ contains plan.json, execution.json, verification.json.
Planner generates a new plan_id folder on each new plan; all reads/writes use plan_id.
Uses orjson for faster JSON parsing.
"""

from pathlib import Path

import aiofiles
import orjson
from loguru import logger

DB_DIR = Path(__file__).parent
DEFAULT_PLAN_ID = "test"


def _validate_plan_id(plan_id: str) -> None:
    """Reject path traversal and invalid plan_id."""
    if not plan_id or not isinstance(plan_id, str):
        raise ValueError("plan_id must be a non-empty string")
    if ".." in plan_id or "/" in plan_id or "\\" in plan_id:
        raise ValueError("plan_id must not contain path separators")


def _get_plan_dir(plan_id: str = DEFAULT_PLAN_ID) -> Path:
    return DB_DIR / plan_id


def _get_file_path(plan_id: str, filename: str) -> Path:
    return _get_plan_dir(plan_id) / filename


async def _ensure_plan_dir(plan_id: str = DEFAULT_PLAN_ID) -> None:
    _validate_plan_id(plan_id)
    plan_dir = _get_plan_dir(plan_id)
    plan_dir.mkdir(parents=True, exist_ok=True)


async def _read_json_file(plan_id: str, filename: str):
    await _ensure_plan_dir(plan_id)
    file_path = _get_file_path(plan_id, filename)
    try:
        async with aiofiles.open(file_path, "rb") as f:
            data = await f.read()
            return orjson.loads(data)
    except FileNotFoundError:
        return None
    except orjson.JSONDecodeError as e:
        logger.warning("Invalid JSON in %s: %s", file_path, e)
        return None


async def _write_json_file(plan_id: str, filename: str, data: dict) -> dict:
    await _ensure_plan_dir(plan_id)
    file_path = _get_file_path(plan_id, filename)
    content = orjson.dumps(data, option=orjson.OPT_INDENT_2).decode("utf-8")
    async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
        await f.write(content)
    return {"success": True}


async def get_idea(plan_id: str = DEFAULT_PLAN_ID):
    """Get idea from plan (plan.idea or task0.description)."""
    plan = await get_plan(plan_id)
    if not plan:
        return None
    if plan.get("idea"):
        return plan["idea"]
    task0 = next((t for t in (plan.get("tasks") or []) if t.get("task_id") == "0"), None)
    return task0.get("description") if task0 else None


async def get_execution(plan_id: str = DEFAULT_PLAN_ID):
    """Get execution."""
    return await _read_json_file(plan_id, "execution.json")


async def save_execution(execution: dict, plan_id: str = DEFAULT_PLAN_ID) -> dict:
    """Save execution."""
    await _write_json_file(plan_id, "execution.json", execution)
    return {"success": True, "execution": execution}


async def get_verification(plan_id: str = DEFAULT_PLAN_ID):
    """Get verification."""
    return await _read_json_file(plan_id, "verification.json")


async def save_verification(verification: dict, plan_id: str = DEFAULT_PLAN_ID) -> dict:
    """Save verification."""
    await _write_json_file(plan_id, "verification.json", verification)
    return {"success": True, "verification": verification}


async def get_plan(plan_id: str = DEFAULT_PLAN_ID):
    """Get plan (AI-refined idea with tasks)."""
    return await _read_json_file(plan_id, "plan.json")


async def save_plan(plan: dict, plan_id: str = DEFAULT_PLAN_ID) -> dict:
    """Save plan."""
    await _write_json_file(plan_id, "plan.json", plan)
    return {"success": True, "plan": plan}
