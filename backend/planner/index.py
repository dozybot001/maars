"""
Planner module - verify, decompose, format flow.
Uses real LLM by default; Mock AI when use_mock=True.
"""

import asyncio
import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .llm_client import chat_completion as real_chat_completion
from test.mock_stream import mock_chat_completion

PLANNER_DIR = Path(__file__).parent
MOCK_AI_DIR = PLANNER_DIR.parent / "test" / "mock-ai"
MAX_DECOMPOSE_DEPTH = 5
MAX_CONCURRENT_CALLS = 10

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
            _mock_cache[response_type] = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
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
        content_str = json.dumps(content, ensure_ascii=False)
    return {"content": content_str, "reasoning": entry.get("reasoning", "")}


# Operation labels for thinking display
_OP_LABELS = {"verify": "Verify", "decompose": "Decompose", "format": "Format"}


def _build_user_message(response_type: str, task: Dict) -> str:
    tid = task.get("task_id", "")
    desc = task.get("description", "")
    if response_type == "verify":
        return f'Input: task_id "{tid}", description "{desc}"\nOutput:'
    if response_type == "decompose":
        return f'**Input:** task_id "{tid}", description "{desc}"\n\n**Output:**'
    if response_type == "format":
        return f'**Input task:** task_id "{tid}", description "{desc}"\n\n**Output:**'
    return f"Task: {tid} - {desc}"


async def _call_chat_completion(
    on_thinking: Callable[..., None],
    context: Dict,
    abort_event: Optional[Any],
    stream: bool = True,
    use_mock: bool = False,
    api_config: Optional[Dict] = None,
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
    prompt_file = {"verify": "verify-prompt.txt", "decompose": "decompose-prompt.txt", "format": "format-prompt.txt"}[response_type]
    system_prompt = _get_prompt_cached(prompt_file)
    user_message = _build_user_message(response_type, task)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    cfg = api_config or {}
    effective_on_chunk = stream_chunk if (stream and on_thinking) else None
    async with _get_call_semaphore():
        return await real_chat_completion(
            messages,
            cfg,
            on_chunk=effective_on_chunk,
            abort_event=abort_event,
            stream=stream,
        )


def _parse_json_response(text: str) -> Any:
    """Parse JSON from AI response with fallback for common malformations."""
    cleaned = (text or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if m:
        cleaned = m.group(1).strip()

    def _try_parse(s: str) -> Any:
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass
        # Fix trailing commas (common AI output malformation)
        s = re.sub(r",\s*}", "}", s)
        s = re.sub(r",\s*]", "]", s)
        try:
            return json.loads(s)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON from AI response: {e}") from e

    return _try_parse(cleaned)


async def _decompose_task(
    parent_task: Dict,
    on_thinking: Callable[[str], None],
    abort_event: Optional[Any],
    use_mock: bool = False,
    api_config: Optional[Dict] = None,
) -> List[Dict]:
    content = await _call_chat_completion(
        on_thinking,
        {"type": "decompose", "taskId": parent_task["task_id"], "task": parent_task},
        abort_event,
        stream=True,
        use_mock=use_mock,
        api_config=api_config,
    )
    result = _parse_json_response(content)
    tasks = result.get("tasks") or []
    return [
        t
        for t in tasks
        if t.get("task_id") and t.get("description") and isinstance(t.get("dependencies"), list)
    ]


async def _verify_task(
    task: Dict,
    on_thinking: Callable[[str], None],
    abort_event: Optional[Any],
    use_mock: bool = False,
    api_config: Optional[Dict] = None,
) -> Dict:
    content = await _call_chat_completion(
        on_thinking,
        {"type": "verify", "taskId": task["task_id"], "task": task},
        abort_event,
        stream=False,
        use_mock=use_mock,
        api_config=api_config,
    )
    result = _parse_json_response(content)
    return {"atomic": bool(result.get("atomic"))}


async def _format_task(
    task: Dict,
    on_thinking: Callable[[str], None],
    abort_event: Optional[Any],
    use_mock: bool = False,
    api_config: Optional[Dict] = None,
) -> Optional[Dict]:
    content = await _call_chat_completion(
        on_thinking,
        {"type": "format", "taskId": task["task_id"], "task": task},
        abort_event,
        stream=True,
        use_mock=use_mock,
        api_config=api_config,
    )
    result = _parse_json_response(content)
    if result.get("input") and result.get("output"):
        return {"input": result["input"], "output": result["output"]}
    return None


async def _verify_and_decompose_recursive(
    task: Dict,
    all_tasks: List[Dict],
    on_task: Optional[Callable[[Dict], None]],
    on_thinking: Callable[[str], None],
    depth: int,
    check_aborted: Callable[[], bool],
    abort_event: Optional[Any],
    on_tasks_batch: Optional[Callable[[List[Dict], Dict, List[Dict]], None]] = None,
    use_mock: bool = False,
    api_config: Optional[Dict] = None,
) -> None:
    if check_aborted and check_aborted():
        raise asyncio.CancelledError("Aborted")

    if depth >= MAX_DECOMPOSE_DEPTH:
        io_result = await _format_task(task, on_thinking, abort_event, use_mock, api_config)
        if not io_result:
            raise ValueError(f"Format failed for task {task['task_id']} at max depth: missing input/output")
        idx = next((i for i, t in enumerate(all_tasks) if t.get("task_id") == task["task_id"]), -1)
        if idx >= 0:
            all_tasks[idx] = {**all_tasks[idx], **io_result}
        return

    v = await _verify_task(task, on_thinking, abort_event, use_mock, api_config)
    atomic = v["atomic"]

    if atomic:
        io_result = await _format_task(task, on_thinking, abort_event, use_mock, api_config)
        if not io_result:
            raise ValueError(f"Format failed for atomic task {task['task_id']}: missing input/output")
        idx = next((i for i, t in enumerate(all_tasks) if t.get("task_id") == task["task_id"]), -1)
        if idx >= 0:
            all_tasks[idx] = {**all_tasks[idx], **io_result}
        return

    children = await _decompose_task(task, on_thinking, abort_event, use_mock, api_config)
    if not children:
        raise ValueError(f"Decompose returned no children for task {task['task_id']}")

    all_tasks.extend(children)
    if on_tasks_batch:
        on_tasks_batch(children, task, list(all_tasks))
    elif on_task:
        for t in children:
            on_task(t)

    await asyncio.gather(*[
        _verify_and_decompose_recursive(
            child, all_tasks, on_task, on_thinking, depth + 1, check_aborted, abort_event, on_tasks_batch,
            use_mock, api_config,
        )
        for child in children
    ])


async def run_plan(
    plan: Dict,
    on_task: Optional[Callable[[Dict], None]],
    on_thinking: Callable[[str], None],
    abort_event: Optional[Any] = None,
    on_tasks_batch: Optional[Callable[[List[Dict], Dict, List[Dict]], None]] = None,
    use_mock: bool = False,
    api_config: Optional[Dict] = None,
) -> Dict:
    """Run verify->decompose->format from root task, top-down to all atomic tasks."""

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
    await _verify_and_decompose_recursive(
        root_task, all_tasks, on_task, on_thinking_fn, 0, check_aborted, abort_event, on_tasks_batch,
        use_mock=use_mock, api_config=api_config,
    )
    return {"tasks": all_tasks}
