"""
LLM-based task executor. Generates output from task description and input artifacts.
Supports mock mode (useMock=True): returns simulated output without LLM calls.
Supports streaming via on_thinking callback for real-time output display.
"""

import re
from typing import Any, Callable, Dict, Optional

import orjson
import json_repair

from planner.llm_client import chat_completion, merge_phase_config


def _mock_execute(output_format: str, task_id: str, on_thinking: Optional[Callable] = None) -> Any:
    """Return simulated output for mock mode. No LLM call. Optionally streams to on_thinking."""
    if _is_json_format(output_format):
        result = {"_mock": True, "task_id": task_id, "note": "Simulated output (Mock AI mode)"}
        if on_thinking:
            for chunk in _chunk_string(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode("utf-8"), 20):
                on_thinking(chunk, task_id=task_id, operation="Execute")
        return result
    text = f"# Mock Output\n\nSimulated content for task {task_id}.\n\n(Mock AI mode)"
    if on_thinking:
        for chunk in _chunk_string(text, 20):
            on_thinking(chunk, task_id=task_id, operation="Execute")
    return text


def _chunk_string(s: str, size: int):
    """Yield string in chunks for simulated streaming."""
    for i in range(0, len(s), size):
        yield s[i : i + size]


def _is_json_format(output_format: str) -> bool:
    """Check if output format expects JSON."""
    if not output_format:
        return False
    fmt = output_format.strip().upper()
    return fmt.startswith("JSON") or "JSON" in fmt


async def execute_task(
    task_id: str,
    description: str,
    input_spec: Dict[str, Any],
    output_spec: Dict[str, Any],
    resolved_inputs: Dict[str, Any],
    api_config: Optional[Dict[str, Any]] = None,
    abort_event: Optional[Any] = None,
    on_thinking: Optional[Callable[[str, Optional[str], Optional[str]], None]] = None,
) -> Any:
    """
    Execute task via LLM. Returns parsed output (dict for JSON, str for Markdown).
    When useMock=True in api_config, returns simulated output without LLM call.
    """
    raw_cfg = api_config or {}
    if raw_cfg.get("useMock") or raw_cfg.get("use_mock"):
        output_format = (output_spec or {}).get("format") or ""
        return _mock_execute(output_format, task_id, on_thinking)

    api_config = merge_phase_config(raw_cfg, "execute")
    output_format = output_spec.get("format") or ""
    output_desc = output_spec.get("description") or ""
    input_desc = input_spec.get("description") or ""

    system_prompt = """You are a research task executor. Your job is to complete a single atomic task and produce output in the exact format specified.

Rules:
1. Use only the provided input artifacts and task description.
2. Output must strictly conform to the specified format.
3. For JSON: output valid JSON only, no extra text or markdown fences.
4. For Markdown: output the document content directly."""

    inputs_str = "No input artifacts."
    if resolved_inputs:
        try:
            inputs_str = orjson.dumps(resolved_inputs, option=orjson.OPT_INDENT_2).decode("utf-8")
        except (TypeError, ValueError):
            inputs_str = str(resolved_inputs)

    user_prompt = f"""**Task ID:** {task_id}
**Description:** {description}

**Input description:** {input_desc}
**Input artifacts:**
```json
{inputs_str}
```

**Output description:** {output_desc}
**Output format:** {output_format}

Produce the output now. Output ONLY the result, no explanation."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    use_json_mode = _is_json_format(output_format)
    response_format = {"type": "json_object"} if use_json_mode else None
    stream = on_thinking is not None

    def _on_chunk(chunk: str) -> None:
        if on_thinking and chunk:
            on_thinking(chunk, task_id=task_id, operation="Execute")

    content = await chat_completion(
        messages,
        api_config,
        on_chunk=_on_chunk if stream else None,
        abort_event=abort_event,
        stream=stream,
        temperature=0.3,
        response_format=response_format,
    )

    content = (content or "").strip()
    if not content:
        raise ValueError("LLM returned empty response")

    if use_json_mode:
        cleaned = content
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
        if m:
            cleaned = m.group(1).strip()
        try:
            return json_repair.loads(cleaned)
        except Exception as e:
            raise ValueError(f"Failed to parse JSON from LLM response: {e}") from e

    return content
