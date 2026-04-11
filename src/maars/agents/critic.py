"""Refine / Critic — structured-output LLM judge."""

from __future__ import annotations

from pydantic import BaseModel, Field

from maars.models import get_chat_model
from maars.prompts.critic import CRITIC_SYSTEM_PROMPT
from maars.state import Issue


class CritiqueResult(BaseModel):
    """Output of one Critic review round."""

    issues: list[Issue] = Field(
        description="Issues found in the current draft. Empty list if no issues."
    )
    resolved: list[str] = Field(
        default_factory=list,
        description="IDs of previously-raised issues that are now resolved in this draft.",
    )
    passed: bool = Field(
        description="True if the draft is ready to exit the Refine loop (no blockers, and at most 1 major)."
    )
    summary: str = Field(
        description="One-paragraph overall assessment, 3 sentences max."
    )


def critique_draft(
    draft: str,
    *,
    prior_issues: list[Issue] | None = None,
) -> CritiqueResult:
    """Run the Critic once on a draft and return a structured CritiqueResult."""
    model = get_chat_model(temperature=0.0)
    critic = model.with_structured_output(CritiqueResult)

    prior_block = ""
    if prior_issues:
        lines = [
            f"- [{i.id}] ({i.severity}) {i.summary}: {i.detail}"
            for i in prior_issues
        ]
        prior_block = "\n\n## 前轮 issues（检查是否已解决）\n\n" + "\n".join(lines)

    user_message = f"""请审查下面的研究提案草稿。

## Draft

{draft}{prior_block}

请按 CritiqueResult 的结构化格式返回你的评审结果。"""

    result = critic.invoke(
        [
            ("system", CRITIC_SYSTEM_PROMPT),
            ("human", user_message),
        ]
    )
    return result  # type: ignore[return-value]
