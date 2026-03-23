import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_mode: str = "mock"  # "mock", "gemini", or "agent"
    google_api_key: str = ""  # shared across gemini and agent modes
    gemini_model: str = "gemini-2.0-flash"
    mock_chunk_delay: float = 0.08  # seconds between mock chunks

    class Config:
        env_prefix = "MAARS_"
        env_file = ".env"


settings = Settings()

# ADK reads GOOGLE_API_KEY from env — bridge our config
if settings.google_api_key:
    os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)
