"""Wasatch pytest database URL must ignore unrelated WASATCH_DATABASE_URL exports."""

from __future__ import annotations

import os

from wasatch_api.testing.postgres import wasatch_test_database_url


def test_wasatch_test_url_ignores_ops_database(monkeypatch) -> None:
    monkeypatch.delenv("WASATCH_TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "WASATCH_DATABASE_URL",
        "postgresql+psycopg://wasatch:replace-me@localhost:5432/wasatch_development_ops",
    )
    assert wasatch_test_database_url().endswith("/wasatch_test")
