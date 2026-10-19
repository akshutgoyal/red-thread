from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RED_THREAD_",
        env_file=(BACKEND_ROOT / ".env", PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Red Thread"
    app_version: str = "0.1.0"
    environment: str = "development"

    data_dir: Path = PROJECT_ROOT / "data"
    reports_dir: Path = PROJECT_ROOT / "reports"
    sample_data_dir: Path = PROJECT_ROOT / "sample_data"
    database_url: str | None = None
    max_upload_mb: int = 50
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    enable_live_monitor: bool = False
    seed_demo: bool = False

    storage_backend: str = "local"
    r2_account_id: str | None = Field(default=None, validation_alias="R2_ACCOUNT_ID")
    r2_access_key_id: str | None = Field(default=None, validation_alias="R2_ACCESS_KEY_ID")
    r2_secret_access_key: str | None = Field(
        default=None, validation_alias="R2_SECRET_ACCESS_KEY"
    )
    r2_bucket: str | None = Field(default=None, validation_alias="R2_BUCKET")
    r2_endpoint: str | None = Field(default=None, validation_alias="R2_ENDPOINT")
    r2_region: str = Field(default="auto", validation_alias="R2_REGION")

    auth_default_timezone: str = "UTC"
    default_timezone: str = "Asia/Kolkata"
    auth_default_year: int | None = None

    ai_provider: str = "auto"
    ai_timeout_seconds: float = 60.0
    ai_max_retries: int = 2
    ai_max_context_chars: int = 60000
    ai_max_tokens: int = 8192
    ai_redact_pii: bool = True

    commandcode_api_key: str | None = Field(default=None, validation_alias="COMMANDCODE_API_KEY")
    commandcode_base_url: str = Field(
        default="https://api.commandcode.ai/provider/v1",
        validation_alias="COMMANDCODE_BASE_URL",
    )
    commandcode_model: str = Field(
        default="deepseek/deepseek-v4.1-flash",
        validation_alias="COMMANDCODE_MODEL",
    )
    commandcode_zdr: bool = Field(default=True, validation_alias="COMMANDCODE_ZDR")

    tokenharbor_api_key: str | None = Field(default=None, validation_alias="TOKENHARBOR_API_KEY")
    tokenharbor_base_url: str = Field(
        default="https://tokenharbor.ai/v1",
        validation_alias="TOKENHARBOR_BASE_URL",
    )
    tokenharbor_model: str = Field(
        default="deepseek-v4.1-flash:free",
        validation_alias="TOKENHARBOR_MODEL",
    )

    tesseract_cmd: str | None = Field(default=None, validation_alias="TESSERACT_CMD")

    @field_validator("auth_default_year", mode="before")
    @classmethod
    def _blank_year_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("data_dir", mode="before")
    @classmethod
    def _blank_data_dir_uses_default(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return PROJECT_ROOT / "data"
        return value

    @field_validator("reports_dir", mode="before")
    @classmethod
    def _blank_reports_dir_uses_default(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return PROJECT_ROOT / "reports"
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def _blank_database_url_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("sample_data_dir", mode="before")
    @classmethod
    def _blank_sample_data_dir_uses_default(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return PROJECT_ROOT / "sample_data"
        return value

    @field_validator("storage_backend", mode="before")
    @classmethod
    def _normalize_storage_backend(cls, value: object) -> str:
        normalized = str(value or "local").strip().lower()
        if normalized not in {"local", "r2"}:
            raise ValueError("RED_THREAD_STORAGE_BACKEND must be 'local' or 'r2'.")
        return normalized

    @model_validator(mode="after")
    def _validate_r2_configuration(self) -> "Settings":
        if self.storage_backend != "r2":
            return self
        missing: list[str] = []
        if not self.r2_endpoint and not self.r2_account_id:
            missing.append("R2_ACCOUNT_ID or R2_ENDPOINT")
        if not self.r2_access_key_id:
            missing.append("R2_ACCESS_KEY_ID")
        if not self.r2_secret_access_key:
            missing.append("R2_SECRET_ACCESS_KEY")
        if not self.r2_bucket:
            missing.append("R2_BUCKET")
        if missing:
            raise ValueError(
                "RED_THREAD_STORAGE_BACKEND=r2 requires: " + ", ".join(missing)
            )
        return self

    @property
    def resolved_data_dir(self) -> Path:
        return self.data_dir.expanduser().resolve()

    @property
    def resolved_reports_dir(self) -> Path:
        return self.reports_dir.expanduser().resolve()

    @property
    def evidence_dir(self) -> Path:
        return self.resolved_data_dir / "evidence"

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            value = self.database_url.strip()
            if value.startswith("postgres://"):
                return "postgresql+psycopg://" + value[len("postgres://") :]
            if value.startswith("postgresql://"):
                return "postgresql+psycopg://" + value[len("postgresql://") :]
            return value
        return f"sqlite:///{self.resolved_data_dir / 'red-thread.db'}"

    @property
    def is_r2(self) -> bool:
        return self.storage_backend == "r2"

    @property
    def resolved_r2_endpoint(self) -> str | None:
        if self.r2_endpoint:
            return self.r2_endpoint.rstrip("/")
        if self.r2_account_id:
            return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"
        return None

    @property
    def cors_origin_list(self) -> list[str]:
        origins: list[str] = []
        for raw in self.cors_origins.split(","):
            origin = raw.strip().rstrip("/")
            if origin:
                origins.append(origin)
        return origins

    @property
    def max_upload_bytes(self) -> int:
        return max(1, self.max_upload_mb) * 1024 * 1024

    def ensure_directories(self) -> None:
        self.resolved_data_dir.mkdir(parents=True, exist_ok=True)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.resolved_reports_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
