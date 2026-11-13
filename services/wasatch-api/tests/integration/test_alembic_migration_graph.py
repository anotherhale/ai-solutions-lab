"""Upgrade/downgrade the full Alembic chain on a disposable database."""

from __future__ import annotations

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from wasatch_api.config import REPO_ROOT, get_settings

API_ROOT = REPO_ROOT / "services" / "wasatch-api"
DISPOSABLE_DB = "wasatch_alembic_disposable"


def _ensure_disposable_database(admin_url: str, target: str) -> str:
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        with admin.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": target},
            ).scalar()
            if exists:
                connection.execute(
                    text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = :name AND pid <> pg_backend_pid()"
                    ),
                    {"name": target},
                )
                connection.execute(text(f'DROP DATABASE "{target}"'))
            connection.execute(text(f'CREATE DATABASE "{target}"'))
    finally:
        admin.dispose()
    base = admin_url.rsplit("/", 1)[0]
    return f"{base}/{target}"


@pytest.fixture(scope="module")
def disposable_engine() -> Engine:
    admin_url = os.environ.get("WASATCH_TEST_DATABASE_URL") or os.environ.get(
        "WASATCH_DATABASE_URL",
        "postgresql+psycopg://wasatch:replace-me@localhost:5432/wasatch_test",
    )
    admin_base = admin_url.rsplit("/", 1)[0] + "/wasatch"
    url = _ensure_disposable_database(admin_base, DISPOSABLE_DB)
    os.environ["WASATCH_DATABASE_URL"] = url
    get_settings.cache_clear()
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = create_engine(url, pool_pre_ping=True)
    yield engine
    engine.dispose()
    get_settings.cache_clear()


def test_linear_head_is_0013(disposable_engine: Engine) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    config.set_main_option(
        "sqlalchemy.url",
        disposable_engine.url.render_as_string(hide_password=False),
    )
    command.downgrade(config, "0011")
    command.upgrade(config, "0013")
    with disposable_engine.connect() as connection:
        coordinator = connection.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'development_ops' "
                "AND table_name = 'coordinator_tasks'"
            )
        ).scalar()
        lines = connection.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'invoice_lines'"
            )
        ).scalar()
        payments = connection.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'payments'"
            )
        ).scalar()
    assert coordinator == 1
    assert lines == 1
    assert payments == 1


def test_coordinator_revision_downgrade(disposable_engine: Engine) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    config.set_main_option(
        "sqlalchemy.url",
        disposable_engine.url.render_as_string(hide_password=False),
    )
    command.downgrade(config, "0011")
    try:
        with disposable_engine.connect() as connection:
            missing = connection.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'development_ops' "
                    "AND table_name = 'coordinator_tasks'"
                )
            ).scalar()
        assert missing is None
    finally:
        command.upgrade(config, "head")
