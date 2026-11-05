"""Database URL selection for development_ops."""

from __future__ import annotations

import os

from development_ops.database import development_ops_database_url


def test_ops_url_does_not_follow_wasatch_test(monkeypatch) -> None:
    monkeypatch.setenv(
        "WASATCH_DATABASE_URL",
        "postgresql+psycopg://wasatch:replace-me@localhost:5432/wasatch_test",
    )
    monkeypatch.delenv("DEVELOPMENT_OPS_DATABASE_URL", raising=False)
    url = development_ops_database_url()
    assert url.endswith("/wasatch_development_ops")


def test_explicit_ops_url_wins(monkeypatch) -> None:
    monkeypatch.setenv(
        "DEVELOPMENT_OPS_DATABASE_URL",
        "postgresql+psycopg://wasatch:replace-me@localhost:5432/custom_ops",
    )
    assert development_ops_database_url().endswith("/custom_ops")
