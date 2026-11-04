"""PostgreSQL integration tests for development_ops.activity_events."""

from __future__ import annotations

import os
import uuid

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from wasatch_api.config import REPO_ROOT, get_settings

API_ROOT = REPO_ROOT / "services" / "wasatch-api"
from development_ops.models import ActivityEventCreate, GitHubReference  # noqa: E402
from development_ops.persistence.repository import (  # noqa: E402
    ActivityEventQuery,
    ActivityEventRepository,
)
from development_ops.recorder import ActivityRecorder  # noqa: E402
from development_ops.slack.notifier import CursorSlackConfirmationNotifier  # noqa: E402
from development_ops.taxonomy import EventSeverity, EventType  # noqa: E402


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


def test_development_ops_schema_exists(engine: Engine) -> None:
    with engine.connect() as connection:
        schema_exists = connection.execute(
            text(
                "SELECT 1 FROM information_schema.schemata "
                "WHERE schema_name = 'development_ops'"
            )
        ).scalar()
    assert schema_exists == 1


def test_activity_events_table_and_indexes(engine: Engine) -> None:
    inspector = inspect(engine)
    assert "activity_events" in inspector.get_table_names(schema="development_ops")
    indexes = {
        index["name"]
        for index in inspector.get_indexes("activity_events", schema="development_ops")
    }
    assert "ix_activity_events_run_id_occurred_at" in indexes


def test_append_and_query_events(engine: Engine) -> None:
    session = sessionmaker(bind=engine, autoflush=False)()
    run_id = uuid.uuid4()
    try:
        recorder = ActivityRecorder(session, notify_slack=False)
        payload = ActivityEventCreate(
            run_id=run_id,
            task_id="activity-log-foundation",
            event_type=EventType.IMPLEMENTATION_MILESTONE,
            severity=EventSeverity.NOTICE,
            title="Persist activity event",
            summary="Integration test",
            idempotency_key=f"test:{run_id}:milestone",
            github=GitHubReference(
                repository="anotherhale/ai-solutions-lab",
                pull_number=99,
            ),
        )
        first = recorder.record(payload)
        second = recorder.record(payload)
        assert first.created is True
        assert second.created is False
        assert first.event.id == second.event.id

        repo = ActivityEventRepository(session)
        rows = repo.search(ActivityEventQuery(run_id=run_id))
        assert len(rows) == 1
        assert rows[0].github.pull_number == 99
    finally:
        session.close()


def test_slack_failure_does_not_drop_event(engine: Engine) -> None:
    session = sessionmaker(bind=engine, autoflush=False)()
    run_id = uuid.uuid4()
    try:
        recorder = ActivityRecorder(
            session,
            notifier=CursorSlackConfirmationNotifier(
                channel_id="C0CFJDH7PTJ",
                message_ts="1234.5678",
            ),
            notify_slack=True,
        )
        payload = ActivityEventCreate(
            run_id=run_id,
            event_type=EventType.PROGRESS_REPORT,
            severity=EventSeverity.INFO,
            title="Slack delivery recorded",
            idempotency_key=f"test:{run_id}:slack",
        )
        result = recorder.record(payload)
        assert result.slack_delivered is True
        assert result.event.slack.message_ts == "1234.5678"
    finally:
        session.close()


def test_revision_0009_downgrade_upgrade(engine: Engine) -> None:
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
        command.upgrade(config, "0009")
        assert "activity_events" in inspect(engine).get_table_names(
            schema="development_ops"
        )
    finally:
        command.upgrade(config, "head")
