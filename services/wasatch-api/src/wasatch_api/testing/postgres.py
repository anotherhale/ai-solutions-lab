"""Test-only PostgreSQL URL helpers."""

from __future__ import annotations

import os

DEFAULT_TEST_DATABASE_URL = (
    "postgresql+psycopg://wasatch:replace-me@localhost:5432/wasatch_test"
)


def wasatch_test_database_url() -> str:
    """Database URL for pytest and CI.

    ``WASATCH_TEST_DATABASE_URL`` wins. ``WASATCH_DATABASE_URL`` is ignored so
    a shell export for the API or activity CLI cannot redirect migration tests
    onto the laboratory ``wasatch`` or ``wasatch_development_ops`` databases.
    """
    return os.environ.get("WASATCH_TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
