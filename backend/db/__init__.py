"""
Database Module
File-based storage: db/{plan_id}/ contains plan.json, execution.json, validation.json.
Planner generates a new plan_id folder on each new plan; all reads/writes use plan_id.
Uses orjson for faster JSON parsing.
"""

import re
from pathlib import Path

import aiofiles
import orjson
from loguru import logger

DB_DIR = Path(__file__).parent
DEFAULT_PLAN_ID = "test"
API_CONFIG_FILE = "api_config.json"


def _validate_plan_id(plan_id: str) -> None:
    """Reject path traversal and invalid plan_id."""
    if not plan_id or not isinstance(plan_id, str):
        raise ValueError("plan_id must be a non-empty string")
    if ".." in plan_id or "/" in plan_id or "\\" in plan_id:
        raise ValueError("plan_id must not contain path separators")


def _validate_task_id(task_id: str) -> None:
    """Reject path traversal and invalid task_id. Only alphanumeric and underscore."""
    if not task_id or not isinstance(task_id, str):
        raise ValueError("task_id must be a non-empty string")
    if ".." in task_id or "/" in task_id or "\\" in task_id:
        raise ValueError("task_id must not contain path separators")
    if not re.match(r"^[a-zA-Z0-9_]+$", task_id):
        raise ValueError("task_id must contain only letters, digits, and underscores")


def _get_plan_dir(plan_id: str = DEFAULT_PLAN_ID) -> Path:
    return DB_DIR / plan_id


def _get_file_path(plan_id: str, filename: str) -> Path:
    return _get_plan_dir(plan_id) / filename


def _get_task_dir(plan_id: str, task_id: str) -> Path:
    """Return db/{plan_id}/{task_id}/."""
    _validate_plan_id(plan_id)
    _validate_task_id(task_id)
    return _get_plan_dir(plan_id) / task_id


async def get_task_artifact(plan_id: str, task_id: str):
    """Read artifact from db/{plan_id}/{task_id}/output.json. Returns dict or None."""
    _validate_plan_id(plan_id)
    _validate_task_id(task_id)
    task_dir = _get_task_dir(plan_id, task_id)
    file_path = task_dir / "output.json"
    try:
        async with aiofiles.open(file_path, "rb") as f:
            data = await f.read()
            return orjson.loads(data)
    except FileNotFoundError:
        return None
    except orjson.JSONDecodeError as e:
        logger.warning("Invalid JSON in %s: %s", file_path, e)
        return None


async def save_task_artifact(plan_id: str, task_id: str, value) -> dict:
    """Write artifact to db/{plan_id}/{task_id}/output.json. Accepts dict or str (wrapped as {"content": ...})."""
    _validate_plan_id(plan_id)
    _validate_task_id(task_id)
    if isinstance(value, str):
        value = {"content": value}
    task_dir = _get_task_dir(plan_id, task_id)
    task_dir.mkdir(parents=True, exist_ok=True)
    file_path = task_dir / "output.json"
    content = orjson.dumps(value, option=orjson.OPT_INDENT_2).decode("utf-8")
    async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
        await f.write(content)
    return {"success": True}


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


async def get_validation(plan_id: str = DEFAULT_PLAN_ID):
    """Get validation (output validation results)."""
    return await _read_json_file(plan_id, "validation.json")


async def save_validation(validation: dict, plan_id: str = DEFAULT_PLAN_ID) -> dict:
    """Save validation (output validation results)."""
    await _write_json_file(plan_id, "validation.json", validation)
    return {"success": True, "validation": validation}


async def list_plan_ids() -> list:
    """List plan IDs from db/, sorted by plan.json mtime (newest first)."""
    if not DB_DIR.exists():
        return []
    result = []
    for p in DB_DIR.iterdir():
        if p.is_dir() and not p.name.startswith("."):
            plan_file = p / "plan.json"
            if plan_file.exists():
                try:
                    mtime = plan_file.stat().st_mtime
                    result.append((p.name, mtime))
                except OSError:
                    result.append((p.name, 0))
    result.sort(key=lambda x: x[1], reverse=True)
    return [pid for pid, _ in result]


async def get_api_config() -> dict:
    """Get API config from db/api_config.json. Returns {} if not found."""
    file_path = DB_DIR / API_CONFIG_FILE
    try:
        async with aiofiles.open(file_path, "rb") as f:
            data = await f.read()
            return orjson.loads(data)
    except FileNotFoundError:
        return {}
    except orjson.JSONDecodeError as e:
        logger.warning("Invalid JSON in %s: %s", file_path, e)
        return {}


async def save_api_config(config: dict) -> dict:
    """Save API config to db/api_config.json."""
    file_path = DB_DIR / API_CONFIG_FILE
    content = orjson.dumps(config or {}, option=orjson.OPT_INDENT_2).decode("utf-8")
    async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
        await f.write(content)
    return {"success": True}


async def get_plan(plan_id: str = DEFAULT_PLAN_ID):
    """Get plan (AI-refined idea with tasks)."""
    return await _read_json_file(plan_id, "plan.json")


async def save_plan(plan: dict, plan_id: str = DEFAULT_PLAN_ID) -> dict:
    """Save plan."""
    await _write_json_file(plan_id, "plan.json", plan)
    return {"success": True, "plan": plan}
