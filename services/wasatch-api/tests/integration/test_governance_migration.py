"""Upgrade and downgrade revision 0003 on the synthetic database."""

from __future__ import annotations

import importlib.util
import os
import uuid

import pytest
from alembic import command
from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import sessionmaker

from wasatch_api.config import REPO_ROOT, get_settings
from wasatch_api.shared.seed import seed_valid_fixtures

API_ROOT = REPO_ROOT / "services" / "wasatch-api"
REVISION_PATH = API_ROOT / "alembic" / "versions" / "0003_governance_slice.py"


def _revision():
    spec = importlib.util.spec_from_file_location("revision_0003", REVISION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def _column(inspector, table: str, name: str) -> dict:
    for column in inspector.get_columns(table):
        if column["name"] == name:
            return column
    raise AssertionError(f"{table}.{name} is missing")


def _is_uuid(column: dict) -> bool:
    return "UUID" in str(column["type"]).upper()


def _is_string(column: dict) -> bool:
    label = str(column["type"]).upper()
    return "CHAR" in label or "STRING" in label or "VARCHAR" in label


def _message_approval(engine: Engine, message_id: str):
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT approval_request_id FROM messages WHERE business_id = :id"),
            {"id": message_id},
        ).scalar()


def _has_unique_business_id(inspector, table: str) -> bool:
    for constraint in inspector.get_unique_constraints(table):
        if constraint.get("column_names") == ["business_id"]:
            return True
    for index in inspector.get_indexes(table):
        if index.get("unique") and index.get("column_names") == ["business_id"]:
            return True
    return False


def _reseed(engine: Engine) -> None:
    session = sessionmaker(bind=engine, autoflush=False)()
    try:
        seed_valid_fixtures(session, REPO_ROOT / "data" / "fixtures" / "valid")
    finally:
        session.close()


def test_governance_revision_exposes_no_audit_mutation() -> None:
    source = REVISION_PATH.read_text(encoding="utf-8")
    for line in source.splitlines():
        upper = line.strip().upper()
        assert not upper.startswith("UPDATE AUDIT_EVENTS")
        assert not upper.startswith("DELETE FROM AUDIT_EVENTS")


def test_governance_revision_upgrades_and_downgrades(seeded_engine: Engine) -> None:
    config = _alembic_config(seeded_engine)
    revision = _revision()
    seeded_engine.dispose()
    command.downgrade(config, "0002")
    try:
        assert _version(seeded_engine) == "0002"
        inspector = inspect(seeded_engine)
        names = set(inspector.get_table_names())
        assert "approval_requests" not in names
        assert "approval_decision_history" not in names
        assert "audit_events" not in names
        column = _column(inspector, "messages", "approval_request_id")
        assert _is_string(column)
        assert _message_approval(seeded_engine, "msg_0016") == "apr_0001"
        assert _message_approval(seeded_engine, "msg_0017") == "apr_0004"
        assert _message_approval(seeded_engine, "msg_0001") is None

        _assert_upgrade_backfill_rolls_back(seeded_engine, revision)
        assert "approval_requests" not in set(inspect(seeded_engine).get_table_names())

        command.upgrade(config, "0003")
        assert _version(seeded_engine) == "0003"
        upgraded = inspect(seeded_engine)
        upgraded_names = set(upgraded.get_table_names())
        assert {"approval_requests", "audit_events"} <= upgraded_names
        for table in ("approval_requests", "audit_events"):
            assert upgraded.get_pk_constraint(table)["constrained_columns"] == ["id"]
            assert _is_uuid(_column(upgraded, table, "id"))
            assert _has_unique_business_id(upgraded, table)
        audit_columns = {item["name"] for item in upgraded.get_columns("audit_events")}
        assert "updated_at" not in audit_columns
        assert "created_at" not in audit_columns
        message_column = _column(upgraded, "messages", "approval_request_id")
        assert _is_uuid(message_column)
        message_keys = [
            fk
            for fk in upgraded.get_foreign_keys("messages")
            if fk.get("referred_table") == "approval_requests"
        ]
        assert len(message_keys) == 1
        assert message_keys[0]["constrained_columns"] == ["approval_request_id"]
        assert message_keys[0]["name"] == "fk_messages_approval_request"
        audit_keys = [
            fk
            for fk in upgraded.get_foreign_keys("audit_events")
            if fk.get("referred_table") == "approval_requests"
        ]
        assert len(audit_keys) == 1
        assert audit_keys[0]["name"] == "fk_audit_events_approval_request"
        assert _message_approval(seeded_engine, "msg_0016") is None
        with seeded_engine.connect() as connection:
            trigger = connection.execute(
                text("SELECT tgname FROM pg_trigger WHERE tgname = :name"),
                {"name": "audit_events_insert_only"},
            ).scalar()
        assert trigger == "audit_events_insert_only"
    finally:
        command.upgrade(config, "head")
        _reseed(seeded_engine)

    with seeded_engine.connect() as connection:
        linked = connection.execute(
            text(
                """
                SELECT apr.business_id
                FROM messages AS msg
                JOIN approval_requests AS apr ON apr.id = msg.approval_request_id
                WHERE msg.business_id = 'msg_0016'
                """
            )
        ).scalar()
        approvals = connection.execute(
            text("SELECT count(*) FROM approval_requests")
        ).scalar()
        audits = connection.execute(text("SELECT count(*) FROM audit_events")).scalar()
    assert linked == "apr_0001"
    assert approvals == 10
    assert audits == 50
    _assert_audit_events_are_insert_only(seeded_engine)


def _assert_upgrade_backfill_rolls_back(engine: Engine, revision) -> None:
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                revision.create_governance_tables()
                approval_id = uuid.uuid4()
                inserted = connection.execute(
                    text(
                        """
                        INSERT INTO approval_requests (
                            id, business_id, action_type, status,
                            requested_by_employee_id, subject_type, subject_id,
                            rationale, requested_at, created_at, updated_at
                        )
                        SELECT
                            :id, 'apr_0001', 'send_customer_message', 'pending',
                            id, 'message', 'msg_0016',
                            'Backfill probe', created_at, created_at, updated_at
                        FROM employees
                        WHERE business_id = 'emp_0006'
                        """
                    ),
                    {"id": approval_id},
                ).rowcount
                assert inserted == 1
                revision.replace_message_approval_column()
                linked = connection.execute(
                    text(
                        """
                        SELECT approval_request_id
                        FROM messages
                        WHERE business_id = 'msg_0016'
                        """
                    )
                ).scalar()
                unmatched = connection.execute(
                    text(
                        """
                        SELECT approval_request_id
                        FROM messages
                        WHERE business_id = 'msg_0017'
                        """
                    )
                ).scalar()
                assert linked == approval_id
                assert unmatched is None
        finally:
            transaction.rollback()


def _assert_audit_events_are_insert_only(engine: Engine) -> None:
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
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            with pytest.raises(DatabaseError, match="insert-only"):
                connection.execute(
                    text("DELETE FROM audit_events WHERE business_id = 'aud_0001'")
                )
        finally:
            transaction.rollback()
    with engine.connect() as connection:
        remaining = connection.execute(
            text("SELECT count(*) FROM audit_events")
        ).scalar()
    assert remaining == 50
