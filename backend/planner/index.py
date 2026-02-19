"""
Planner module - atomicity check, decompose, format flow.
(Atomicity = check if task is atomic; output validation is in execution phase.)
Uses real LLM by default; Mock AI when use_mock=True.
"""

import asyncio
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import orjson
import json_repair

from .llm_client import chat_completion as real_chat_completion, merge_phase_config
from test.mock_stream import mock_chat_completion
from .graph_utils import has_cycle_in_subset

PLANNER_DIR = Path(__file__).parent
MOCK_AI_DIR = PLANNER_DIR.parent / "test" / "mock-ai"
MAX_DECOMPOSE_DEPTH = 5
MAX_CONCURRENT_CALLS = 10
MAX_VALIDATION_RETRIES = 2
RETRY_TEMPERATURE = 0.5

# Caches
_prompt_cache: Dict[str, str] = {}
_mock_cache: Dict[str, Dict] = {}
_call_semaphore: Optional[asyncio.Semaphore] = None


def _get_call_semaphore() -> asyncio.Semaphore:
    global _call_semaphore
    if _call_semaphore is None:
        _call_semaphore = asyncio.Semaphore(MAX_CONCURRENT_CALLS)
    return _call_semaphore


def _get_prompt_cached(filename: str) -> str:
    if filename not in _prompt_cache:
        path = PLANNER_DIR / "prompts" / filename
        _prompt_cache[filename] = path.read_text(encoding="utf-8").strip()
    return _prompt_cache[filename]


def _get_mock_cached(response_type: str) -> Dict:
    if response_type not in _mock_cache:
        path = MOCK_AI_DIR / f"{response_type}.json"
        try:
            _mock_cache[response_type] = orjson.loads(path.read_bytes())
        except (FileNotFoundError, orjson.JSONDecodeError):
            _mock_cache[response_type] = {}
    return _mock_cache[response_type]


def _load_mock_response(response_type: str, task_id: str) -> Optional[Dict]:
    data = _get_mock_cached(response_type)
    entry = data.get(task_id) or data.get("_default")
    if not entry:
        return None
    content = entry.get("content")
    if isinstance(content, str):
        content_str = content
    else:
        content_str = orjson.dumps(content).decode("utf-8")
    return {"content": content_str, "reasoning": entry.get("reasoning", "")}


# Operation labels for thinking display
# "atomicity" = atomicity check (whether task is atomic, no further decomposition)
# "validator" in execution = output validation (whether task output meets criteria)
_OP_LABELS = {
    "atomicity": "Atomicity",
    "decompose": "Decompose",
    "format_io": "Format (IO)",
    "format_validate": "Format (Validate)",
    "quality": "Quality",
}


def _find_task_idx(all_tasks: List[Dict], task_id: str) -> int:
    """Return index of task in all_tasks, or -1 if not found."""
    return next((i for i, t in enumerate(all_tasks) if t.get("task_id") == task_id), -1)


def _get_parent_id(task_id: str) -> str:
    """Get parent task_id. E.g. '1_2' -> '1', '1' -> '0'."""
    if "_" in task_id:
        return task_id.rsplit("_", 1)[0]
    return "0"


def _get_ancestor_path(task_id: str) -> str:
    """Build ancestor path string, e.g. '1_2' -> '0 → 1 → 1_2'."""
    if not task_id:
        return ""
    parts = []
    curr = task_id
    while True:
        parts.insert(0, curr)
        if curr == "0":
            break
        curr = _get_parent_id(curr)
    return " → ".join(parts)


def _build_user_message(response_type: str, task: Dict, context: Optional[Dict] = None) -> str:
    tid = task.get("task_id", "")
    desc = task.get("description", "")
    if response_type == "atomicity":
        return f'Input: task_id "{tid}", description "{desc}"\nOutput:'
    if response_type == "decompose":
        parts = [f'**Input:** task_id "{tid}", description "{desc}"']
        ctx = context or {}
        if ctx.get("depth") is not None:
            parts.append(f'\n**Context - depth:** {ctx["depth"]}')
        if ctx.get("ancestor_path"):
            parts.append(f'\n**Context - ancestor path:** {ctx["ancestor_path"]}')
        if ctx.get("idea"):
            parts.append(f'\n**Context - idea:** {ctx["idea"]}')
        if ctx.get("siblings"):
            sib = ctx["siblings"]
            if isinstance(sib, list):
                sib_str = "; ".join(f'{t.get("task_id","")}: {t.get("description","")}' for t in sib if t.get("task_id"))
            else:
                sib_str = str(sib)
            if sib_str:
                parts.append(f'\n**Context - sibling tasks:** {sib_str}')
        parts.append('\n\n**Output:**')
        return "".join(parts)
    if response_type == "quality":
        ctx = context or {}
        idea = ctx.get("idea", "")
        tasks_summary = ctx.get("tasksSummary", "")
        return f'**Idea:** {idea}\n\n**Tasks:**\n{tasks_summary}\n\n**Output:**'
    if response_type == "format_io":
        return f'**Input task:** task_id "{tid}", description "{desc}"\n\n**Output:**'
    if response_type == "format_validate":
        parts = [f'**Input task:** task_id "{tid}", description "{desc}"']
        ctx = context or {}
        io_spec = ctx.get("inputOutputSpec")
        if io_spec:
            io_str = orjson.dumps(io_spec, option=orjson.OPT_INDENT_2).decode("utf-8")
            parts.append(f'\n\n**Input/Output spec (from Phase 1):**\n```json\n{io_str}\n```')
        parts.append('\n\n**Output:**')
        return "".join(parts)
    return f"Task: {tid} - {desc}"


async def _call_chat_completion(
    on_thinking: Callable[..., None],
    context: Dict,
    abort_event: Optional[Any],
    stream: bool = True,
    use_mock: bool = False,
    api_config: Optional[Dict] = None,
    temperature: Optional[float] = None,
) -> str:
    response_type = context["type"]
    task_id = context["taskId"]
    task = context.get("task", {})

    def stream_chunk(chunk: str) -> None:
        if on_thinking and chunk:
            op_label = _OP_LABELS.get(response_type, response_type.capitalize())
            on_thinking(chunk, task_id=task_id, operation=op_label)

    if use_mock:
        mock = _load_mock_response(response_type, task_id)
        if not mock:
            raise ValueError(f"No mock data for {response_type}/{task_id}")
        effective_on_thinking = stream_chunk if (stream and on_thinking) else None
        async with _get_call_semaphore():
            return await mock_chat_completion(
                mock["content"],
                mock["reasoning"],
                effective_on_thinking,
                abort_event=abort_event,
                stream=stream,
            )

    # Real LLM
    prompt_file = {
        "atomicity": "atomicity-prompt.txt",
        "decompose": "decompose-prompt.txt",
        "format_io": "format-io-prompt.txt",
        "format_validate": "format-validate-prompt.txt",
        "quality": "quality-assess-prompt.txt",
    }.get(response_type, "atomicity-prompt.txt")
    system_prompt = _get_prompt_cached(prompt_file)
    msg_ctx = (
        context.get("decomposeContext") if response_type == "decompose"
        else context.get("qualityContext") if response_type == "quality"
        else context.get("formatContext") if response_type == "format_validate"
        else None
    )
    user_message = _build_user_message(response_type, context.get("task", {}), msg_ctx)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    phase = "atomicity" if response_type in ("atomicity", "quality") else "decompose" if response_type == "decompose" else "format"
    cfg = merge_phase_config(api_config, phase)
    effective_on_chunk = stream_chunk if (stream and on_thinking) else None
    # JSON mode for atomicity/quality (pure JSON); decompose/format_* keep reasoning + JSON block
    response_format = {"type": "json_object"} if response_type in ("atomicity", "quality") else None
    async with _get_call_semaphore():
        return await real_chat_completion(
            messages,
            cfg,
            on_chunk=effective_on_chunk,
            abort_event=abort_event,
            stream=stream,
            temperature=temperature,
            response_format=response_format,
        )


def _parse_json_response(text: str) -> Any:
    """Parse JSON from AI response using json_repair for malformed output."""
    cleaned = (text or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if m:
        cleaned = m.group(1).strip()
    try:
        return json_repair.loads(cleaned)
    except Exception as e:
        raise ValueError(f"Failed to parse JSON from AI response: {e}") from e


def _validate_atomicity_response(result: Any) -> bool:
    """Validate atomicity check output. Returns True if valid."""
    if not isinstance(result, dict):
        return False
    if "atomic" not in result:
        return False
    v = result["atomic"]
    return isinstance(v, bool) or v in (0, 1, "true", "false")


def _validate_decompose_response(result: Any, parent_id: str) -> tuple[bool, str]:
    """Validate decompose output. Returns (valid, error_msg)."""
    if not isinstance(result, dict):
        return False, "Response is not a dict"
    tasks = result.get("tasks")
    if not isinstance(tasks, list) or len(tasks) == 0:
        return False, "tasks must be a non-empty list"
    seen_ids: set[str] = set()
    valid_prefix = parent_id if parent_id == "0" else f"{parent_id}_"
    allowed_deps = {parent_id} | seen_ids
    for i, t in enumerate(tasks):
        if not isinstance(t, dict):
            return False, f"Task {i} is not a dict"
        tid = t.get("task_id")
        if not tid or not isinstance(tid, str):
            return False, f"Task {i} missing or invalid task_id"
        if tid in seen_ids:
            return False, f"Duplicate task_id: {tid}"
        seen_ids.add(tid)
        allowed_deps.add(tid)
        if parent_id == "0":
            if not tid.isdigit() or tid == "0":
                return False, f"Top-level task_id must be 1,2,3,... got {tid}"
        else:
            if not tid.startswith(valid_prefix) or tid == parent_id:
                return False, f"Child task_id must be {parent_id}_N, got {tid}"
        if not t.get("description") or not isinstance(t.get("description"), str):
            return False, f"Task {tid} missing or invalid description"
        deps = t.get("dependencies")
        if not isinstance(deps, list):
            return False, f"Task {tid} dependencies must be a list"
        for d in deps:
            if not isinstance(d, str):
                return False, f"Task {tid} has non-string dependency"
            if d and d not in allowed_deps:
                return False, f"Task {tid} dependency {d} does not exist (must be {parent_id} or sibling)"
    if has_cycle_in_subset(tasks, seen_ids):
        return False, "Circular dependency detected among children"
    return True, ""


async def _decompose_task(
    parent_task: Dict,
    on_thinking: Callable[[str], None],
    abort_event: Optional[Any],
    all_tasks: List[Dict],
    idea: Optional[str] = None,
    depth: int = 0,
    use_mock: bool = False,
    api_config: Optional[Dict] = None,
) -> List[Dict]:
    ctx: Dict[str, Any] = {"type": "decompose", "taskId": parent_task["task_id"], "task": parent_task}
    pid = parent_task["task_id"]
    siblings = [t for t in all_tasks if t.get("task_id") != pid and _get_parent_id(t.get("task_id", "")) == _get_parent_id(pid)]
    ctx["decomposeContext"] = {
        "idea": idea or "",
        "siblings": siblings,
        "depth": depth,
        "ancestor_path": _get_ancestor_path(pid),
    }
    last_err: Optional[Exception] = None
    for attempt in range(MAX_VALIDATION_RETRIES + 1):
        try:
            content = await _call_chat_completion(
                on_thinking,
                ctx,
                abort_event,
                stream=True,
                use_mock=use_mock,
                api_config=api_config,
                temperature=RETRY_TEMPERATURE if attempt > 0 else None,
            )
            result = _parse_json_response(content)
            valid, err_msg = _validate_decompose_response(result, pid)
            if not valid:
                raise ValueError(f"Decompose validation failed: {err_msg}")
            tasks = result.get("tasks") or []
            return [
                t
                for t in tasks
                if t.get("task_id") and t.get("description") and isinstance(t.get("dependencies"), list)
            ]
        except Exception as e:
            last_err = e
            if attempt >= MAX_VALIDATION_RETRIES:
                raise
    raise last_err or ValueError("Decompose failed")


async def _check_atomicity(
    task: Dict,
    on_thinking: Callable[[str], None],
    abort_event: Optional[Any],
    use_mock: bool = False,
    api_config: Optional[Dict] = None,
) -> Dict:
    last_err: Optional[Exception] = None
    for attempt in range(MAX_VALIDATION_RETRIES + 1):
        try:
            content = await _call_chat_completion(
                on_thinking,
                {"type": "atomicity", "taskId": task["task_id"], "task": task},
                abort_event,
                stream=False,
                use_mock=use_mock,
                api_config=api_config,
                temperature=RETRY_TEMPERATURE if attempt > 0 else None,
            )
            result = _parse_json_response(content)
            if not _validate_atomicity_response(result):
                raise ValueError("Atomicity response invalid: missing or invalid atomic field")
            return {"atomic": bool(result.get("atomic"))}
        except Exception as e:
            last_err = e
            if attempt >= MAX_VALIDATION_RETRIES:
                raise
    raise last_err or ValueError("Atomicity check failed")


async def _format_task(
    task: Dict,
    on_thinking: Callable[[str], None],
    abort_event: Optional[Any],
    use_mock: bool = False,
    api_config: Optional[Dict] = None,
) -> Optional[Dict]:
    # Phase 1: Define input/output specification
    content_io = await _call_chat_completion(
        on_thinking,
        {"type": "format_io", "taskId": task.get("task_id", ""), "task": task},
        abort_event,
        stream=True,
        use_mock=use_mock,
        api_config=api_config,
    )
    result_io = _parse_json_response(content_io)
    if not result_io.get("input") or not result_io.get("output"):
        return None
    io_spec = {"input": result_io["input"], "output": result_io["output"]}

    # Phase 2: Define validation specification (context includes input/output from Phase 1)
    content_val = await _call_chat_completion(
        on_thinking,
        {
            "type": "format_validate",
            "taskId": task.get("task_id", ""),
            "task": task,
            "formatContext": {"inputOutputSpec": io_spec},
        },
        abort_event,
        stream=True,
        use_mock=use_mock,
        api_config=api_config,
    )
    result_val = _parse_json_response(content_val)
    validation = result_val.get("validation") if isinstance(result_val.get("validation"), dict) else None

    return {
        "input": io_spec["input"],
        "output": io_spec["output"],
        **({"validation": validation} if validation else {}),
    }


async def _atomicity_and_decompose_recursive(
    task: Dict,
    all_tasks: List[Dict],
    on_task: Optional[Callable[[Dict], None]],
    on_thinking: Callable[[str], None],
    depth: int,
    check_aborted: Callable[[], bool],
    abort_event: Optional[Any],
    on_tasks_batch: Optional[Callable[[List[Dict], Dict, List[Dict]], None]] = None,
    idea: Optional[str] = None,
    use_mock: bool = False,
    api_config: Optional[Dict] = None,
) -> None:
    if check_aborted and check_aborted():
        raise asyncio.CancelledError("Aborted")

    if depth >= MAX_DECOMPOSE_DEPTH:
        io_result = await _format_task(task, on_thinking, abort_event, use_mock, api_config)
        if not io_result:
            raise ValueError(f"Format failed for task {task['task_id']} at max depth: missing input/output")
        idx = _find_task_idx(all_tasks, task["task_id"])
        if idx >= 0:
            all_tasks[idx] = {**all_tasks[idx], **io_result}
        return

    v = await _check_atomicity(task, on_thinking, abort_event, use_mock, api_config)
    atomic = v["atomic"]

    if atomic:
        io_result = await _format_task(task, on_thinking, abort_event, use_mock, api_config)
        if not io_result:
            raise ValueError(f"Format failed for atomic task {task['task_id']}: missing input/output")
        idx = _find_task_idx(all_tasks, task["task_id"])
        if idx >= 0:
            all_tasks[idx] = {**all_tasks[idx], **io_result}
        return

    children = await _decompose_task(task, on_thinking, abort_event, all_tasks, idea, depth, use_mock, api_config)
    if not children:
        raise ValueError(f"Decompose returned no children for task {task['task_id']}")

    all_tasks.extend(children)
    if on_tasks_batch:
        on_tasks_batch(children, task, list(all_tasks))
    elif on_task:
        for t in children:
            on_task(t)

    await asyncio.gather(*[
        _atomicity_and_decompose_recursive(
            child, all_tasks, on_task, on_thinking, depth + 1, check_aborted, abort_event, on_tasks_batch,
            idea, use_mock, api_config,
        )
        for child in children
    ])


async def _assess_quality(
    plan: Dict,
    on_thinking: Callable[[str], None],
    abort_event: Optional[Any],
    use_mock: bool = False,
    api_config: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Assess plan quality. Returns {score, comment} or {score: 0, comment: 'N/A'} on failure."""
    if use_mock:
        return {"score": 85, "comment": "Mock assessment"}
    idea = plan.get("idea", "")
    tasks = plan.get("tasks") or []
    lines = []
    for t in tasks:
        tid = t.get("task_id", "")
        desc = (t.get("description") or "")[:80]
        deps = ",".join(t.get("dependencies") or [])
        has_io = "✓" if (t.get("input") and t.get("output")) else ""
        lines.append(f"- {tid}: {desc} | deps:[{deps}] {has_io}")
    tasks_summary = "\n".join(lines) if lines else "(no tasks)"
    ctx: Dict[str, Any] = {
        "type": "quality",
        "taskId": "_",
        "task": {},
        "qualityContext": {"idea": idea, "tasksSummary": tasks_summary},
    }
    try:
        content = await _call_chat_completion(
            on_thinking,
            ctx,
            abort_event,
            stream=False,
            use_mock=use_mock,
            api_config=api_config,
        )
        result = _parse_json_response(content)
        score = result.get("score")
        if isinstance(score, (int, float)):
            score = max(0, min(100, int(score)))
        else:
            score = 0
        comment = result.get("comment") or ""
        return {"score": score, "comment": str(comment)}
    except Exception:
        return {"score": 0, "comment": "Assessment skipped"}


async def run_plan(
    plan: Dict,
    on_task: Optional[Callable[[Dict], None]],
    on_thinking: Callable[[str], None],
    abort_event: Optional[Any] = None,
    on_tasks_batch: Optional[Callable[[List[Dict], Dict, List[Dict]], None]] = None,
    use_mock: bool = False,
    api_config: Optional[Dict] = None,
    skip_quality_assessment: bool = False,
) -> Dict:
    """Run atomicity->decompose->format from root task, top-down to all atomic tasks."""

    def check_aborted() -> bool:
        return abort_event is not None and abort_event.is_set()

    tasks = plan.get("tasks") or []
    root_task = next((t for t in tasks if t.get("task_id") == "0"), None)
    if not root_task:
        root_task = next(
            (t for t in tasks if t.get("task_id") and not (t.get("dependencies") or [])),
            tasks[0] if tasks else None,
        )
    if not root_task:
        raise ValueError("No decomposable task found. Generate plan first.")

    all_tasks = list(tasks)
    on_thinking_fn = on_thinking or (lambda _: None)
    idea = plan.get("idea") or root_task.get("description") or ""
    await _atomicity_and_decompose_recursive(
        root_task, all_tasks, on_task, on_thinking_fn, 0, check_aborted, abort_event, on_tasks_batch,
        idea=idea, use_mock=use_mock, api_config=api_config,
    )
    plan["tasks"] = all_tasks
    if not skip_quality_assessment:
        quality = await _assess_quality(plan, on_thinking_fn, abort_event, use_mock, api_config)
        plan["qualityScore"] = quality.get("score", 0)
        plan["qualityComment"] = quality.get("comment", "")
    else:
        plan["qualityScore"] = None
        plan["qualityComment"] = ""
    return {"tasks": all_tasks}
