from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class StreamEvent:
    """Structured event yielded by LLMClient.stream().

    Pipeline dispatches all events uniformly — clients never broadcast directly.
    """
    type: str  # "content" | "think" | "tool_call" | "tool_result" | "tokens"
    text: str = ""
    call_id: str = ""
    metadata: dict = field(default_factory=dict)


class LLMClient(ABC):
    """Abstract base for all LLM providers.

    Mock and real implementations share the same interface so the
    pipeline layer never knows which provider is active.
    """

    # If True, the client has tools and reads dependencies via tools.
    # Pipeline will NOT pre-load dependency outputs into prompts.
    has_tools = False

    @abstractmethod
    async def stream(self, messages: list[dict]) -> AsyncIterator[StreamEvent]:
        """Yield StreamEvents from the LLM response."""
        ...

    def describe_capabilities(self) -> str:
        """Describe what this client can do. Used for atomic task calibration.

        Override in subclasses to provide tool-specific descriptions.
        """
        if self.has_tools:
            return "AI Agent with tool access and multi-step reasoning."
        return "Text-only LLM. Single conversation turn. No tools or code execution."

    def request_stop(self):
        """Signal the client to stop after the current in-flight event.
        Default no-op. AgentClient/AgnoClient override to break the loop."""
        pass

    def reset(self):
        """Reset internal state. Called when the pipeline restarts.
        No-op for real LLM clients. MockClient clears response counters."""
        pass
