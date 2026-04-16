import os

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Google LLM ---
    google_api_key: str
    google_model: str
    refine_model: str | None = None
    research_model: str | None = None
    write_model: str | None = None
    polish_model: str | None = None

    # --- Research ---
    research_max_iterations: int
    team_max_delegations: int

    # --- Kaggle ---
    kaggle_api_token: str
    dataset_dir: str

    # --- API ---
    api_concurrency: int
    api_request_interval: float = 0  # min seconds between consecutive LLM calls
    output_language: str

    # --- Docker Sandbox ---
    docker_sandbox_image: str
    docker_sandbox_timeout: int  # one code_execute shell limit (seconds)
    agent_session_timeout: int | None = None  # one LLM arun; unset => 2 * docker_sandbox_timeout
    docker_sandbox_memory: str
    docker_sandbox_cpu: float
    docker_sandbox_network: bool
    docker_sandbox_gpu: bool

    class Config:
        env_prefix = "MAARS_"
        env_file = ".env"
        extra = "ignore"

    @model_validator(mode="after")
    def _agent_timeout_vs_sandbox(self):
        eff = self.agent_session_timeout_seconds()
        if eff < self.docker_sandbox_timeout:
            raise ValueError(
                "MAARS_AGENT_SESSION_TIMEOUT must be >= MAARS_DOCKER_SANDBOX_TIMEOUT "
                "(an agent turn may run one full code_execute plus model time)."
            )
        return self

    def agent_session_timeout_seconds(self) -> int:
        if self.agent_session_timeout is not None:
            return self.agent_session_timeout
        return 2 * self.docker_sandbox_timeout

    def is_chinese(self) -> bool:
        return self.output_language.lower().startswith("ch")

    def model_for_stage(self, stage: str) -> str:
        override = getattr(self, f"{stage}_model", None)
        if override:
            return override
        # polish falls back to write_model before google_model
        if stage == "polish" and self.write_model:
            return self.write_model
        return self.google_model


settings = Settings()

if settings.google_api_key:
    os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)
if settings.kaggle_api_token:
    os.environ.setdefault("KAGGLE_API_TOKEN", settings.kaggle_api_token)
