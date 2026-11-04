"""Environment-driven application configuration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]

# The header adapter is a development identity simulation. These are the only
# environments where it may run. There is no production authenticator.
LOCAL_SYNTHETIC_ENVIRONMENTS = frozenset({"local", "development", "test"})
PRODUCTION_ENVIRONMENTS = frozenset({"production", "prod"})


class UnsafeProductionConfiguration(RuntimeError):
    """The process must not serve traffic with this environment."""


def normalize_app_env(app_env: str) -> str:
    return app_env.strip().lower()


def laboratory_actor_adapter_allowed(app_env: str) -> bool:
    """True only for local synthetic development."""

    return normalize_app_env(app_env) in LOCAL_SYNTHETIC_ENVIRONMENTS


def reject_unsafe_production_configuration(app_env: str) -> None:
    """Refuse to start when the laboratory header would be unsafe.

    ``production`` and ``prod`` are production configurations. The header is
    not a production authenticator, and leaving business reads open is also
    unsafe, so startup fails. Any other environment outside local synthetic
    development fails for the same reason: no second authenticator exists.
    """

    if laboratory_actor_adapter_allowed(app_env):
        return
    env = normalize_app_env(app_env)
    if env in PRODUCTION_ENVIRONMENTS:
        raise UnsafeProductionConfiguration(
            "Refusing to start: APP_ENV is a production configuration. "
            "The X-Laboratory-Actor header is a local synthetic development "
            "identity simulation, not a production authenticator. "
            "No password system and no identity provider is configured."
        )
    allowed = ", ".join(sorted(LOCAL_SYNTHETIC_ENVIRONMENTS))
    raise UnsafeProductionConfiguration(
        "Refusing to start: APP_ENV "
        f"{app_env!r} is outside local synthetic development ({allowed}). "
        "The laboratory actor adapter stays inactive, and business API reads "
        "cannot be left unauthenticated. No password system and no identity "
        "provider is configured."
    )


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
