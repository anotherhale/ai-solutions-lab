"""Upgrade and downgrade revision 0002 on the synthetic database."""

from __future__ import annotations

import importlib.util
import os
import uuid

from alembic import command
from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from wasatch_api.config import REPO_ROOT, get_settings
from wasatch_api.shared.seed import seed_valid_fixtures

API_ROOT = REPO_ROOT / "services" / "wasatch-api"


def _revision():
    path = API_ROOT / "alembic" / "versions" / "0002_customer_service_slice.py"
    spec = importlib.util.spec_from_file_location("revision_0002", path)
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


def _ticket_business_id(engine: Engine, work_order_id: str) -> str | None:
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT support_ticket_id FROM work_orders WHERE business_id = :id"),
            {"id": work_order_id},
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


def test_customer_service_revision_upgrades_and_downgrades(
    seeded_engine: Engine,
) -> None:
    config = _alembic_config(seeded_engine)
    revision = _revision()
    seeded_engine.dispose()
    command.downgrade(config, "0001")
    try:
        assert _version(seeded_engine) == "0001"
        inspector = inspect(seeded_engine)
        names = set(inspector.get_table_names())
        assert "support_tickets" not in names
        assert "messages" not in names
        assert "interactions" not in names
        column = _column(inspector, "work_orders", "support_ticket_id")
        assert _is_string(column)
        assert _ticket_business_id(seeded_engine, "wo_0001") == "tkt_0001"
        assert _ticket_business_id(seeded_engine, "wo_0002") == "tkt_0002"
        assert _ticket_business_id(seeded_engine, "wo_0016") is None

        _assert_upgrade_backfill_rolls_back(seeded_engine, revision)
        assert "support_tickets" not in set(inspect(seeded_engine).get_table_names())

        command.upgrade(config, "head")
        assert _version(seeded_engine) == "0002"
        upgraded = inspect(seeded_engine)
        upgraded_names = set(upgraded.get_table_names())
        assert {"support_tickets", "messages", "interactions"} <= upgraded_names
        for table in ("support_tickets", "messages", "interactions"):
            assert upgraded.get_pk_constraint(table)["constrained_columns"] == ["id"]
            assert _is_uuid(_column(upgraded, table, "id"))
            assert _has_unique_business_id(upgraded, table)
        ticket_column = _column(upgraded, "work_orders", "support_ticket_id")
        assert _is_uuid(ticket_column)
        foreign_keys = [
            fk
            for fk in upgraded.get_foreign_keys("work_orders")
            if fk.get("referred_table") == "support_tickets"
        ]
        assert len(foreign_keys) == 1
        assert foreign_keys[0]["constrained_columns"] == ["support_ticket_id"]
        assert foreign_keys[0]["name"] == "fk_work_orders_support_ticket"
        ondelete = (foreign_keys[0].get("options") or {}).get("ondelete")
        if ondelete is not None:
            assert ondelete.upper() == "SET NULL"
        assert _ticket_business_id(seeded_engine, "wo_0001") is None
    finally:
        command.upgrade(config, "head")
        _reseed(seeded_engine)

    with seeded_engine.connect() as connection:
        linked = connection.execute(
            text(
                """
                SELECT st.business_id
                FROM work_orders AS wo
                JOIN support_tickets AS st ON st.id = wo.support_ticket_id
                WHERE wo.business_id = 'wo_0001'
                """
            )
        ).scalar()
        tickets = connection.execute(
            text("SELECT count(*) FROM support_tickets")
        ).scalar()
        messages = connection.execute(text("SELECT count(*) FROM messages")).scalar()
        interactions = connection.execute(
            text("SELECT count(*) FROM interactions")
        ).scalar()
    assert linked == "tkt_0001"
    assert tickets == 15
    assert messages == 17
    assert interactions == 15


def _assert_upgrade_backfill_rolls_back(engine: Engine, revision) -> None:
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                revision.create_customer_service_tables()
                ticket_id = uuid.uuid4()
                inserted = connection.execute(
                    text(
                        """
                        INSERT INTO support_tickets (
                            id, business_id, customer_id, contact_id,
                            service_location_id, work_order_id, status, priority,
                            channel, subject, opened_at, related_document_ids,
                            created_at, updated_at
                        )
                        SELECT
                            :id, 'tkt_0001', customer_id, requested_by_contact_id,
                            service_location_id, id, 'opened', 'normal', 'phone',
                            'Backfill probe', opened_at, ARRAY[]::varchar[],
                            created_at, updated_at
                        FROM work_orders
                        WHERE business_id = 'wo_0001'
                        """
                    ),
                    {"id": ticket_id},
                ).rowcount
                assert inserted == 1
                revision.replace_work_order_support_ticket_column()
                linked = connection.execute(
                    text(
                        """
                        SELECT support_ticket_id
                        FROM work_orders
                        WHERE business_id = 'wo_0001'
                        """
                    )
                ).scalar()
                other = connection.execute(
                    text(
                        """
                        SELECT support_ticket_id
                        FROM work_orders
                        WHERE business_id = 'wo_0002'
                        """
                    )
                ).scalar()
                assert linked == ticket_id
                assert other is None
        finally:
            transaction.rollback()
