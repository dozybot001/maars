"""Shared utilities for the MAARS backend."""

import json
import re


def parse_json_fenced(text: str, fallback: dict | None = None) -> dict:
    """Extract a JSON object from LLM output that may be wrapped in markdown fences.

    Tries raw JSON first, then looks for ```json ... ``` blocks.
    Returns *fallback* (default empty dict) on parse failure.
    """
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    return fallback if fallback is not None else {}
