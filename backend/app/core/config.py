from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CINEFORGE_",
        extra="ignore",
    )

    env: str = "local"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./storage/cineforge_local.db"
    comfyui_base_url: AnyHttpUrl = "http://127.0.0.1:8188"
    storage_root: Path = Field(default=Path("./storage"))
    allow_absolute_input_paths: bool = False
    queue_worker_enabled: bool = False
    autonomy_mode: str = "scaffold_only"
    cors_allowed_origins: list[str] = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]

    @property
    def workflow_template_root(self) -> Path:
        return self.storage_root / "workflow_templates"

    @property
    def workflow_snapshot_root(self) -> Path:
        return self.storage_root / "workflow_snapshots"

    @property
    def probes_root(self) -> Path:
        return self.storage_root / "probes"


@lru_cache
def get_settings() -> Settings:
    return Settings()

