"""Google Gemini LLM client."""

from typing import AsyncIterator

from google import genai

from .client import LLMClient


class GeminiClient(LLMClient):
    """Streams responses from Google Gemini API.

    Each instance carries its own instruction (system prompt).
    Pipeline stages only send user messages; the instruction is
    prepended by the client internally.
    """

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash",
                 instruction: str | None = None):
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._instruction = instruction
        self._broadcast = lambda event: None

    def set_broadcast(self, fn):
        self._broadcast = fn

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        # Client's own instruction takes priority; fall back to
        # any system message in the messages list (backward compat)
        system_instruction = self._instruction
        contents = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                if not system_instruction:
                    system_instruction = content
                # else: ignore pipeline's system prompt, client owns it
            elif role == "user":
                contents.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})

        config = None
        if system_instruction:
            config = genai.types.GenerateContentConfig(
                system_instruction=system_instruction,
            )

        response = await self._client.aio.models.generate_content_stream(
            model=self._model,
            contents=contents,
            config=config,
        )

        usage = None
        async for chunk in response:
            if chunk.text:
                yield chunk.text
            if chunk.usage_metadata:
                usage = chunk.usage_metadata

        if usage:
            self._broadcast({
                "stage": "_llm",
                "type": "tokens",
                "data": {
                    "input": usage.prompt_token_count or 0,
                    "output": getattr(usage, 'candidates_token_count', None)
                             or getattr(usage, 'response_token_count', None) or 0,
                    "total": usage.total_token_count or 0,
                },
            })
