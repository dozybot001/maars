import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- LLM Provider ---
    model_provider: str = "google"  # "google", "anthropic", or "openai"

    # Per-provider config (only the active provider's fields are required)
    google_api_key: str = ""
    google_model: str = "gemini-2.5-flash"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5-20250514"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # --- Research ---
    research_max_iterations: int = 3  # 1 = no evaluate loop, 3 = up to 2 feedback rounds

    # --- Kaggle ---
    kaggle_api_token: str = ""
    kaggle_competition_id: str = ""  # set at runtime for Kaggle mode
    dataset_dir: str = ""  # mounted read-only at /workspace/data in sandbox

    # --- Docker Sandbox ---
    docker_sandbox_image: str = "maars-sandbox:latest"
    docker_sandbox_timeout: int = 600  # seconds
    docker_sandbox_memory: str = "4g"
    docker_sandbox_cpu: float = 1.0
    docker_sandbox_network: bool = True
    docker_sandbox_concurrency: int = 2  # max concurrent containers

    class Config:
        env_prefix = "MAARS_"
        env_file = ".env"

    @property
    def active_api_key(self) -> str:
        """Return the API key for the active provider."""
        return {
            "google": self.google_api_key,
            "anthropic": self.anthropic_api_key,
            "openai": self.openai_api_key,
        }.get(self.model_provider, "")

    @property
    def active_model(self) -> str:
        """Return the model ID for the active provider."""
        return {
            "google": self.google_model,
            "anthropic": self.anthropic_model,
            "openai": self.openai_model,
        }.get(self.model_provider, "")


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
