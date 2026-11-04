from __future__ import annotations

from wasatch_api.config import Settings, get_settings


def test_sqlalchemy_url_from_parts(monkeypatch) -> None:
    monkeypatch.delenv("WASATCH_DATABASE_URL", raising=False)
    get_settings.cache_clear()
    settings = Settings(
        postgres_host="db.internal",
        postgres_port=6543,
        postgres_db="lab",
        postgres_user="wasatch",
        postgres_password="secret",
        database_url=None,
    )
    assert settings.sqlalchemy_url == (
        "postgresql+psycopg://wasatch:secret@db.internal:6543/lab"
    )


def test_explicit_database_url_wins() -> None:
    settings = Settings.model_construct(
        postgres_host="localhost",
        postgres_port=5432,
        postgres_db="wasatch",
        postgres_user="wasatch",
        postgres_password="replace-me",
        database_url="postgresql+psycopg://other/db",
        cors_origins="http://localhost:3000",
    )
    assert settings.sqlalchemy_url == "postgresql+psycopg://other/db"
    assert settings.cors_origin_list() == ["http://localhost:3000"]


def test_cors_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    settings = Settings()
    assert settings.cors_origin_list() == []
