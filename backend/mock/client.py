import asyncio
import random
from typing import AsyncIterator

from backend.llm.client import LLMClient


class MockClient(LLMClient):
    """Sequential response playback for single-stream stages (Refine, Write).

    Returns responses one by one. After exhausting the list, repeats the last.
    """

    def __init__(self, responses: list[str], chunk_delay: float = 0.08):
        self._responses = responses
        self._index = 0
        self.chunk_delay = chunk_delay

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        text = self._next()
        async for chunk in _stream_text(text, self.chunk_delay):
            yield chunk

    def _next(self) -> str:
        if not self._responses:
            return "Mock response."
        text = self._responses[min(self._index, len(self._responses) - 1)]
        self._index += 1
        return text

    def reset(self):
        self._index = 0


class ParallelMockClient(LLMClient):
    """Mock client safe for parallel tasks. Each asyncio Task gets its own
    response counter, so parallel tasks independently cycle through responses.

    Mirrors Gemini's behavior: each concurrent stream() call is independent.
    """

    def __init__(self, responses: list[str], chunk_delay: float = 0.08):
        self._responses = responses
        self.chunk_delay = chunk_delay
        self._task_counters: dict[int, int] = {}

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        text = self._next_for_task()
        async for chunk in _stream_text(text, self.chunk_delay):
            yield chunk

    def _next_for_task(self) -> str:
        if not self._responses:
            return "Mock response."

        task = asyncio.current_task()
        task_id = id(task) if task else 0

        if task_id not in self._task_counters:
            self._task_counters[task_id] = 0

        idx = self._task_counters[task_id]
        text = self._responses[min(idx, len(self._responses) - 1)]
        self._task_counters[task_id] = idx + 1
        return text

    def reset(self):
        self._task_counters.clear()


# --- Shared streaming helper ---

async def _stream_text(text: str, chunk_delay: float) -> AsyncIterator[str]:
    """Stream text: word-by-word for prose, chunk-based for JSON."""
    if text.lstrip().startswith(("{", "[")):
        chunk_size = max(1, len(text) // 4)
        for i in range(0, len(text), chunk_size):
            await asyncio.sleep(chunk_delay + random.uniform(0, 0.03))
            yield text[i:i + chunk_size]
    else:
        for word in text.split(" "):
            if word:
                await asyncio.sleep(chunk_delay + random.uniform(0, 0.03))
                yield word + " "
