"""Development activity log database URL and provisioning."""

from __future__ import annotations

import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

DEFAULT_DEVELOPMENT_OPS_DATABASE_URL = (
    "postgresql+psycopg://wasatch:replace-me@localhost:5432/wasatch_development_ops"
)


def development_ops_database_url() -> str:
    """URL for activity_events only.

    Never fall back to the Wasatch API test URL. Laboratory agents record here;
    pytest migration tests use ``wasatch_test`` and must not wipe this database.
    """
    explicit = os.environ.get("DEVELOPMENT_OPS_DATABASE_URL", "").strip()
    if explicit:
        return explicit
    legacy = os.environ.get("WASATCH_DATABASE_URL", "").strip()
    if legacy and legacy.endswith("/wasatch_development_ops"):
        return legacy
    return DEFAULT_DEVELOPMENT_OPS_DATABASE_URL


def _missing_database(exc: BaseException) -> bool:
    sqlstate = getattr(exc, "sqlstate", None)
    if sqlstate == "3D000":
        return True
    origin = getattr(exc, "orig", None)
    if origin is not None:
        nested = getattr(origin, "sqlstate", None)
        if nested == "3D000":
            return True
    message = str(exc).lower()
    return "database" in message and "does not exist" in message


def ensure_development_ops_database(database_url: str | None = None) -> str:
    """Create the development_ops database when missing."""
    url = database_url or development_ops_database_url()
    parsed = make_url(url)
    target = parsed.database
    if not target or target in {"wasatch", "postgres"}:
        return url
    for admin_name in ("wasatch", "postgres"):
        if admin_name == target:
            continue
        admin_engine = create_engine(
            parsed.set(database=admin_name),
            isolation_level="AUTOCOMMIT",
            pool_pre_ping=True,
        )
        try:
            with admin_engine.connect() as connection:
                exists = connection.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :name"),
                    {"name": target},
                ).scalar()
                if not exists:
                    connection.execute(text(f'CREATE DATABASE "{target}"'))
            return url
        except Exception as exc:
            if _missing_database(exc):
                continue
            raise
        finally:
            admin_engine.dispose()
    return url
