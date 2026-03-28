"""Multi-agent architecture for MAARS.

Provides AgentSession as an alternative to PipelineOrchestrator.
Activated via MAARS_ARCHITECTURE=agents.
"""

from backend.agents.session import AgentSession

__all__ = ["AgentSession"]
