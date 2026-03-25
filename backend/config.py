import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_mode: str = "mock"  # "mock", "gemini", "adk", or "agno"
    google_api_key: str = ""  # shared across gemini and adk modes
    gemini_model: str = "gemini-2.0-flash"
    mock_chunk_delay: float = 0.08  # seconds between mock chunks

    # Agno mode
    agno_model_provider: str = "google"  # "google", "anthropic", or "openai"
    agno_model_id: str = "gemini-2.5-flash"
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # Docker sandbox
    docker_sandbox_image: str = "maars-sandbox:latest"
    docker_sandbox_timeout: int = 120  # seconds
    docker_sandbox_memory: str = "512m"
    docker_sandbox_cpu: float = 1.0
    docker_sandbox_network: bool = False

    class Config:
        env_prefix = "MAARS_"
        env_file = ".env"


settings = Settings()

# Bridge API keys to standard env vars (ADK and Agno read from env)
if settings.google_api_key:
    os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)
if settings.openai_api_key:
    os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
if settings.anthropic_api_key:
    os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)
