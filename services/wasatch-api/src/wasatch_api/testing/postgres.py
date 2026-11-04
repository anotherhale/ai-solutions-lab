"""Test-only PostgreSQL URL helpers."""

from __future__ import annotations

import os

from sqlalchemy.engine import make_url

DEFAULT_TEST_DATABASE_URL = (
    "postgresql+psycopg://wasatch:replace-me@localhost:5432/wasatch_test"
)


def wasatch_test_database_url() -> str:
    """Database URL for pytest and CI.

    ``WASATCH_TEST_DATABASE_URL`` wins. ``WASATCH_DATABASE_URL`` is used only
    when its database name is ``wasatch_test`` (GitHub Actions). Other values
    are ignored so a shell export for the API or activity CLI cannot redirect
    migration tests onto ``wasatch`` or ``wasatch_development_ops``.
    """
    explicit = os.environ.get("WASATCH_TEST_DATABASE_URL", "").strip()
    if explicit:
        return explicit
    legacy = os.environ.get("WASATCH_DATABASE_URL", "").strip()
    if legacy:
        try:
            if make_url(legacy).database == "wasatch_test":
                return legacy
        except Exception:
            pass
    return DEFAULT_TEST_DATABASE_URL


def wasatch_development_ops_database_url_for_tests() -> str:
    """Ops DB URL aligned with pytest credentials (CI uses ``wasatch`` password)."""
    explicit = os.environ.get("DEVELOPMENT_OPS_DATABASE_URL", "").strip()
    if explicit:
        return explicit
    test_url = wasatch_test_database_url()
    parsed = make_url(test_url)
    if parsed.database == "wasatch_test":
        return parsed.set(database="wasatch_development_ops").render_as_string(
            hide_password=False
        )
    return (
        "postgresql+psycopg://wasatch:replace-me@localhost:5432/wasatch_development_ops"
    )
