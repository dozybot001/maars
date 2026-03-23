"""Google Gemini LLM client."""

from typing import AsyncIterator

from google import genai

from .client import LLMClient


class GeminiClient(LLMClient):
    """Streams responses from Google Gemini API.

    Converts OpenAI-style messages (role/content dicts) to Gemini format.
    """

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        system_instruction, contents = self._convert_messages(messages)

        response = await self._client.aio.models.generate_content_stream(
            model=self._model,
            contents=contents,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_instruction,
            ) if system_instruction else None,
        )

        async for chunk in response:
            if chunk.text:
                yield chunk.text

    def _convert_messages(self, messages: list[dict]) -> tuple[str | None, list[dict]]:
        """Convert OpenAI-style messages to Gemini format.

        Returns (system_instruction, contents).
        Gemini uses "user" and "model" roles (not "assistant").
        """
        system_instruction = None
        contents = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                system_instruction = content
            elif role == "user":
                contents.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})

        return system_instruction, contents
