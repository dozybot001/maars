"""Mock streaming simulation.

Simulates chunked streaming output for frontend thinking display during mock mode.
Chunk size and delay are configurable via environment variables:
  MAARS_MOCK_STREAM_CHUNK_SIZE (default 8)
  MAARS_MOCK_STREAM_DELAY_MS (default 30)
"""

import asyncio
import os
from typing import Any, Callable, Optional


async def stream_mock(
    content: str,
    on_chunk: Optional[Callable[[str], None]] = None,
    abort_event: Optional[Any] = None,
) -> str:
    """Simulate streaming of mock content, then return it."""
    if on_chunk and content:
        chunk_size = max(1, int(os.getenv("MAARS_MOCK_STREAM_CHUNK_SIZE", "8")))
        delay_s = max(0.0, int(os.getenv("MAARS_MOCK_STREAM_DELAY_MS", "30")) / 1000.0)
        for i in range(0, len(content), chunk_size):
            if abort_event and abort_event.is_set():
                raise asyncio.CancelledError("Aborted")
            chunk = content[i : i + chunk_size]
            if chunk:
                r = on_chunk(chunk)
                if asyncio.iscoroutine(r):
                    await r
            if delay_s:
                await asyncio.sleep(delay_s)
    return content or ""
