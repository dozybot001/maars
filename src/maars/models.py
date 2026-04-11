"""Chat model factory — multi-provider via LangChain init_chat_model."""

from __future__ import annotations

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from maars.config import CHAT_MODEL


def get_chat_model(
    *,
    model: str | None = None,
    temperature: float = 0.0,
) -> BaseChatModel:
    """Return a chat model routed by provider prefix.

    Examples of MAARS_CHAT_MODEL values:
        google_genai:gemini-3-flash-preview
        anthropic:claude-sonnet-4-6
    """
    return init_chat_model(
        model=model or CHAT_MODEL,
        temperature=temperature,
    )
