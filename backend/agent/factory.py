"""Centralized ADK Agent factory.

All Agent instances in MAARS should be created through create_agent()
so that boilerplate config (model, tool_config) is maintained in one place.
"""

from google.adk import Agent
from google.genai import types

# Shared config for all agents — server-side tool invocations required
# for ADK built-in tools (google_search, url_context)
_DEFAULT_CONFIG = types.GenerateContentConfig(
    tool_config=types.ToolConfig(
        include_server_side_tool_invocations=True,
    ),
)


def create_agent(
    name: str,
    instruction: str,
    model: str = "gemini-2.0-flash",
    tools: list | None = None,
) -> Agent:
    """Create an ADK Agent with standard MAARS config.

    All boilerplate (generate_content_config, tool_config) is handled here.
    Callers only specify what varies: name, instruction, tools.
    """
    return Agent(
        name=name,
        model=model,
        instruction=instruction,
        tools=tools or [],
        generate_content_config=_DEFAULT_CONFIG,
    )
