"""Wasatch pytest database URL helpers must never target operational databases."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine

from wasatch_api.testing.postgres import (
    DISPOSABLE_TEST_DATABASES,
    OPERATIONAL_DATABASES,
    UnsafeTestDatabaseError,
    assert_disposable_test_database,
    assert_engine_is_disposable,
    database_name,
    drop_and_recreate_test_database,
    is_disposable_test_database,
    wasatch_development_ops_test_database_url,
    wasatch_test_database_url,
)

OPERATIONAL_URL = (
    "postgresql+psycopg://wasatch:replace-me@localhost:5432/wasatch_development_ops"
)


def test_wasatch_test_url_ignores_ops_database(monkeypatch) -> None:
    monkeypatch.delenv("WASATCH_TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv("WASATCH_DATABASE_URL", OPERATIONAL_URL)
    assert wasatch_test_database_url().endswith("/wasatch_test")


def test_explicit_test_url_must_be_disposable(monkeypatch) -> None:
    monkeypatch.setenv("WASATCH_TEST_DATABASE_URL", OPERATIONAL_URL)
    with pytest.raises(UnsafeTestDatabaseError):
        wasatch_test_database_url()


def test_ops_test_url_never_resolves_to_operational_database(monkeypatch) -> None:
    """Even when DEVELOPMENT_OPS_DATABASE_URL points at live data."""
    monkeypatch.delenv("DEVELOPMENT_OPS_TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv("DEVELOPMENT_OPS_DATABASE_URL", OPERATIONAL_URL)
    monkeypatch.setenv("WASATCH_DATABASE_URL", OPERATIONAL_URL)
    resolved = wasatch_development_ops_test_database_url()
    assert database_name(resolved) == "wasatch_development_ops_test"
    assert not resolved.endswith("/wasatch_development_ops")


def test_explicit_ops_test_url_must_be_disposable(monkeypatch) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_TEST_DATABASE_URL", OPERATIONAL_URL)
    with pytest.raises(UnsafeTestDatabaseError):
        wasatch_development_ops_test_database_url()


def test_operational_database_names_are_never_disposable() -> None:
    for name in OPERATIONAL_DATABASES:
        assert is_disposable_test_database(name) is False
        with pytest.raises(UnsafeTestDatabaseError):
            assert_disposable_test_database(f"postgresql+psycopg://u:p@h:5432/{name}")


def test_unknown_database_name_is_rejected() -> None:
    with pytest.raises(UnsafeTestDatabaseError):
        assert_disposable_test_database("postgresql+psycopg://u:p@h:5432/wasatch_prod")


def test_missing_database_name_is_rejected() -> None:
    with pytest.raises(UnsafeTestDatabaseError):
        assert_disposable_test_database("postgresql+psycopg://u:p@h:5432/")


def test_approved_test_databases_are_disposable() -> None:
    for name in DISPOSABLE_TEST_DATABASES:
        url = f"postgresql+psycopg://u:p@h:5432/{name}"
        assert is_disposable_test_database(name) is True
        assert assert_disposable_test_database(url) == name


def test_drop_and_recreate_rejects_operational_before_sql() -> None:
    """The guard fires before any connection, so no destructive SQL runs."""
    with pytest.raises(UnsafeTestDatabaseError):
        drop_and_recreate_test_database(OPERATIONAL_URL)


def test_engine_guard_rejects_operational_database() -> None:
    engine = create_engine(
        "postgresql+psycopg://wasatch:replace-me@localhost:5432/wasatch_development_ops"
    )
    try:
        with pytest.raises(UnsafeTestDatabaseError):
            assert_engine_is_disposable(engine)
    finally:
        engine.dispose()
