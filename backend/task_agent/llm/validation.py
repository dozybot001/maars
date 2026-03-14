"""
Task output validation - LLM-based validation. Used in LLM mode only.
Agent mode uses task-output-validator skill instead.
Supports streaming via on_chunk for real-time Thinking display.
"""

import asyncio
import json
import re
from typing import Any, Callable, Dict, Optional, Tuple

from shared.constants import TEMP_DETERMINISTIC
from shared.llm_client import chat_completion, merge_phase_config


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


def _normalize_criteria_for_format(criteria: list[str], output_format: str) -> tuple[list[str], str]:
    """Normalize criteria that are impossible under strict JSON serialization."""
    if not criteria:
        return [], ""

    fmt = (output_format or "").strip().upper()
    is_json = fmt.startswith("JSON") or "JSON" in fmt
    is_structured_artifact = any(
        token in fmt
        for token in ("ARRAY", "OBJECT", "DICT", "TABLE", "CSV", "TIME-SERIES", "TIME SERIES", "MATRIX", "TENSOR")
    )
    if not is_json:
        if not is_structured_artifact:
            return criteria, ""
        normalized = []
        for c in criteria:
            c_lower = c.lower()
            if (
                "signal length" in c_lower
                or "frequency spectrum" in c_lower
                or "baseline drift" in c_lower
                or "nan" in c_lower
                or "infinite" in c_lower
                or "time-series object" in c_lower
                or "numerical array" in c_lower
            ):
                normalized.append(
                    "For structured artifact-backed output, provide a loadable data artifact path plus enough evidence to validate the requirement: shape/length, dtype, no-NaN/Inf checks, and any quantitative spectral or filtering evidence required by the task."
                )
                continue
            normalized.append(c)
        validator_note = (
            "Structured outputs may be returned as artifact references plus validation evidence. "
            "Do not fail solely because the raw numeric payload is not embedded inline when the output provides a loadable artifact and concrete verification metadata."
        )
        return normalized, validator_note

    normalized: list[str] = []
    for c in criteria:
        c_lower = c.lower()
        if (
            "initialized model" in c_lower
            or "initialized instance" in c_lower
            or "programmatic object" in c_lower
            or "ready for the training phase" in c_lower
            or "ready for training" in c_lower
        ):
            normalized.append(
                (
                    "For JSON output, represent trainable models in a JSON-serializable way: "
                    "either class/import path + constructor parameters, or references to serialized "
                    "model artifacts (e.g., .pkl/.joblib) that can be loaded for training."
                )
            )
            continue

        # JSON cannot embed live ndarray objects; require executable array references instead.
        if (
            "numpy array" in c_lower
            or "ndarray" in c_lower
            or "shape (n_samples" in c_lower
            or "shape(n_samples" in c_lower
            or "shape of x" in c_lower
            or "rows (samples) in x" in c_lower
            or "x must be" in c_lower and "array" in c_lower
            or "y must be" in c_lower and "array" in c_lower
        ):
            normalized.append(
                (
                    "For JSON output, represent arrays as loadable artifacts and metadata, "
                    "not inline in-memory ndarrays: include file path(s) (.npy/.npz), "
                    "array key names when using .npz, shape, dtype, and sample-count alignment "
                    "(e.g., X_rows == y_rows). If available, include a validation summary that "
                    "confirms numeric data with no NaN/Inf."
                )
            )
            continue
        normalized.append(c)

    validator_note = (
        "JSON output cannot contain live in-memory Python objects. "
        "Do not fail solely because literal instances/ndarrays are not embedded in JSON. "
        "Pass when output provides a practical, executable representation for downstream use "
        "(for example, artifact references plus shape/dtype/consistency metadata)."
    )
    return normalized, validator_note


def classify_validation_failure(report: str, output_format: str = "") -> dict:
    """Best-effort local classification for retry policy decisions."""
    text = f"{output_format}\n{report or ''}".lower()
    if not text.strip():
        return {"category": "semantic", "retryable": True}

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
    When on_thinking provided, streams LLM output for real-time Thinking display.
    """
    content = _get_content_str(result)
    validation = validation_spec or {}
    criteria = validation.get("criteria") or []
    output_format = (output_spec or {}).get("format") or ""
    normalized_criteria, validator_note = _normalize_criteria_for_format(criteria, output_format)

    policy_note = validator_note or "Apply criteria exactly as provided."
    system_prompt = (
        "You are a validation assistant. Judge whether the task output meets the validation criteria.\n\n"
        "Output in two parts:\n"
        "1. **Reasoning** (1-2 sentences): Briefly explain your validation analysis. This will be shown as your thinking process.\n"
        "2. **JSON**: Output a JSON block in ```json and ``` with: {\"passed\": true|false, \"report\": \"markdown string\"}\n"
        "The report should list each criterion and PASS/FAIL, then a final Result line.\n\n"
        f"Validation policy note:\n{policy_note}"
    )

    criteria_text = "\n".join(f"- {c}" for c in normalized_criteria) if normalized_criteria else "Output should be complete and align with the task description."
    user_message = f"""Task ID: {task_id}
Output format expected: {output_format}

Validation criteria:
{criteria_text}

Task output to validate:
```
{content[:8000]}
```

Output your reasoning first, then the JSON block."""

    def _stream_chunk(chunk: str):
        """转发 chunk 到 on_thinking，若为 async 则返回 coroutine 供 chat_completion await。"""
        if on_thinking and chunk:
            r = on_thinking(chunk, task_id=task_id, operation="Validate", schedule_info=None)
            if asyncio.iscoroutine(r):
                return r

    try:
        cfg = merge_phase_config(api_config or {}, "validate")
        stream = on_thinking is not None
        # 不使用 response_format，以便 LLM 先输出 reasoning 再输出 JSON（Thinking 显示推理）
        response = await chat_completion(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            cfg,
            on_chunk=_stream_chunk if stream else None,
            abort_event=abort_event,
            stream=stream,
            temperature=TEMP_DETERMINISTIC,
        )
        text = response if isinstance(response, str) else (response.get("content") or "")
        # 从 reasoning + ```json...``` 中提取 JSON，若无代码块则尝试整体解析
        cleaned = (text or "").strip()
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
        if m:
            cleaned = m.group(1).strip()
        try:
            parsed = json.loads(cleaned) if cleaned else {}
        except (json.JSONDecodeError, TypeError):
            parsed = {}
        passed = bool(parsed.get("passed"))
        report = parsed.get("report") or f"# Validating Task {task_id}\n\n**Result: {'PASS' if passed else 'FAIL'}** (LLM validation)"
        return passed, report
    except Exception as e:
        report = f"# Validating Task {task_id}\n\n**Result: FAIL**\n\nLLM validation error: {e}"
        return False, report
