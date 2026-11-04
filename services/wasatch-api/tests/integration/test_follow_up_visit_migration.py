"""Upgrade and downgrade revision 0007 on the synthetic database."""

from __future__ import annotations

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DatabaseError, IntegrityError

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


def _version(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar()


def test_follow_up_revision_upgrades_and_downgrades(seeded_engine: Engine) -> None:
    engine = seeded_engine
    config = _alembic_config(engine)
    engine.dispose()
    try:
        command.downgrade(config, "0006")
        assert _version(engine) == "0006"
        tables = set(inspect(engine).get_table_names())
        assert "follow_up_visits" not in tables
        assert "procedure_page_embeddings" in tables
        assert "audit_events" in tables

        command.upgrade(config, "0007")
        assert _version(engine) == "0007"
        upgraded = inspect(engine)
        assert "follow_up_visits" in set(upgraded.get_table_names())
        columns = {
            column["name"] for column in upgraded.get_columns("follow_up_visits")
        }
        assert "embedding" not in columns
        assert "scheduled_for" not in columns
        assert "assigned_employee_id" not in columns
        assert columns >= {
            "business_id",
            "approval_request_id",
            "message_id",
            "status",
            "opened_by_employee_id",
            "decided_by_employee_id",
        }
        _assert_no_vector_column(engine)
        _assert_audit_events_stay_insert_only(engine)
        _assert_unapproved_shape_is_rejected(engine)
        with engine.connect() as connection:
            count = connection.execute(
                text("SELECT count(*) FROM follow_up_visits")
            ).scalar()
            audits = connection.execute(
                text("SELECT count(*) FROM audit_events")
            ).scalar()
        assert count == 0
        assert audits == 50
    finally:
        command.upgrade(config, "head")
        get_settings.cache_clear()


def _assert_no_vector_column(engine: Engine) -> None:
    with engine.connect() as connection:
        vectors = connection.execute(
            text(
                """
                SELECT count(*)
                FROM pg_attribute
                JOIN pg_type ON pg_type.oid = pg_attribute.atttypid
                WHERE attrelid = 'follow_up_visits'::regclass
                  AND NOT attisdropped
                  AND typname = 'vector'
                """
            )
        ).scalar()
    assert vectors == 0


def _assert_audit_events_stay_insert_only(engine: Engine) -> None:
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            with pytest.raises(DatabaseError, match="insert-only"):
                connection.execute(
                    text(
                        """
                        UPDATE audit_events
                        SET outcome = 'failed'
                        WHERE business_id = 'aud_0001'
                        """
                    )
                )
        finally:
            transaction.rollback()


def _assert_unapproved_shape_is_rejected(engine: Engine) -> None:
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        """
                        INSERT INTO follow_up_visits (
                            id, business_id, approval_request_id, message_id,
                            support_ticket_id, status, opened_by_employee_id,
                            opened_at, decided_by_employee_id, decided_at,
                            created_at, updated_at
                        )
                        SELECT
                            gen_random_uuid(), 'fuv_0001', approval_requests.id,
                            messages.id, messages.support_ticket_id, 'confirmed',
                            employees.id, now(), NULL, NULL, now(), now()
                        FROM approval_requests
                        JOIN messages ON messages.business_id = 'msg_0016'
                        JOIN employees ON employees.business_id = 'emp_0004'
                        WHERE approval_requests.business_id = 'apr_0001'
                        """
                    )
                )
        finally:
            transaction.rollback()
