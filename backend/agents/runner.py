"""Agent mode runner — runs research pipeline stages via Google ADK agents."""


async def run_idea(idea, api_config, limit=10, on_thinking=None, abort_event=None, **kwargs):
    from agents.idea import run
    return await run(idea, api_config, limit, on_thinking, abort_event)


async def run_plan(plan, api_config, on_thinking=None, abort_event=None, on_tasks_batch=None, idea_id=None, plan_id=None, **kwargs):
    from agents.plan import run
    return await run(plan, on_thinking, abort_event, on_tasks_batch, api_config, idea_id, plan_id)


async def run_task(task_id, description, input_spec, output_spec, resolved_inputs, api_config, **kwargs):
    from agents.task import run
    return await run(task_id=task_id, description=description, input_spec=input_spec, output_spec=output_spec, resolved_inputs=resolved_inputs, api_config=api_config, **kwargs)


async def run_paper(plan, outputs, api_config, format_type="markdown", on_thinking=None, abort_event=None, **kwargs):
    from agents.paper import run
    return await run(plan, outputs, api_config, format_type, on_thinking, abort_event)
