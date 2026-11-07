"""Coordinator integration fixtures must never target operational telemetry.

These tests use only the disposable ``wasatch_development_ops_test`` database.
They never connect to ``wasatch_development_ops``.
"""

from __future__ import annotations

import uuid

import pytest
from development_ops.models import ActivityEventCreate
from development_ops.persistence.repository import (
    ActivityEventQuery,
    ActivityEventRepository,
)
from development_ops.recorder import ActivityRecorder
from development_ops.taxonomy import EventSeverity, EventType
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from wasatch_api.testing.postgres import (
    UnsafeTestDatabaseError,
    assert_engine_is_disposable,
    database_name,
)

OPERATIONAL_URL = (
    "postgresql+psycopg://wasatch:replace-me@localhost:5432/wasatch_development_ops"
)


def _name(engine: Engine) -> str:
    return database_name(engine.url.render_as_string(hide_password=False))


@pytest.fixture(autouse=True)
def _clean_disposable_ops_tables(ops_test_engine: Engine) -> None:
    """Clear only the disposable ops-test database this module may write to."""
    assert_engine_is_disposable(ops_test_engine)
    with ops_test_engine.begin() as connection:
        connection.execute(text("DELETE FROM development_ops.activity_events"))
        connection.execute(text("DELETE FROM development_ops.coordinator_tasks"))


def test_ops_test_engine_resolves_to_disposable_database(
    ops_test_engine: Engine,
) -> None:
    assert _name(ops_test_engine) == "wasatch_development_ops_test"
    assert _name(ops_test_engine) != "wasatch_development_ops"
    assert_engine_is_disposable(ops_test_engine)


def test_ops_test_engine_is_migrated(ops_test_engine: Engine) -> None:
    with ops_test_engine.connect() as connection:
        found = connection.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'development_ops' "
                "AND table_name = 'activity_events'"
            )
        ).scalar()
    assert found == 1


def test_operational_url_is_rejected_before_destructive_sql() -> None:
    """The guard fails closed before any connection is attempted."""
    engine = create_engine(OPERATIONAL_URL, pool_pre_ping=True)
    try:
        with pytest.raises(UnsafeTestDatabaseError):
            assert_engine_is_disposable(engine)
    finally:
        engine.dispose()


def test_activity_events_persist_in_disposable_database(
    ops_test_engine: Engine,
) -> None:
    """Recording and reading activity works without touching live telemetry."""
    run_id = uuid.uuid4()
    session = sessionmaker(bind=ops_test_engine, autoflush=False)()
    try:
        ActivityRecorder(session, notify_slack=False).record(
            ActivityEventCreate(
                run_id=run_id,
                event_type=EventType.PROGRESS_REPORT,
                severity=EventSeverity.INFO,
                title="Disposable telemetry probe",
                idempotency_key=f"isolation:{run_id}",
            )
        )
        events = ActivityEventRepository(session).search(
            ActivityEventQuery(run_id=run_id, limit=10)
        )
    finally:
        session.close()
    assert len(events) == 1
    assert events[0].title == "Disposable telemetry probe"
