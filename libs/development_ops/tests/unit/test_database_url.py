"""Development ops database URL resolution."""

from __future__ import annotations

from development_ops.database import (
    DEFAULT_DEVELOPMENT_OPS_DATABASE_URL,
    development_ops_database_url,
)


def test_default_isolated_database(monkeypatch) -> None:
    monkeypatch.delenv("DEVELOPMENT_OPS_DATABASE_URL", raising=False)
    monkeypatch.delenv("WASATCH_DATABASE_URL", raising=False)
    assert development_ops_database_url() == DEFAULT_DEVELOPMENT_OPS_DATABASE_URL


def test_explicit_ops_url(monkeypatch) -> None:
    custom = "postgresql+psycopg://wasatch:replace-me@localhost:5432/custom_ops"
    monkeypatch.setenv("DEVELOPMENT_OPS_DATABASE_URL", custom)
    assert development_ops_database_url() == custom


def test_wasatch_url_does_not_redirect_ops(monkeypatch) -> None:
    monkeypatch.delenv("DEVELOPMENT_OPS_DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "WASATCH_DATABASE_URL",
        "postgresql+psycopg://wasatch:replace-me@localhost:5432/wasatch",
    )
    assert development_ops_database_url() == DEFAULT_DEVELOPMENT_OPS_DATABASE_URL
