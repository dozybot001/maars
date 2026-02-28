"""
Execution logic - LLM-based task execution and artifact resolution.
"""

from .artifact_resolver import resolve_artifacts
from .llm_executor import execute_task

__all__ = ["resolve_artifacts", "execute_task"]
