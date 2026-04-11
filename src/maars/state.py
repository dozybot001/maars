"""Graph state schemas and supporting types."""

from __future__ import annotations

from operator import add
from typing import Annotated, TypedDict

from pydantic import BaseModel, Field


class Issue(BaseModel):
    """A single issue raised by a Critic during Refine iteration."""

    id: str = Field(
        description="Stable identifier for this issue (e.g. 'vague-scope-1')."
    )
    severity: str = Field(description="One of: blocker, major, minor.")
    summary: str = Field(description="One-line description of the issue.")
    detail: str = Field(description="Full explanation of why this is a problem.")


class RefineState(TypedDict, total=False):
    """State schema for the Refine graph (Explorer ↔ Critic)."""

    raw_idea: str
    draft: str
    issues: Annotated[list[Issue], add]
    resolved: Annotated[list[str], add]
    round: int
    passed: bool
    refined_idea: str
