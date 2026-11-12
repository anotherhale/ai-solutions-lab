"""Test-only PostgreSQL URL helpers and destructive-operation guards.

Every helper here resolves to a *disposable* database. Operational databases
(``wasatch``, ``wasatch_development_ops``) and server maintenance databases
(``postgres``, ``template0``, ``template1``) are refused before any destructive
SQL runs, so a stray environment export cannot redirect pytest at live data.
"""

from __future__ import annotations

import os
import re

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

DEFAULT_TEST_DATABASE_URL = (
    "postgresql+psycopg://wasatch:replace-me@localhost:5432/wasatch_test"
)

# Databases the test suite may create, drop, or clear.
DISPOSABLE_TEST_DATABASES: frozenset[str] = frozenset(
    {
        "wasatch_test",
        "wasatch_development_ops_test",
        "wasatch_alembic_disposable",
    }
)

# Operational and server-maintenance databases. Never a test target.
OPERATIONAL_DATABASES: frozenset[str] = frozenset(
    {
        "wasatch",
        "wasatch_development_ops",
        "postgres",
        "template0",
        "template1",
    }
)

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class UnsafeTestDatabaseError(RuntimeError):
    """Raised when a test would touch a non-disposable database."""


def database_name(url: str) -> str:
    """Return the database name from ``url`` or fail closed."""
    name = make_url(url).database
    if not name:
        raise UnsafeTestDatabaseError(f"database URL has no database name: {url!r}")
    if not _IDENTIFIER.match(name):
        raise UnsafeTestDatabaseError(f"unsafe database identifier: {name!r}")
    return name


def is_disposable_test_database(name: str) -> bool:
    """True only for a database the suite is allowed to destroy."""
    if name in OPERATIONAL_DATABASES:
        return False
    return (
        name in DISPOSABLE_TEST_DATABASES
        or name.endswith("_test")
        or name.endswith("_disposable")
    )


def assert_disposable_test_database(url: str) -> str:
    """Fail closed unless ``url`` names a disposable test database.

    Returns the database name. Raises :class:`UnsafeTestDatabaseError` for an
    operational, maintenance, missing, or unrecognized database so destructive
    setup and teardown never reach a live database.
    """
    name = database_name(url)
    if name in OPERATIONAL_DATABASES:
        raise UnsafeTestDatabaseError(
            f"refusing to run tests against operational database {name!r}"
        )
    if not is_disposable_test_database(name):
        raise UnsafeTestDatabaseError(
            f"database {name!r} is not an approved disposable test database; "
            f"allowed: {sorted(DISPOSABLE_TEST_DATABASES)}"
        )
    return name


def assert_engine_is_disposable(engine: Engine) -> str:
    """Fail closed when an engine is bound to a non-disposable database."""
    return assert_disposable_test_database(
        engine.url.render_as_string(hide_password=False)
    )


def wasatch_test_database_url() -> str:
    """Database URL for pytest and CI.

    ``WASATCH_TEST_DATABASE_URL`` wins but must name a disposable database.
    ``WASATCH_DATABASE_URL`` is used only when its database name is
    ``wasatch_test`` (GitHub Actions). Other values are ignored so a shell
    export for the API or activity CLI cannot redirect migration tests onto
    ``wasatch`` or ``wasatch_development_ops``.
    """
    explicit = os.environ.get("WASATCH_TEST_DATABASE_URL", "").strip()
    if explicit:
        assert_disposable_test_database(explicit)
        return explicit
    legacy = os.environ.get("WASATCH_DATABASE_URL", "").strip()
    if legacy:
        try:
            if make_url(legacy).database == "wasatch_test":
                return legacy
        except Exception:
            pass
    return DEFAULT_TEST_DATABASE_URL


def wasatch_development_ops_test_database_url() -> str:
    """Disposable ops-test database URL for pytest.

    This never returns the operational ``wasatch_development_ops`` database,
    even when ``DEVELOPMENT_OPS_DATABASE_URL`` points at it. An explicit
    ``DEVELOPMENT_OPS_TEST_DATABASE_URL`` is honored only when it names a
    disposable database; otherwise the name is derived from the test URL.
    """
    explicit = os.environ.get("DEVELOPMENT_OPS_TEST_DATABASE_URL", "").strip()
    if explicit:
        assert_disposable_test_database(explicit)
        return explicit
    parsed = make_url(wasatch_test_database_url())
    derived = parsed.set(database="wasatch_development_ops_test").render_as_string(
        hide_password=False
    )
    assert_disposable_test_database(derived)
    return derived


def drop_and_recreate_test_database(url: str) -> str:
    """Drop and recreate a disposable test database, guarded.

    The guard runs before any connection or destructive SQL, so an operational
    URL is rejected without touching the server.
    """
    name = assert_disposable_test_database(url)
    parsed = make_url(url)
    last_error: Exception | None = None
    for admin_name in ("wasatch", "postgres"):
        if admin_name == name:
            continue
        admin = create_engine(
            parsed.set(database=admin_name),
            isolation_level="AUTOCOMMIT",
            pool_pre_ping=True,
        )
        try:
            with admin.connect() as connection:
                connection.execute(
                    text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = :name AND pid <> pg_backend_pid()"
                    ),
                    {"name": name},
                )
                connection.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
                connection.execute(text(f'CREATE DATABASE "{name}"'))
            return url
        except Exception as exc:
            last_error = exc
            continue
        finally:
            admin.dispose()
    if last_error is not None:
        raise last_error
    return url
