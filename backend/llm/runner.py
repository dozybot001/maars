"""LLM mode runner — runs research pipeline stages via single-round LLM calls."""


async def run_idea(idea, api_config, limit=10, on_thinking=None, abort_event=None):
    from llm.idea import run_idea_llm
    return await run_idea_llm(idea, api_config, limit, on_thinking, abort_event)


async def run_plan(plan, api_config, on_thinking=None, abort_event=None, **kwargs):
    from llm.plan import run_plan_llm
    return await run_plan_llm(plan=plan, api_config=api_config, on_thinking=on_thinking, abort_event=abort_event, **kwargs)


async def run_task(task_id, description, input_spec, output_spec, resolved_inputs, api_config, **kwargs):
    from llm.task import execute_task
    return await execute_task(task_id=task_id, description=description, input_spec=input_spec, output_spec=output_spec, resolved_inputs=resolved_inputs, api_config=api_config, **kwargs)


async def run_paper(plan, outputs, api_config, format_type="markdown", on_thinking=None, abort_event=None):
    from llm.paper import draft_paper_single_pass
    return await draft_paper_single_pass(plan=plan, outputs=outputs, api_config=api_config, format_type=format_type, on_thinking=on_thinking, abort_event=abort_event)
