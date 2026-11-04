#!/usr/bin/env python3
"""Create the target database, migrate, and seed for host-run API checks."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "services" / "wasatch-api"
FIXTURES = REPO_ROOT / "data" / "fixtures" / "valid"


def _database_url() -> str:
    return os.environ.get(
        "WASATCH_DATABASE_URL",
        "postgresql+psycopg://wasatch:replace-me@localhost:5432/wasatch",
    )


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


def ensure_database(database_url: str) -> None:
    parsed = make_url(database_url)
    target = parsed.database
    if not target or target in {"wasatch", "postgres"}:
        return
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
            return
        except Exception as exc:
            if _missing_database(exc):
                continue
            raise
        finally:
            admin_engine.dispose()


def main() -> int:
    database_url = _database_url()
    os.environ["WASATCH_DATABASE_URL"] = database_url
    sys.path.insert(0, str(API_ROOT / "src"))
    from wasatch_api.config import get_settings  # noqa: E402
    from wasatch_api.shared.database.session import reset_engine  # noqa: E402
    from wasatch_api.shared.seed import seed_valid_fixtures  # noqa: E402

    get_settings.cache_clear()
    reset_engine()
    ensure_database(database_url)
    alembic_cfg = Config(str(API_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    alembic_cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    command.upgrade(alembic_cfg, "head")
    engine = create_engine(database_url, pool_pre_ping=True)
    session = sessionmaker(bind=engine, autoflush=False)()
    try:
        seed_valid_fixtures(session, FIXTURES)
    finally:
        session.close()
        engine.dispose()
        reset_engine()
        get_settings.cache_clear()
    print(f"Prepared {database_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
