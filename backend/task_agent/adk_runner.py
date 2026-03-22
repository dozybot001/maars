"""
Task Agent - Google ADK 驱动实现。
当 taskAgentMode=True 时使用，替代自实现 ReAct 循环。
"""

from typing import Any, Callable, Dict, Optional

from shared.utils import parse_json_response

from adk.runner import run_agent
from db import ensure_execution_task_dirs, ensure_sandbox_dir
from shared.adk_bridge import prepare_api_env
from shared.constants import TASK_AGENT_MAX_TURNS
from shared.constants import TASK_AGENT_CONTEXT_TARGET_TOKENS
from shared.constants import TEMP_STRUCTURED
from llm.client import llm_call

from .agent_tools import TOOLS, execute_tool


from .adk_prompt import (
    _build_system_prompt,
    _build_user_message,
    _estimate_tokens,
    _truncate_string,
    _shrink_for_prompt,
)


def _is_json_output(output_spec: dict) -> bool:
    return (output_spec.get("type") or "").strip().lower() == "json"


def _parse_task_agent_output(content: str, use_json_mode: bool) -> Any:
    """Parse Task Agent output to final result."""
    content = (content or "").strip()
    if not content:
        raise ValueError("LLM returned empty response")
    if use_json_mode:
        try:
            return parse_json_response(content)
        except Exception as e:
            raise ValueError(f"Failed to parse JSON from LLM response: {e}") from e
    return content


def _safe_json_loads(raw: str) -> Any:
    try:
        return parse_json_response(raw)
    except Exception:
        return None


def _validate_compressed_object_shape(original: Any, compressed: Any, label: str) -> tuple[bool, str]:
    if compressed is None:
        return False, "compressed payload is None"
    if label in ("resolved_inputs", "execution_context"):
        if isinstance(original, dict) and isinstance(compressed, dict):
            # keep critical top-level keys when present
            for key in ("globalGoal", "planContext", "taskContract", "retryMemory"):
                if key in original and key not in compressed:
                    return False, f"missing required top-level key: {key}"
            return True, "ok"
        if isinstance(original, dict) and not isinstance(compressed, dict):
            return False, "compressed payload must remain object for dict input"
    return True, "ok"


async def _compress_object_with_llm(
    value: Any,
    *,
    label: str,
    target_tokens: int,
    api_config: Dict[str, Any],
    abort_event: Optional[Any],
) -> tuple[Any, dict]:
    import orjson

    if value is None:
        return value, {
            "mode": "empty",
            "originalTokensEst": 0,
            "compressedTokensEst": 0,
            "valid": True,
        }

    try:
        original_text = orjson.dumps(value, option=orjson.OPT_INDENT_2).decode("utf-8")
    except Exception:
        original_text = str(value)
    original_tokens = _estimate_tokens(original_text)

    if original_tokens <= target_tokens:
        return value, {
            "mode": "passthrough",
            "originalTokensEst": original_tokens,
            "compressedTokensEst": original_tokens,
            "valid": True,
        }

    system_prompt = (
        "You are a strict JSON context compressor. "
        "Compress large JSON context while preserving task-critical semantics. "
        "Output JSON only."
    )
    user_prompt = f"""
Label: {label}
Target token budget: <= {target_tokens}

Return JSON object with exact shape:
{{
  "compressed": <json object/array/string>,
  "notes": ["short note", "..."]
}}

Rules:
1) Preserve goals, constraints, task contract, retry failures, and actionable next steps.
2) Remove repetitive logs and oversized raw payloads by replacing them with concise semantic summaries.
3) Keep keys stable when possible.
4) Never output markdown.

Input JSON:
{original_text}
"""

    try:
        resp = await llm_call(
            system=system_prompt,
            user=user_prompt,
            api_config=api_config or {},
            temperature=TEMP_STRUCTURED,
            json_output=True,
            abort_event=abort_event,
        )
        parsed = _safe_json_loads(resp)
        compressed = (parsed or {}).get("compressed") if isinstance(parsed, dict) else None
        ok, reason = _validate_compressed_object_shape(value, compressed, label)
        if ok:
            try:
                compressed_text = orjson.dumps(compressed, option=orjson.OPT_INDENT_2).decode("utf-8")
            except Exception:
                compressed_text = str(compressed)
            return compressed, {
                "mode": "llm",
                "originalTokensEst": original_tokens,
                "compressedTokensEst": _estimate_tokens(compressed_text),
                "valid": True,
                "reason": "ok",
            }
        fallback = _shrink_for_prompt(value, max_depth=5, max_items=40, max_str_chars=1800)
        try:
            fallback_text = orjson.dumps(fallback, option=orjson.OPT_INDENT_2).decode("utf-8")
        except Exception:
            fallback_text = str(fallback)
        return fallback, {
            "mode": "fallback",
            "originalTokensEst": original_tokens,
            "compressedTokensEst": _estimate_tokens(fallback_text),
            "valid": False,
            "reason": reason,
        }
    except Exception as e:
        fallback = _shrink_for_prompt(value, max_depth=5, max_items=40, max_str_chars=1800)
        try:
            fallback_text = orjson.dumps(fallback, option=orjson.OPT_INDENT_2).decode("utf-8")
        except Exception:
            fallback_text = str(fallback)
        return fallback, {
            "mode": "fallback",
            "originalTokensEst": original_tokens,
            "compressedTokensEst": _estimate_tokens(fallback_text),
            "valid": False,
            "reason": f"llm_error: {e}",
        }


async def run_task_agent_adk(
    task_id: str,
    description: str,
    input_spec: Dict[str, Any],
    output_spec: Dict[str, Any],
    resolved_inputs: Dict[str, Any],
    api_config: Dict[str, Any],
    abort_event: Optional[Any],
    on_thinking: Optional[Callable[[str, Optional[str], Optional[str]], None]],
    idea_id: str,
    plan_id: str,
    execution_run_id: str = "",
    docker_container_name: str = "",
    validation_spec: Optional[Dict[str, Any]] = None,
    idea_context: str = "",
    execution_context: Optional[Dict[str, Any]] = None,
    on_prompt_built: Optional[Callable[[Dict[str, Any]], Any]] = None,
) -> Any:
    """
    使用 Google ADK Runner 运行 Task Agent。
    返回任务输出 (dict 或 str)。
    """
    prepare_api_env(api_config)

    if idea_id and plan_id and task_id and execution_run_id:
        await ensure_execution_task_dirs(execution_run_id, task_id)
    elif idea_id and plan_id and task_id:
        await ensure_sandbox_dir(idea_id, plan_id, task_id)

    output_format = output_spec.get("format") or ""
    use_json_mode = _is_json_output(output_spec)
    on_thinking_fn = on_thinking or (lambda *a, **_: None)

    compressed_inputs, _inputs_compress_meta = await _compress_object_with_llm(
        resolved_inputs,
        label="resolved_inputs",
        target_tokens=max(4000, int(TASK_AGENT_CONTEXT_TARGET_TOKENS * 0.45)),
        api_config=api_config,
        abort_event=abort_event,
    )
    compressed_execution_context, _context_compress_meta = await _compress_object_with_llm(
        execution_context,
        label="execution_context",
        target_tokens=max(3000, int(TASK_AGENT_CONTEXT_TARGET_TOKENS * 0.35)),
        api_config=api_config,
        abort_event=abort_event,
    )

    # Capture the real parsed task output from execute_tool (Finish handler).
    # run_agent's finish_result only sees the generic success message we return,
    # so we side-channel the actual value here.
    task_output: list = [None]

    async def executor_fn(name: str, args_str: str) -> tuple[bool, str]:
        out, tool_result = await execute_tool(
            name,
            args_str,
            idea_id,
            plan_id,
            task_id,
            execution_run_id=execution_run_id,
            docker_container_name=docker_container_name,
            output_format=output_format,
        )
        if out is not None:
            task_output[0] = out
            return True, '{"status": "success", "message": "Task completed."}'
        return False, tool_result

    system_prompt = _build_system_prompt(output_format, validation_spec, idea_context)

    user_message, _context_budget = _build_user_message(
        task_id=task_id,
        description=description,
        input_spec=input_spec,
        resolved_inputs=compressed_inputs,
        output_spec=output_spec,
        output_format=output_format,
        validation_spec=validation_spec,
        idea_context=idea_context,
        execution_context=compressed_execution_context,
    )

    if on_prompt_built is not None:
        payload = {
            "taskId": task_id,
            "outputFormat": output_format,
            "systemPrompt": system_prompt,
            "userMessage": user_message,
            "contextBudget": _context_budget,
            "compression": {
                "resolvedInputs": _inputs_compress_meta,
                "executionContext": _context_compress_meta,
            },
        }
        maybe = on_prompt_built(payload)
        if hasattr(maybe, "__await__"):
            await maybe

    _, turn_count = await run_agent(
        name="task",
        prompt=system_prompt,
        user_message=user_message,
        tools=TOOLS,
        executor_fn=executor_fn,
        api_config=api_config,
        max_turns=TASK_AGENT_MAX_TURNS,
        finish_tool="Finish",
        operation="Execute",
        on_thinking=on_thinking_fn,
        abort_event=abort_event,
        task_id=task_id,
    )

    if task_output[0] is not None:
        return task_output[0]

    raise ValueError(
        f"Agent reached max turns ({TASK_AGENT_MAX_TURNS}) without calling Finish"
    )
