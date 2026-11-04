"""Pytest must not inherit WASATCH_DATABASE_URL from the shell."""

from __future__ import annotations

from wasatch_api.testing.postgres import wasatch_test_database_url


def test_pytest_database_ignores_wasatch_database_url(monkeypatch) -> None:
    monkeypatch.delenv("WASATCH_TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "WASATCH_DATABASE_URL",
        "postgresql+psycopg://wasatch:replace-me@localhost:5432/wasatch",
    )
    assert wasatch_test_database_url().endswith("/wasatch_test")


def test_pytest_database_accepts_wasatch_test_database_url(monkeypatch) -> None:
    ci = "postgresql+psycopg://wasatch:wasatch@localhost:5432/wasatch_test"
    monkeypatch.delenv("WASATCH_TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv("WASATCH_DATABASE_URL", ci)
    assert wasatch_test_database_url() == ci


def test_pytest_database_honors_test_url(monkeypatch) -> None:
    custom = "postgresql+psycopg://wasatch:replace-me@localhost:5432/wasatch_test"
    monkeypatch.setenv("WASATCH_TEST_DATABASE_URL", custom)
    monkeypatch.setenv(
        "WASATCH_DATABASE_URL",
        "postgresql+psycopg://wasatch:replace-me@localhost:5432/wasatch",
    )
    assert wasatch_test_database_url() == custom
