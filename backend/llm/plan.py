"""
Plan Agent single-turn LLM functions — atomicity, decompose, format, quality.

Merged from plan_agent/llm/executor_helpers.py (helpers) and
plan_agent/llm/executor.py (LLM call functions).
"""

import asyncio
from typing import Any, Callable, Dict, List, Optional

import networkx as nx

from db import save_ai_response
from llm.client import llm_call_structured, load_prompt
from shared.constants import (
    MAX_FORMAT_REPAIR_ATTEMPTS,
    PLAN_MAX_CONCURRENT_CALLS,
    PLAN_MAX_VALIDATION_RETRIES,
    TEMP_AGENT_LOOP,
    TEMP_DETERMINISTIC,
    TEMP_RETRY,
    TEMP_STRUCTURED,
)
from shared.graph import build_dependency_graph, get_ancestor_path, get_parent_id
from mock import load_mock
from shared.utils import parse_json_response

# ---------------------------------------------------------------------------
# Helpers  (originally in executor_helpers.py)
# ---------------------------------------------------------------------------

_call_semaphore: Optional[asyncio.Semaphore] = None


def _get_call_semaphore() -> asyncio.Semaphore:
    global _call_semaphore
    if _call_semaphore is None:
        _call_semaphore = asyncio.Semaphore(PLAN_MAX_CONCURRENT_CALLS)
    return _call_semaphore



_OP_LABELS = {
    "atomicity": "Atomicity",
    "decompose": "Decompose",
    "format": "Format",
    "quality": "Quality",
}


def _build_user_message(response_type: str, task: Dict, context: Optional[Dict] = None) -> str:
    tid = task.get("task_id", "")
    desc = task.get("description", "")
    if response_type == "atomicity":
        parts = [f'Input: task_id "{tid}", description "{desc}"']
        ctx = context or {}
        if ctx.get("depth") is not None:
            parts.append(f'\nContext - depth: {ctx["depth"]}')
        if ctx.get("ancestor_path"):
            parts.append(f'\nContext - ancestor path: {ctx["ancestor_path"]}')
        if ctx.get("idea"):
            parts.append(f'\nContext - idea: {ctx["idea"]}')
        if ctx.get("siblings"):
            sib = ctx["siblings"]
            if isinstance(sib, list):
                sib_str = "; ".join(f'{t.get("task_id","")}: {t.get("description","")}' for t in sib if t.get("task_id"))
            else:
                sib_str = str(sib)
            if sib_str:
                parts.append(f'\nContext - sibling tasks: {sib_str}')
        parts.append('\nOutput:')
        return "".join(parts)
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
    if response_type == "format":
        return f'**Input task:** task_id "{tid}", description "{desc}"\n\n**Output:**'
    return f"Task: {tid} - {desc}"


def _build_messages_for_context(context: Dict[str, Any]) -> tuple[str, str]:
    """Return ``(system_prompt, user_text)`` for the given context."""
    response_type = context["type"]
    prompt_file = {
        "atomicity": "plan-atomicity.txt",
        "decompose": "plan-decompose.txt",
        "format": "plan-format.txt",
        "quality": "plan-quality.txt",
    }.get(response_type, "plan-atomicity.txt")
    system_prompt = load_prompt(prompt_file)
    msg_ctx = (
        context.get("decomposeContext") if response_type == "decompose"
        else context.get("qualityContext") if response_type == "quality"
        else context.get("atomicityContext") if response_type == "atomicity"
        else None
    )
    user_text = _build_user_message(response_type, context.get("task", {}), msg_ctx)
    return system_prompt, user_text

# ---------------------------------------------------------------------------
# LLM functions  (originally in executor.py)
# ---------------------------------------------------------------------------


def _parse_json_response(text: str) -> Any:
    """Parse JSON from AI response using json_repair for malformed output."""
    try:
        return parse_json_response(text)
    except Exception as e:
        raise ValueError(f"Failed to parse JSON from AI response: {e}") from e


def _validate_atomicity_response(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    if "atomic" not in result:
        return False
    v = result["atomic"]
    return isinstance(v, bool) or v in (0, 1, "true", "false")


def _validate_decompose_response(result: Any, parent_id: str) -> tuple[bool, str]:
    if not isinstance(result, dict):
        return False, "Response is not a dict"
    tasks = result.get("tasks")
    if not isinstance(tasks, list) or len(tasks) == 0:
        return False, "tasks must be a non-empty list"
    seen_ids: set[str] = set()
    valid_prefix = parent_id if parent_id == "0" else f"{parent_id}_"
    for i, t in enumerate(tasks):
        if not isinstance(t, dict):
            return False, f"Task {i} is not a dict"
        tid = t.get("task_id")
        if not tid or not isinstance(tid, str):
            return False, f"Task {i} missing or invalid task_id"
        if tid in seen_ids:
            return False, f"Duplicate task_id: {tid}"
        seen_ids.add(tid)
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
            if d == parent_id:
                return False, f"Task {tid} must not depend on parent {parent_id} (use task_id hierarchy instead)"
            if d and d not in seen_ids:
                return False, f"Task {tid} dependency {d} must be an earlier sibling"
    if seen_ids and not nx.is_directed_acyclic_graph(build_dependency_graph(tasks, ids=seen_ids)):
        return False, "Circular dependency detected among children"
    return True, ""


def raise_if_aborted(abort_event: Optional[Any]) -> None:
    """Raise CancelledError if abort_event is set."""
    if abort_event is not None and abort_event.is_set():
        raise asyncio.CancelledError("Aborted")


def _make_on_chunk(on_thinking: Callable, task_id: str, op_label: str) -> Callable[[str], None]:
    """Build an on_chunk callback that delegates to on_thinking with task_id/operation."""
    def stream_chunk(chunk: str):
        if on_thinking and chunk:
            return on_thinking(chunk, task_id=task_id, operation=op_label)
    return stream_chunk


async def check_atomicity(
    task: Dict,
    on_thinking: Callable[[str], None],
    abort_event: Optional[Any],
    atomicity_context: Optional[Dict] = None,
    use_mock: bool = False,
    api_config: Optional[Dict] = None,
    idea_id: Optional[str] = None,
    plan_id: Optional[str] = None,
) -> Dict:
    """Check if task is atomic. Plan Agent LLM single-turn."""
    raise_if_aborted(abort_event)
    ctx: Dict[str, Any] = {"type": "atomicity", "taskId": task["task_id"], "task": task}
    if atomicity_context:
        ctx["atomicityContext"] = atomicity_context

    system_prompt, user_text = _build_messages_for_context(ctx)

    def _validate(parsed: Any) -> tuple[bool, str]:
        if not _validate_atomicity_response(parsed):
            return False, "Atomicity response invalid: missing or invalid atomic field"
        return True, ""

    mock = None
    if use_mock:
        entry = load_mock("atomicity", task["task_id"])
        if not entry:
            raise ValueError(f"No mock data for atomicity/{task['task_id']}")
        mock = entry["content"]

    task_id = ctx["taskId"]
    op_label = _OP_LABELS.get("atomicity", "Atomicity")
    on_chunk = _make_on_chunk(on_thinking, task_id, op_label) if on_thinking else None
    async with _get_call_semaphore():
        result, _raw = await llm_call_structured(
            system=system_prompt,
            user=user_text,
            api_config=api_config or {},
            parse_fn=_parse_json_response,
            validate_fn=_validate,
            temperatures=[TEMP_DETERMINISTIC] + [TEMP_RETRY] * PLAN_MAX_VALIDATION_RETRIES,
            on_chunk=on_chunk,
            abort_event=abort_event,
            mock=mock,
        )

    out = {"atomic": bool(result.get("atomic"))}
    if idea_id and plan_id:
        asyncio.create_task(save_ai_response(
            idea_id, plan_id, "atomicity", task["task_id"],
            {"content": {"atomic": out["atomic"]}, "reasoning": ""},
        ))
    return out


async def decompose_task(
    parent_task: Dict,
    on_thinking: Callable[[str], None],
    abort_event: Optional[Any],
    all_tasks: List[Dict],
    idea: Optional[str] = None,
    depth: int = 0,
    use_mock: bool = False,
    api_config: Optional[Dict] = None,
    idea_id: Optional[str] = None,
    plan_id: Optional[str] = None,
) -> List[Dict]:
    """Decompose non-atomic task into children. Plan Agent LLM single-turn."""
    raise_if_aborted(abort_event)
    ctx: Dict[str, Any] = {"type": "decompose", "taskId": parent_task["task_id"], "task": parent_task}
    pid = parent_task["task_id"]
    siblings = [t for t in all_tasks if t.get("task_id") != pid and get_parent_id(t.get("task_id", "")) == get_parent_id(pid)]
    ctx["decomposeContext"] = {
        "idea": idea or "",
        "siblings": siblings,
        "depth": depth,
        "ancestor_path": get_ancestor_path(pid),
    }

    system_prompt, user_text = _build_messages_for_context(ctx)

    def _validate(parsed: Any) -> tuple[bool, str]:
        ok, err_msg = _validate_decompose_response(parsed, pid)
        return ok, err_msg or "Decompose validation failed"

    mock = None
    if use_mock:
        entry = load_mock("decompose", pid)
        if not entry:
            raise ValueError(f"No mock data for decompose/{pid}")
        mock = entry["content"]

    task_id = ctx["taskId"]
    op_label = _OP_LABELS.get("decompose", "Decompose")
    on_chunk = _make_on_chunk(on_thinking, task_id, op_label) if on_thinking else None
    async with _get_call_semaphore():
        result, _raw = await llm_call_structured(
            system=system_prompt,
            user=user_text,
            api_config=api_config or {},
            parse_fn=_parse_json_response,
            validate_fn=_validate,
            temperatures=[TEMP_AGENT_LOOP] + [TEMP_RETRY] * PLAN_MAX_VALIDATION_RETRIES,
            on_chunk=on_chunk,
            abort_event=abort_event,
            mock=mock,
        )

    tasks = result.get("tasks") or []
    out = [
        t
        for t in tasks
        if t.get("task_id") and t.get("description") and isinstance(t.get("dependencies"), list)
    ]
    if idea_id and plan_id:
        asyncio.create_task(save_ai_response(
            idea_id, plan_id, "decompose", pid,
            {"content": {"tasks": tasks}, "reasoning": ""},
        ))
    return out


async def format_task(
    task: Dict,
    on_thinking: Callable[[str], None],
    abort_event: Optional[Any],
    use_mock: bool = False,
    api_config: Optional[Dict] = None,
    idea_id: Optional[str] = None,
    plan_id: Optional[str] = None,
) -> Optional[Dict]:
    """Generate input/output spec for atomic task. Plan Agent LLM single-turn with repair retries."""
    temps = [TEMP_STRUCTURED] + [TEMP_RETRY] * max(1, MAX_FORMAT_REPAIR_ATTEMPTS - 1)
    ctx = {"type": "format", "taskId": task.get("task_id", ""), "task": task}
    system_prompt, user_text = _build_messages_for_context(ctx)

    def _validate(parsed: Any) -> tuple[bool, str]:
        if not isinstance(parsed, dict):
            return False, "FormatTask response must be a JSON object"
        if not parsed.get("input") or not parsed.get("output"):
            return False, "FormatTask returned no input/output"
        return True, ""

    mock = None
    if use_mock:
        entry = load_mock("format", task.get("task_id", ""))
        if not entry:
            raise ValueError(f"No mock data for format/{task.get('task_id', '')}")
        mock = entry["content"]

    task_id = ctx["taskId"]
    op_label = _OP_LABELS.get("format", "Format")
    on_chunk = _make_on_chunk(on_thinking, task_id, op_label) if on_thinking else None
    async with _get_call_semaphore():
        result, _raw = await llm_call_structured(
            system=system_prompt,
            user=user_text,
            api_config=api_config or {},
            parse_fn=_parse_json_response,
            validate_fn=_validate,
            temperatures=temps,
            on_chunk=on_chunk,
            abort_event=abort_event,
            mock=mock,
        )

    validation = result.get("validation") if isinstance(result.get("validation"), dict) else None
    out = {
        "input": result["input"],
        "output": result["output"],
        **({"validation": validation} if validation else {}),
    }
    if idea_id and plan_id:
        asyncio.create_task(save_ai_response(
            idea_id, plan_id, "format", task.get("task_id", ""),
            {"content": {"input": result["input"], "output": result["output"], "validation": validation or {}}, "reasoning": ""},
        ))
    return out


async def assess_quality(
    plan: Dict,
    on_thinking: Callable[[str], None],
    abort_event: Optional[Any],
    use_mock: bool = False,
    api_config: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Assess plan quality. Plan Agent LLM single-turn. Returns {score, comment}."""
    raise_if_aborted(abort_event)
    idea = plan.get("idea", "")
    tasks = plan.get("tasks") or []
    lines = []
    for t in tasks:
        tid = t.get("task_id", "")
        desc = (t.get("description") or "")[:80]
        deps = ",".join(t.get("dependencies") or [])
        has_io = "\u2713" if (t.get("input") and t.get("output")) else ""
        lines.append(f"- {tid}: {desc} | deps:[{deps}] {has_io}")
    tasks_summary = "\n".join(lines) if lines else "(no tasks)"
    ctx: Dict[str, Any] = {
        "type": "quality",
        "taskId": "_",
        "task": {},
        "qualityContext": {"idea": idea, "tasksSummary": tasks_summary},
    }
    try:
        system_prompt, user_text = _build_messages_for_context(ctx)

        def _validate(parsed: Any) -> tuple[bool, str]:
            if not isinstance(parsed, dict):
                return False, "Quality response must be a JSON object"
            if "score" not in parsed:
                return False, "Quality response missing score"
            return True, ""

        mock = None
        if use_mock:
            entry = load_mock("quality", "_")
            if not entry:
                raise ValueError("No mock data for quality/_")
            mock = entry["content"]

        task_id = ctx["taskId"]
        op_label = _OP_LABELS.get("quality", "Quality")
        on_chunk = _make_on_chunk(on_thinking, task_id, op_label) if on_thinking else None
        async with _get_call_semaphore():
            result, _raw = await llm_call_structured(
                system=system_prompt,
                user=user_text,
                api_config=api_config or {},
                parse_fn=_parse_json_response,
                validate_fn=_validate,
                temperatures=[TEMP_STRUCTURED] + [TEMP_RETRY] * PLAN_MAX_VALIDATION_RETRIES,
                on_chunk=on_chunk,
                abort_event=abort_event,
                mock=mock,
            )

        score = result.get("score")
        if isinstance(score, (int, float)):
            score = max(0, min(100, int(score)))
        else:
            score = 0
        comment = result.get("comment") or ""
        return {"score": score, "comment": str(comment)}
    except Exception:
        return {"score": 0, "comment": "Assessment skipped"}
