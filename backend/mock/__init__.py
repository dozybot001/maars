"""Mock runtime infrastructure — data loading and stream simulation.

Data files live in mock/data/*.json.
"""

from pathlib import Path
from typing import Dict, Optional

import orjson

MOCK_DATA_DIR = Path(__file__).resolve().parent / "data"

_cache: Dict[str, dict] = {}


def _get_all_entries(response_type: str) -> dict:
    """Load and cache all entries for a response type (e.g. 'atomicity', 'execute')."""
    if response_type not in _cache:
        path = MOCK_DATA_DIR / f"{response_type}.json"
        try:
            _cache[response_type] = orjson.loads(path.read_bytes())
        except (FileNotFoundError, orjson.JSONDecodeError):
            _cache[response_type] = {}
    return _cache[response_type]


def load_mock(
    response_type: str,
    key: str = "_default",
    *,
    fallback_key: str = "_default",
    extra_fallback_key: str = "",
) -> Optional[Dict]:
    """Load a mock entry {content, reasoning}.

    Lookup order: key → extra_fallback_key (if set) → fallback_key.
    Reasoning falls back to _default entry if empty.
    """
    data = _get_all_entries(response_type)
    entry = data.get(key)
    if not entry and extra_fallback_key:
        entry = data.get(extra_fallback_key)
    if not entry:
        entry = data.get(fallback_key)
    if not entry:
        return None

    content = entry.get("content")
    content_str = content if isinstance(content, str) else orjson.dumps(content).decode("utf-8")

    reasoning = entry.get("reasoning", "")
    if not (reasoning or "").strip():
        default_entry = data.get("_default") or {}
        reasoning = default_entry.get("reasoning", "")

    return {"content": content_str, "reasoning": reasoning}
