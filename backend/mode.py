"""
Global mode dispatch.

One setting, three modes:
  "mock"  → mock/runner
  "agent" → agents/runner
  "llm"   → llm/runner (default)

api_config["mode"] controls which runner handles all stages.
"""


def _get_runner(api_config: dict):
    """Return the runner module for the current mode."""
    mode = (api_config or {}).get("mode", "mock").strip().lower()
    if mode == "agent":
        import agents.runner as runner
    elif mode == "mock":
        import mock.runner as runner
    else:
        import llm.runner as runner
    return runner


async def run_idea(idea, api_config, **kwargs):
    return await _get_runner(api_config).run_idea(idea, api_config, **kwargs)


async def run_plan(plan, api_config, **kwargs):
    return await _get_runner(api_config).run_plan(plan, api_config, **kwargs)


async def run_task(task_id, description, input_spec, output_spec, resolved_inputs, api_config, **kwargs):
    return await _get_runner(api_config).run_task(
        task_id, description, input_spec, output_spec, resolved_inputs, api_config, **kwargs
    )


async def run_paper(plan, outputs, api_config, **kwargs):
    return await _get_runner(api_config).run_paper(plan, outputs, api_config, **kwargs)
