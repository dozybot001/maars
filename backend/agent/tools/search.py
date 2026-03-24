"""Google Search tool for ADK agents."""


def create_search_tools() -> list:
    """Return Google Search tool for ADK agents.

    Returns an empty list if the tool is unavailable,
    allowing agents to function without search capability.
    """
    try:
        from google.adk.tools import google_search
        return [google_search]
    except (ImportError, AttributeError):
        return []
