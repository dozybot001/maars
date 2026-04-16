"""Shared utilities for the MAARS backend."""

import json
import re


def parse_json_fenced(text: str, fallback: dict | None = None) -> dict:
    """Extract a JSON object from LLM output that may be wrapped in markdown fences.

    Tries raw JSON first, then looks for ```json ... ``` blocks.
    Falls back to repairing common LLM issues (LaTeX backslashes) before giving up.
    Returns *fallback* (default empty dict) on parse failure.
    """
    _fallback = fallback if fallback is not None else {}
    text = text.strip()

    for candidate in _json_candidates(text):
        try:
            result = json.loads(candidate)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass
        # Retry with repaired backslashes (LaTeX \rho, \in, etc.)
        try:
            result = json.loads(_repair_json_escapes(candidate))
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    return _fallback


def _json_candidates(text: str):
    """Yield candidate JSON strings: raw text first, then fenced blocks."""
    yield text
    for match in re.finditer(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL):
        yield match.group(1).strip()


def _repair_json_escapes(text: str) -> str:
    r"""Double-escape backslashes that aren't valid JSON escape sequences.

    LLM outputs frequently contain LaTeX like \rho, \sigma, \lambda inside
    JSON string values. These break json.loads because \i, \l, \s etc. are
    not valid JSON escapes.

    Strategy:
      1. \X where X ∉ {", \, /, b, f, n, r, t, u} → \\X
      2. \r, \n, \t, \b, \f followed by a letter → \\X (LaTeX like \rho, \nu)
    """
    # Step 1: fix clearly invalid escapes (\i, \l, \s, \p, etc.)
    text = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)
    # Step 2: fix ambiguous escapes that are LaTeX, not JSON
    # e.g. \rho (not carriage-return + "ho"), \beta, \nu, \tau, \frac
    text = re.sub(r'\\([bfnrt])([a-zA-Z])', r'\\\\\1\2', text)
    return text
