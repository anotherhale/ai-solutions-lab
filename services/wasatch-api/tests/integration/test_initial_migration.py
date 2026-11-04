"""Upgrade and downgrade revision 0001 on the synthetic database."""

from __future__ import annotations

import os

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from wasatch_api.config import REPO_ROOT, get_settings
from wasatch_api.shared.seed import seed_valid_fixtures

API_ROOT = REPO_ROOT / "services" / "wasatch-api"


def _alembic_config(engine: Engine) -> Config:
    os.environ["WASATCH_DATABASE_URL"] = engine.url.render_as_string(
        hide_password=False
    )
    get_settings.cache_clear()
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    config.set_main_option(
        "sqlalchemy.url", engine.url.render_as_string(hide_password=False)
    )
    return config


def _version(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar()


def test_initial_revision_upgrades_and_downgrades(engine: Engine) -> None:
    config = _alembic_config(engine)
    engine.dispose()
    command.downgrade(config, "base")
    try:
        assert _version(engine) is None
        inspector = inspect(engine)
        names = set(inspector.get_table_names())
        assert "customers" not in names
        assert "work_orders" not in names
        assert "employees" not in names
        with engine.connect() as connection:
            vector = connection.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            ).scalar()
        assert vector is None

        command.upgrade(config, "0001")
        assert _version(engine) == "0001"
        upgraded = inspect(engine)
        upgraded_names = set(upgraded.get_table_names())
        assert {"customers", "work_orders", "employees", "equipment"} <= upgraded_names
        with engine.connect() as connection:
            vector = connection.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            ).scalar()
        assert vector == "vector"
    finally:
        command.upgrade(config, "head")
        session = sessionmaker(bind=engine, autoflush=False)()
        try:
            seed_valid_fixtures(session, REPO_ROOT / "data" / "fixtures" / "valid")
        finally:
            session.close()
