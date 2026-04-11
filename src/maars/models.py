"""Chat model factory — Gemini only (no multi-provider abstraction)."""

from __future__ import annotations

from langchain_google_genai import ChatGoogleGenerativeAI

from maars.config import CHAT_MODEL


def get_chat_model(
    *,
    model: str | None = None,
    temperature: float = 0.0,
) -> ChatGoogleGenerativeAI:
    """Return a Gemini chat model. Reads GOOGLE_API_KEY from env."""
    return ChatGoogleGenerativeAI(
        model=model or CHAT_MODEL,
        temperature=temperature,
    )


def get_search_model(
    *,
    model: str | None = None,
    temperature: float = 0.0,
):
    """Return a Gemini chat model with built-in google_search grounding.

    The model autonomously decides whether to search. No external search
    API (Tavily etc.) is used. Explorer uses this to verify SOTA baselines
    and current methods in one invocation, without a ReAct loop.
    """
    return ChatGoogleGenerativeAI(
        model=model or CHAT_MODEL,
        temperature=temperature,
    ).bind_tools([{"google_search": {}}])
