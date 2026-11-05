"""Upgrade and downgrade revision 0011 on the synthetic database."""

from __future__ import annotations

import os

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from wasatch_api.config import REPO_ROOT, get_settings

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


def test_payment_revision_upgrades_and_downgrades(seeded_engine: Engine) -> None:
    config = _alembic_config(seeded_engine)
    with seeded_engine.connect() as connection:
        count = connection.execute(text("SELECT count(*) FROM payments")).scalar()
    assert count == 20

    command.downgrade(config, "0010")
    try:
        assert "payments" not in set(inspect(seeded_engine).get_table_names())
        command.upgrade(config, "0011")
        with seeded_engine.connect() as connection:
            restored = connection.execute(
                text("SELECT count(*) FROM payments")
            ).scalar()
        assert restored == 20
    finally:
        command.upgrade(config, "head")
