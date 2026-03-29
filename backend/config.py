import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    google_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"  # default model for agno (google provider)

    # Agno mode — non-google providers
    agno_model_provider: str = "google"  # "google", "anthropic", or "openai"
    agno_model_id: str = ""  # override model for non-google providers (e.g. "claude-sonnet-4-5")
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # Research stage iteration
    research_max_iterations: int = 3  # 1 = no evaluate loop, 3 = up to 2 feedback rounds

    # Kaggle
    kaggle_api_token: str = ""  # KAGGLE_API_TOKEN for API authentication
    kaggle_competition_id: str = ""  # Set at runtime for Kaggle mode
    # External dataset directory (e.g., Kaggle data)
    dataset_dir: str = ""  # mounted read-only at /workspace/data in sandbox

    # Docker sandbox
    docker_sandbox_image: str = "maars-sandbox:latest"
    docker_sandbox_timeout: int = 600  # seconds
    docker_sandbox_memory: str = "4g"
    docker_sandbox_cpu: float = 1.0
    docker_sandbox_network: bool = True

    class Config:
        env_prefix = "MAARS_"
        env_file = ".env"


settings = Settings()

# Bridge API keys to standard env vars (Agno reads from env)
if settings.google_api_key:
    os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)
if settings.openai_api_key:
    os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
if settings.anthropic_api_key:
    os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)
if settings.kaggle_api_token:
    os.environ.setdefault("KAGGLE_API_TOKEN", settings.kaggle_api_token)
