"""Environment-driven application configuration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    """Local and CI settings. Secrets must come from the environment."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "local"
    app_log_level: str = "INFO"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "wasatch"
    postgres_user: str = "wasatch"
    postgres_password: str = "replace-me"
    database_url: str | None = Field(
        default=None, validation_alias="WASATCH_DATABASE_URL"
    )
    fixtures_dir: Path | None = Field(
        default=None, validation_alias="WASATCH_FIXTURES_DIR"
    )
    cors_origins: str = ""

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        password = self.postgres_password
        return (
            f"postgresql+psycopg://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    def resolved_fixtures_dir(self) -> Path:
        if self.fixtures_dir:
            return Path(self.fixtures_dir)
        return REPO_ROOT / "data" / "fixtures" / "valid"

    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
