"""
Database Module
File-based storage: db/{plan_id}/ contains plan.json, execution.json, validation.json.
Planner generates a new plan_id folder on each new plan; all reads/writes use plan_id.
Uses orjson for faster JSON parsing.
"""

import asyncio
import re
import shutil
from pathlib import Path

import aiofiles
import json_repair
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


def get_sandbox_dir(plan_id: str, task_id: str) -> Path:
    """Return db/{plan_id}/{task_id}/sandbox/ for isolated task execution."""
    return _get_task_dir(plan_id, task_id) / "sandbox"


async def ensure_sandbox_dir(plan_id: str, task_id: str) -> Path:
    """Create sandbox dir if not exists. Returns the sandbox path."""
    sandbox = get_sandbox_dir(plan_id, task_id)
    sandbox.mkdir(parents=True, exist_ok=True)
    return sandbox


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
    """Write artifact to db/{plan_id}/{task_id}/output.json. Atomic write. Accepts dict or str (wrapped as {"content": ...})."""
    _validate_plan_id(plan_id)
    _validate_task_id(task_id)
    if isinstance(value, str):
        value = {"content": value}
    task_dir = _get_task_dir(plan_id, task_id)
    task_dir.mkdir(parents=True, exist_ok=True)
    file_path = task_dir / "output.json"
    tmp_path = file_path.with_suffix(file_path.suffix + ".tmp")
    content = orjson.dumps(value, option=orjson.OPT_INDENT_2).decode("utf-8")
    async with aiofiles.open(tmp_path, "w", encoding="utf-8") as f:
        await f.write(content)
    tmp_path.replace(file_path)
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
    """Atomic write: write to .tmp then rename to avoid partial/corrupt files on concurrent access."""
    await _ensure_plan_dir(plan_id)
    file_path = _get_file_path(plan_id, filename)
    tmp_path = file_path.with_suffix(file_path.suffix + ".tmp")
    content = orjson.dumps(data, option=orjson.OPT_INDENT_2).decode("utf-8")
    async with aiofiles.open(tmp_path, "w", encoding="utf-8") as f:
        await f.write(content)
    tmp_path.replace(file_path)
    return {"success": True}


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


def _ai_mode_to_flags(ai_mode: str) -> tuple:
    """Convert aiMode to (useMock, executorAgentMode) for backward compatibility."""
    if ai_mode == "mock":
        return True, False
    if ai_mode == "llm-agent":
        return False, True
    return False, False  # llm or default


def _resolve_api_config(raw: dict) -> dict:
    """Resolve presets+current to effective config. aiMode: mock|llm|llm-agent."""
    if not raw:
        return {}
    ai_mode = raw.get("aiMode") or raw.get("ai_mode")
    if not ai_mode and ("useMock" in raw or "use_mock" in raw):
        use_mock = raw.get("useMock", raw.get("use_mock", True))
        exec_agent = raw.get("executorAgentMode", raw.get("executor_agent_mode", False))
        ai_mode = "mock" if use_mock else ("llm-agent" if exec_agent else "llm")
    ai_mode = ai_mode or "mock"
    use_mock, exec_agent = _ai_mode_to_flags(ai_mode)

    presets = raw.get("presets")
    current = raw.get("current")
    if isinstance(presets, dict) and current and current in presets:
        cfg = dict(presets[current])
        cfg.pop("label", None)
    else:
        cfg = {k: v for k, v in raw.items() if k not in ("presets", "current", "aiMode", "ai_mode")}
    cfg["useMock"] = use_mock
    cfg["executorAgentMode"] = exec_agent
    mode_config = raw.get("modeConfig") or {}
    cfg["modeConfig"] = mode_config
    for m in ("llm", "llm-agent"):
        pm = mode_config.get(m) or {}
        t = pm.get("plannerTemperature")
        if t is not None:
            cfg["temperature"] = float(t)
            break
    return cfg


async def get_api_config() -> dict:
    """Get full API config (with presets) from db/api_config.json. For frontend."""
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


async def get_effective_api_config() -> dict:
    """Get effective API config for LLM calls (resolves current preset)."""
    raw = await get_api_config()
    return _resolve_api_config(raw)


async def save_api_config(config: dict) -> dict:
    """Save API config to db/api_config.json. Atomic write to avoid corruption."""
    file_path = DB_DIR / API_CONFIG_FILE
    tmp_path = file_path.with_suffix(file_path.suffix + ".tmp")
    content = orjson.dumps(config or {}, option=orjson.OPT_INDENT_2).decode("utf-8")
    async with aiofiles.open(tmp_path, "w", encoding="utf-8") as f:
        await f.write(content)
    tmp_path.replace(file_path)
    return {"success": True}


async def get_plan(plan_id: str = DEFAULT_PLAN_ID):
    """Get plan (AI-refined idea with tasks)."""
    return await _read_json_file(plan_id, "plan.json")


async def save_plan(plan: dict, plan_id: str = DEFAULT_PLAN_ID) -> dict:
    """Save plan."""
    await _write_json_file(plan_id, "plan.json", plan)
    return {"success": True, "plan": plan}


# AI response persistence (atomicity, decompose, format) - per plan_id

_ai_save_locks: dict = {}


def _get_ai_save_lock(plan_id: str, response_type: str) -> asyncio.Lock:
    key = (plan_id, response_type)
    if key not in _ai_save_locks:
        _ai_save_locks[key] = asyncio.Lock()
    return _ai_save_locks[key]


async def _read_ai_response_file(plan_id: str, response_type: str) -> dict:
    """Read AI response file with json_repair fallback for corrupted files."""
    await _ensure_plan_dir(plan_id)
    file_path = _get_file_path(plan_id, f"{response_type}.json")
    try:
        async with aiofiles.open(file_path, "rb") as f:
            raw = await f.read()
        try:
            data = orjson.loads(raw)
        except orjson.JSONDecodeError:
            data = json_repair.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception as e:
        logger.warning("Failed to read %s: %s", file_path, e)
        return {}


async def get_ai_responses(plan_id: str, response_type: str) -> dict:
    """Read AI responses for a plan. response_type: atomicity, decompose, format."""
    if response_type not in ("atomicity", "decompose", "format"):
        return {}
    return await _read_ai_response_file(plan_id, response_type)


async def _write_ai_response_file(plan_id: str, response_type: str, data: dict) -> None:
    """Atomic write: write to .tmp then rename."""
    await _ensure_plan_dir(plan_id)
    file_path = _get_file_path(plan_id, f"{response_type}.json")
    tmp_path = file_path.with_suffix(".json.tmp")
    content = orjson.dumps(data, option=orjson.OPT_INDENT_2).decode("utf-8")
    async with aiofiles.open(tmp_path, "w", encoding="utf-8") as f:
        await f.write(content)
    tmp_path.rename(file_path)


async def save_ai_response(plan_id: str, response_type: str, key: str, entry: dict) -> None:
    """Incrementally save one AI response. entry = {content: ..., reasoning: ...}. Serialized per file."""
    if response_type not in ("atomicity", "decompose", "format"):
        return
    lock = _get_ai_save_lock(plan_id, response_type)
    async with lock:
        data = await get_ai_responses(plan_id, response_type)
        data[key] = entry
        await _write_ai_response_file(plan_id, response_type, data)


async def clear_db() -> dict:
    """Clear DB: remove all plan folders."""
    if not DB_DIR.exists():
        return {"success": True, "removed": []}
    removed = []
    for p in DB_DIR.iterdir():
        if not p.is_dir() or p.name.startswith("."):
            continue
        try:
            shutil.rmtree(p)
            removed.append(p.name)
        except OSError as e:
            logger.warning("Failed to remove %s: %s", p, e)
    return {"success": True, "removed": removed}
