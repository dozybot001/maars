import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Google LLM ---
    google_api_key: str
    google_model: str

    # --- Research ---
    research_max_iterations: int
    team_max_delegations: int

    # --- Kaggle ---
    kaggle_api_token: str
    dataset_dir: str

    # --- API ---
    api_concurrency: int
    output_language: str

    # --- Docker Sandbox ---
    docker_sandbox_image: str
    docker_sandbox_timeout: int
    docker_sandbox_memory: str
    docker_sandbox_cpu: float
    docker_sandbox_network: bool
    docker_sandbox_gpu: bool

    class Config:
        env_prefix = "MAARS_"
        env_file = ".env"
        extra = "ignore"


settings = Settings()

if settings.google_api_key:
    os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)
if settings.kaggle_api_token:
    os.environ.setdefault("KAGGLE_API_TOKEN", settings.kaggle_api_token)
