from functools import lru_cache
from pathlib import Path
import re

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/:-]{0,199}$")
_FORBIDDEN_URL_CHARS = set(";|`$\n\r&<>")


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

    # ------------------------------------------------------------------
    # OpenAI planning provider (configuration only; no credential persistence)
    # ------------------------------------------------------------------
    # Logical Sol/Terra/Luna model identifiers map to hosted OpenAI model IDs.
    # These are control-plane settings only — never shell commands or paths.
    openai_planning_enabled: bool = False
    openai_api_key: SecretStr | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_timeout_sec: float = Field(default=60.0, ge=1.0, le=600.0)
    openai_wall_time_sec: float = Field(default=120.0, ge=1.0, le=1800.0)
    openai_transport_retries: int = Field(default=2, ge=0, le=5)
    openai_max_response_bytes: int = Field(default=524_288, ge=1024, le=8_388_608)
    openai_repair_instruction_limit: int = Field(default=12, ge=0, le=20)
    openai_logical_model_luna: str = "gpt-4o-mini"
    openai_logical_model_terra: str = "gpt-4o"
    openai_logical_model_sol: str = "gpt-4.1"

    @field_validator("openai_base_url")
    @classmethod
    def validate_openai_base_url(cls, value: str) -> str:
        cleaned = (value or "").strip().rstrip("/")
        if not cleaned.startswith(("http://", "https://")):
            raise ValueError("openai_base_url must be an http(s) URL")
        if any(ch in cleaned for ch in _FORBIDDEN_URL_CHARS):
            raise ValueError("openai_base_url contains forbidden characters")
        # Reject shell/executable path shapes — HTTP endpoints only.
        if cleaned.lower().startswith(("file:", "ftp:")):
            raise ValueError("openai_base_url must be an http(s) URL")
        return cleaned

    @field_validator(
        "openai_logical_model_luna",
        "openai_logical_model_terra",
        "openai_logical_model_sol",
    )
    @classmethod
    def validate_logical_model_id(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned or not _MODEL_ID_RE.match(cleaned):
            raise ValueError(
                "logical model identifier must be a safe model id "
                "(letters, digits, . _ / : -); shell commands and paths are rejected"
            )
        lowered = cleaned.lower()
        if any(
            token in lowered
            for token in (
                ".exe",
                ".bat",
                ".cmd",
                ".ps1",
                ".sh",
                "powershell",
                "cmd.exe",
                "/bin/",
                "\\",
            )
        ):
            raise ValueError("logical model identifier must not look like an executable path")
        return cleaned

    @property
    def openai_configured(self) -> bool:
        """True when the OpenAI planning adapter may be constructed."""
        if not self.openai_planning_enabled:
            return False
        if self.openai_api_key is None:
            return False
        secret = self.openai_api_key.get_secret_value()
        return bool(secret and secret.strip())

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
