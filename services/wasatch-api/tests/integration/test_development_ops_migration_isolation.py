"""Activity events on the ops database survive application migration tests."""

from __future__ import annotations

import os
import uuid

import pytest
from alembic import command
from alembic.config import Config
from development_ops.database import ensure_development_ops_database
from development_ops.models import ActivityEventCreate
from development_ops.persistence.repository import ActivityEventRepository
from development_ops.recorder import ActivityRecorder
from development_ops.taxonomy import EventSeverity, EventType
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from wasatch_api.config import REPO_ROOT, get_settings
from wasatch_api.testing.postgres import wasatch_development_ops_database_url_for_tests

API_ROOT = REPO_ROOT / "services" / "wasatch-api"


@pytest.fixture(scope="module")
def isolated_ops_engine() -> Engine:
    previous_wasatch_url = os.environ.get("WASATCH_DATABASE_URL")
    url = wasatch_development_ops_database_url_for_tests()
    ensure_development_ops_database(url)
    os.environ["WASATCH_DATABASE_URL"] = url
    get_settings.cache_clear()
    alembic_cfg = Config(str(API_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", url)
    alembic_cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    command.upgrade(alembic_cfg, "head")
    engine = create_engine(url, pool_pre_ping=True)
    yield engine
    engine.dispose()
    if previous_wasatch_url is not None:
        os.environ["WASATCH_DATABASE_URL"] = previous_wasatch_url
    else:
        os.environ.pop("WASATCH_DATABASE_URL", None)
    get_settings.cache_clear()


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


def test_activity_on_ops_database_survives_test_db_downgrade(
    isolated_ops_engine: Engine,
    engine: Engine,
) -> None:
    run_id = uuid.uuid4()
    idempotency_key = f"isolation-test:{run_id}"
    ops_session = sessionmaker(bind=isolated_ops_engine, autoflush=False)()
    try:
        recorder = ActivityRecorder(ops_session, notify_slack=False)
        recorder.record(
            ActivityEventCreate(
                run_id=run_id,
                event_type=EventType.PROGRESS_REPORT,
                severity=EventSeverity.INFO,
                title="Isolation regression sentinel",
                idempotency_key=idempotency_key,
                metadata={"test": "migration_isolation"},
            )
        )
    finally:
        ops_session.close()

    config = _alembic_config(engine)
    command.downgrade(config, "0008")
    try:
        with engine.connect() as connection:
            missing = connection.execute(
                text(
                    "SELECT 1 FROM information_schema.schemata "
                    "WHERE schema_name = 'development_ops'"
                )
            ).scalar()
        assert missing is None
    finally:
        command.upgrade(config, "head")

    verify_session = sessionmaker(bind=isolated_ops_engine, autoflush=False)()
    try:
        repo = ActivityEventRepository(verify_session)
        event = repo.get_by_idempotency_key(idempotency_key)
        assert event is not None
        assert event.title == "Isolation regression sentinel"
    finally:
        verify_session.close()
