"""
Task Agent 单轮 LLM 实现 - 任务执行与验证。
Mock 模式依赖 test/mock-ai/execute.json，通过 llm_call / llm_call_structured 的 mock 参数注入。
Validation: LLM-based validation. Used in LLM mode only.
Agent mode uses task-output-validator skill instead.
Supports streaming via on_chunk for real-time Thinking display.
"""

import asyncio
import json
import re
from typing import Any, Callable, Dict, Optional, Tuple

import json_repair
import orjson

from llm.client import llm_call, llm_call_structured, load_prompt
from shared.constants import MAX_FORMAT_REPAIR_ATTEMPTS, TEMP_DETERMINISTIC, TEMP_RETRY, TEMP_TASK_EXECUTE
from mock import load_mock
from shared.utils import extract_codeblock

RESPONSE_TYPE = "execute"


def _get_output_type(output_spec: Dict[str, Any]) -> str:
    """Get output type from spec. Returns 'json' or 'markdown'."""
    return "json" if (output_spec.get("type") or "").strip().lower() == "json" else "markdown"



def _build_task_agent_messages(
    task_id: str,
    description: str,
    input_spec: Dict[str, Any],
    output_spec: Dict[str, Any],
    resolved_inputs: Dict[str, Any],
    idea_context: str = "",
) -> tuple[str, str]:
    """Build system prompt and user prompt for single-turn Task Agent."""
    output_format = output_spec.get("format") or ""
    output_desc = output_spec.get("description") or ""
    output_type = _get_output_type(output_spec)
    input_desc = input_spec.get("description") or ""

    system_prompt = load_prompt("task-execute.txt")

    if output_type == "json":
        system_prompt += "\n6. For structured data outputs, return a valid JSON payload; do not return a prose-only summary."

    inputs_str = "No input artifacts."
    if resolved_inputs:
        try:
            inputs_str = orjson.dumps(resolved_inputs, option=orjson.OPT_INDENT_2).decode("utf-8")
        except (TypeError, ValueError):
            inputs_str = str(resolved_inputs)

    idea_section = ""
    if idea_context:
        idea_section = f"\n**Research idea (project context):** {idea_context}\n"

    user_prompt = f"""**Task ID:** {task_id}
**Description:** {description}
{idea_section}
**Input description:** {input_desc}
**Input artifacts:**
```json
{inputs_str}
```

**Output description:** {output_desc}
**Output format:** {output_format}

Produce the output now. You may reason first; then output the result."""

    return system_prompt, user_prompt


def _parse_task_agent_output(content: str, output_type: str) -> Any:
    """Parse Task Agent output. output_type is 'json' or 'markdown'."""
    content = (content or "").strip()
    if not content:
        raise ValueError("LLM returned empty response")
    if output_type == "json":
        cleaned = extract_codeblock(content) or content
        if not cleaned or not cleaned.strip().startswith(("{", "[")):
            obj_match = re.search(r"[\{\[][\s\S]*[\}\]]", content)
            if obj_match:
                cleaned = obj_match.group(0)
        try:
            parsed = json_repair.loads(cleaned)
        except Exception as e:
            raise ValueError(f"Failed to parse JSON from LLM response: {e}") from e
        if isinstance(parsed, str):
            raise ValueError("JSON output must be object/array, not a prose string")
        return parsed
    # Markdown: strip reasoning prefix if present
    if "\n\n" in content and len(content.split("\n\n", 1)[0]) < 300:
        return content.split("\n\n", 1)[1].strip()
    return content


async def execute_task(
    task_id: str,
    description: str,
    input_spec: Dict[str, Any],
    output_spec: Dict[str, Any],
    resolved_inputs: Dict[str, Any],
    api_config: Optional[Dict[str, Any]] = None,
    abort_event: Optional[Any] = None,
    on_thinking: Optional[Callable[[str, Optional[str], Optional[str]], None]] = None,
    idea_id: Optional[str] = None,
    plan_id: Optional[str] = None,
    idea_context: str = "",
) -> Any:
    """
    Execute task via single-turn LLM. Returns parsed output (dict for JSON, str for Markdown).
    """
    raw_cfg = api_config or {}
    output_type = _get_output_type(output_spec)

    mock = None
    if raw_cfg.get("taskUseMock", True):
        entry = load_mock(RESPONSE_TYPE, task_id, extra_fallback_key="_default_markdown" if output_type != "json" else "")
        if not entry:
            raise ValueError(f"No mock data for {RESPONSE_TYPE}/{task_id}")
        mock = entry["content"]
    system_prompt, user_prompt = _build_task_agent_messages(
        task_id, description, input_spec, output_spec, resolved_inputs, idea_context
    )
    stream = on_thinking is not None

    def _on_chunk(chunk: str):
        if on_thinking and chunk:
            return on_thinking(chunk, task_id=task_id, operation="Execute")

    if output_type == "json":
        temperatures = [TEMP_TASK_EXECUTE] + [TEMP_RETRY] * max(0, MAX_FORMAT_REPAIR_ATTEMPTS - 1)
        parsed, _raw = await llm_call_structured(
            system=system_prompt,
            user=user_prompt,
            api_config=raw_cfg,
            parse_fn=lambda text: _parse_task_agent_output(text, "json"),
            temperatures=temperatures,
            on_chunk=_on_chunk if stream else None,
            abort_event=abort_event,
            mock=mock,
        )
        return parsed

    content = await llm_call(
        system=system_prompt,
        user=user_prompt,
        api_config=raw_cfg,
        temperature=TEMP_TASK_EXECUTE,
        on_chunk=_on_chunk if stream else None,
        abort_event=abort_event,
        mock=mock,
    )
    return _parse_task_agent_output(content, "markdown")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _get_content_str(result: Any) -> str:
    """Extract content as string for validation."""
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        if "content" in result:
            c = result["content"]
            return c if isinstance(c, str) else json.dumps(c)
        return json.dumps(result)
    return str(result)


# L1: Execution-mode structural mismatch — the current delivery channel is fundamentally
# incapable of producing the artifact form required by the contract (e.g., returning a live
# sklearn Pipeline via a JSON text channel).
_CONTRACT_MISMATCH_MARKERS = (
    "cannot be serialized to json",
    "not json-serializable",
    "live python object",
    "live sklearn",
    "live model instance",
    "live pipeline instance",
    "in-memory object cannot",
    "in-memory model",
    "requires pickling",
    "requires live",
    "not a serializable",
    "cannot serialize the pipeline",
    "cannot serialize the model",
    "delivery mode mismatch",
    "mode cannot produce",
    # File-path vs. in-memory object: task returned a file path when the contract
    # requires an in-memory object (ndarray, DataFrame, etc.). This is a structural
    # delivery-mode mismatch, not a transient failure — reframe is the right action.
    "string path instead of",
    "file path instead of",
    "file paths instead of",
    "only file paths provided",
    "provided as a string path",
    "path instead of ndarray",
    "path instead of array",
    "path instead of dataframe",
    "received string path",
    "received file path",
)


def classify_validation_failure(report: str, output_format: str = "") -> dict:
    """Best-effort local classification for retry policy decisions."""
    text = f"{output_format}\n{report or ''}".lower()
    if not text.strip():
        return {"category": "semantic", "retryable": True}

    terminal_markers = (
        "cannot be implemented",
        "not feasible",
        "infeasible",
        "unachievable",
        "impossible under",
        "objective is impossible",
    )
    if any(marker in text for marker in terminal_markers):
        return {"category": "terminal_unachievable", "retryable": False}

    # L1: execution-mode structural mismatch (detected by explicit signal in report)
    if any(marker in text for marker in _CONTRACT_MISMATCH_MARKERS):
        return {"category": "contract_mismatch", "retryable": True}

    format_markers = (
        "failed to parse",
        "invalid json",
        "expected numerical array",
        "expected numerical array/time-series",
        "expected numerical array or time-series object",
        "received text description",
        "received metadata json",
        "output format: fail",
        "prose-only",
        "content wrapper",
    )
    evidence_markers = (
        "data not provided",
        "no data provided",
        "no spectral analysis or data provided",
        "claimed match, but data not provided",
        "no visual or quantitative evidence provided",
        "no n/a",
    )

    if any(marker in text for marker in format_markers):
        return {"category": "format", "retryable": True}
    if any(marker in text for marker in evidence_markers):
        return {"category": "evidence_missing", "retryable": True}
    return {"category": "semantic", "retryable": True}


def _parse_validation_response(text: str) -> dict:
    """Parse validation JSON from LLM response. Raises on failure to trigger retry."""
    cleaned = extract_codeblock(text) or (text or "").strip()
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict) or "passed" not in parsed:
        raise ValueError("Validation response must be a JSON object with 'passed' field")
    return parsed


async def _run_validation_llm(
    *,
    system_prompt: str,
    user_message: str,
    task_id: str,
    label: str,
    api_config: Optional[Dict],
    abort_event: Optional[Any],
    on_thinking: Optional[Callable[[str, Optional[str], Optional[str], Optional[dict]], None]],
) -> Tuple[bool, str]:
    """Shared LLM validation pipeline: call LLM, extract JSON, return (passed, report)."""

    def _stream_chunk(chunk: str):
        if on_thinking and chunk:
            r = on_thinking(chunk, task_id=task_id, operation="Validate", schedule_info=None)
            if asyncio.iscoroutine(r):
                return r

    try:
        parsed, _raw = await llm_call_structured(
            system=system_prompt,
            user=user_message,
            api_config=api_config or {},
            parse_fn=_parse_validation_response,
            temperatures=[TEMP_DETERMINISTIC, TEMP_DETERMINISTIC],
            on_chunk=_stream_chunk if on_thinking else None,
            abort_event=abort_event,
        )
        passed = bool(parsed.get("passed"))
        report = parsed.get("report") or f"# Validating Task {task_id}\n\n**Result: {'PASS' if passed else 'FAIL'}** ({label})"
        return passed, report
    except Exception as e:
        report = f"# Validating Task {task_id}\n\n**Result: FAIL**\n\n{label} error: {e}"
        return False, report


async def validate_task_output_with_llm(
    result: Any,
    output_spec: Dict[str, Any],
    task_id: str,
    validation_spec: Optional[Dict[str, Any]] = None,
    api_config: Optional[Dict] = None,
    abort_event: Optional[Any] = None,
    on_thinking: Optional[Callable[[str, Optional[str], Optional[str], Optional[dict]], None]] = None,
) -> Tuple[bool, str]:
    """
    Use LLM to validate task output against criteria.
    Returns (passed, report_markdown).
    Called only in LLM mode; Agent mode uses task-output-validator skill.
    """
    content = _get_content_str(result)
    validation = validation_spec or {}
    criteria = validation.get("criteria") or []
    output_format = (output_spec or {}).get("format") or ""

    system_prompt = load_prompt("task-validate.txt")

    criteria_text = "\n".join(f"- {c}" for c in criteria) if criteria else "Output should be complete and align with the task description."
    user_message = f"""Task ID: {task_id}
Output format expected: {output_format}

Validation criteria:
{criteria_text}

Task output to validate:
```
{content[:8000]}
```

Output your reasoning first, then the JSON block."""

    return await _run_validation_llm(
        system_prompt=system_prompt,
        user_message=user_message,
        task_id=task_id,
        label="LLM validation",
        api_config=api_config,
        abort_event=abort_event,
        on_thinking=on_thinking,
    )


async def validate_task_output_with_readonly_agent(
    result: Any,
    output_spec: Dict[str, Any],
    task_id: str,
    validation_spec: Optional[Dict[str, Any]] = None,
    validation_context: Optional[Dict[str, Any]] = None,
    api_config: Optional[Dict] = None,
    abort_event: Optional[Any] = None,
    on_thinking: Optional[Callable[[str, Optional[str], Optional[str], Optional[dict]], None]] = None,
) -> Tuple[bool, str]:
    """Read-only validation agent.

    This validator is intentionally isolated from execution concerns:
    it can reason from provided context and output content only,
    and must not propose file writes or command execution.
    """
    content = _get_content_str(result)
    validation = validation_spec or {}
    criteria = validation.get("criteria") or []
    output_format = (output_spec or {}).get("format") or ""
    context = validation_context or {}

    system_prompt = load_prompt("task-validate-readonly.txt")

    criteria_text = "\n".join(f"- {c}" for c in criteria) if criteria else "Output should be complete and align with the task description."
    context_text = json.dumps(context, ensure_ascii=False)[:4000]
    user_message = f"""Task ID: {task_id}
Output format expected: {output_format}

Validation context (read-only):
```json
{context_text}
```

Validation criteria:
{criteria_text}

Task output to validate:
```
{content[:8000]}
```

Output your reasoning first, then the JSON block."""

    return await _run_validation_llm(
        system_prompt=system_prompt,
        user_message=user_message,
        task_id=task_id,
        label="Read-only validation agent",
        api_config=api_config,
        abort_event=abort_event,
        on_thinking=on_thinking,
    )
