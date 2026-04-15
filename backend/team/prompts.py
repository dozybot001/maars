"""Prompt dispatcher — selects language-specific team prompts based on config."""

from backend.config import settings

if settings.is_chinese():
    from backend.team.prompts_zh import *  # noqa: F401,F403
else:
    from backend.team.prompts_en import *  # noqa: F401,F403
