"""Mock mode runner — returns pre-loaded mock data for each pipeline stage."""

from mock import load_mock
from mock.stream import stream_mock


async def run_idea(idea, api_config, on_thinking=None, abort_event=None, **kwargs):
    # Return mock keywords + mock refined idea
    refine_entry = load_mock("refine-idea")
    content = refine_entry["content"] if refine_entry else ""
    if on_thinking:
        def _cb(chunk):
            if on_thinking:
                return on_thinking(chunk, None, "Refine", None)
        await stream_mock(content, _cb, abort_event)
    return {"keywords": ["research"], "papers": [], "refined_idea": content}


async def run_plan(plan, api_config, on_thinking=None, abort_event=None, **kwargs):
    # In mock mode, just return the existing plan tasks unchanged
    # (Plan mock previously ran individual LLM call mocks per task)
    return {"tasks": plan.get("tasks", [])}


async def run_task(task_id, description, input_spec, output_spec, resolved_inputs, api_config, on_thinking=None, abort_event=None, **kwargs):
    entry = load_mock("execute", task_id)
    if not entry:
        entry = load_mock("execute")
    content = entry["content"] if entry else "{}"
    if on_thinking:
        def _cb(chunk):
            if on_thinking:
                return on_thinking(chunk, task_id=task_id, operation="Execute")
        await stream_mock(content, _cb, abort_event)
    # Parse based on output type
    output_type = (output_spec.get("type") or "markdown").strip().lower()
    if output_type == "json":
        import json
        try:
            return json.loads(content)
        except Exception:
            return {"content": content}
    return content


async def run_paper(plan, outputs, api_config, format_type="markdown", on_thinking=None, abort_event=None, **kwargs):
    entry = load_mock("paper")
    content = entry["content"] if entry else ""
    if on_thinking:
        def _cb(chunk):
            if on_thinking:
                return on_thinking(chunk, None, "Paper", None)
        await stream_mock(content, _cb, abort_event)
    return content
