"""Prompt dispatcher — selects language-specific prompts based on config."""

from backend.config import settings

if settings.is_chinese():
    from backend.pipeline.prompts_zh import *  # noqa: F401,F403
else:
    from backend.pipeline.prompts_en import *  # noqa: F401,F403
