"""Result evaluation: judge whether research results sufficiently address the goal."""

from __future__ import annotations

from typing import Callable

from backend.llm.client import LLMClient, StreamEvent
from backend.utils import parse_json_fenced

_EVALUATE_SYSTEM = """\
You are a research quality evaluator. Given a research goal and completed task results, judge whether the results sufficiently address the goal.

Consider:
1. Are all key aspects of the research goal covered?
2. Are the results substantive (real data, real analysis, not just descriptions)?
3. Are there obvious gaps, contradictions, or areas that need further investigation?

Respond with ONLY a JSON object:
If sufficient: {"satisfied": true}
If needs improvement: {"satisfied": false, "feedback": "What is lacking and what to investigate next", "suggestions": ["specific actionable task 1", "specific actionable task 2"]}
全文使用中文。"""


async def evaluate_results(
    idea: str,
    task_summaries: list[dict],
    llm_client: LLMClient,
    stream_callback: Callable | None = None,
    is_stale: Callable[[], bool] | None = None,
) -> dict:
    """Evaluate whether completed task results sufficiently address the research goal.

    Args:
        idea: The original research idea / goal.
        task_summaries: List of {"id": "1_1", "summary": "..."} dicts.
            Summaries are compact (generated during task verification).
        llm_client: LLM client for streaming.
        stream_callback: Optional callback(event_type, data) for SSE events.
        is_stale: Optional callable returning True if this run has been superseded.

    Returns:
        {"satisfied": True} or {"satisfied": False, "feedback": "...", "suggestions": [...]}
    """
    emit = stream_callback or (lambda t, d: None)
    stale = is_stale or (lambda: False)

    call_id = "Evaluate"
    emit("chunk", {"text": call_id, "call_id": call_id, "label": True})

    summaries_text = "\n".join(
        f"- **Task [{s['id']}]**: {s['summary']}" for s in task_summaries
    )

    messages = [
        {"role": "system", "content": _EVALUATE_SYSTEM},
        {"role": "user", "content": (
            f"## Research Goal\n{idea}\n\n"
            f"## Completed Task Results\n{summaries_text}"
        )},
    ]

    response = ""
    async for event in llm_client.stream(messages):
        if stale():
            break
        if event.type == "content":
            emit("chunk", {"text": event.text, "call_id": call_id})
            response += event.text
        elif event.type in ("think", "tool_call", "tool_result"):
            emit("chunk", {"text": event.call_id, "call_id": event.call_id, "label": True})
            if event.text:
                emit("chunk", {"text": event.text, "call_id": event.call_id})
        elif event.type == "tokens":
            emit("tokens", event.metadata)

    return parse_json_fenced(response, fallback={"satisfied": True})
