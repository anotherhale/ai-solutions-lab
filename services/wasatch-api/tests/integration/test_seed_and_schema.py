from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from wasatch_api.config import REPO_ROOT
from wasatch_api.shared.database.models import MessageORM, WorkOrderORM
from wasatch_api.shared.seed import SeedError, seed_valid_fixtures


def test_pgvector_extension_exists(engine: Engine) -> None:
    with engine.connect() as connection:
        exists = connection.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        ).scalar()
    assert exists == "vector"


def test_expected_tables_exist(engine: Engine) -> None:
    inspector = inspect(engine)
    names = set(inspector.get_table_names())
    expected = {
        "customers",
        "contacts",
        "service_locations",
        "employees",
        "equipment",
        "work_orders",
        "work_order_tasks",
        "appointments",
        "work_order_assignments",
        "work_order_equipment",
        "support_tickets",
        "messages",
        "interactions",
        "alembic_version",
    }
    assert expected <= names


def test_seed_is_idempotent(seeded_engine: Engine) -> None:
    session = sessionmaker(bind=seeded_engine)()
    try:
        first = seed_valid_fixtures(session, REPO_ROOT / "data" / "fixtures" / "valid")
        second = seed_valid_fixtures(session, REPO_ROOT / "data" / "fixtures" / "valid")
    finally:
        session.close()
    assert first["customer"]["created"] == 0
    assert first["work_order"]["updated"] >= 1
    assert first["support_ticket"]["created"] == 0
    assert first["support_ticket"]["updated"] == 15
    assert second["customer"]["created"] == 0
    assert second["work_order"]["created"] == 0
    assert second["appointment"]["updated"] >= 1
    assert second["support_ticket"]["created"] == 0
    assert second["message"]["created"] == 0
    assert second["message"]["updated"] == 17
    assert second["interaction"]["created"] == 0
    assert second["interaction"]["updated"] == 15


def test_seed_rejects_quality_issues(db_session: Session) -> None:
    with pytest.raises(SeedError):
        seed_valid_fixtures(
            db_session, REPO_ROOT / "data" / "fixtures" / "quality-issues"
        )


def test_foreign_key_is_enforced(db_session: Session) -> None:
    work_order = WorkOrderORM(
        id=uuid.uuid4(),
        business_id="wo_9999",
        customer_id=uuid.uuid4(),
        service_location_id=uuid.uuid4(),
        status="created",
        priority="normal",
        work_type="repair",
        summary="Invalid",
        opened_at=datetime.now(tz=UTC),
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )
    db_session.add(work_order)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_message_requires_ticket(db_session: Session) -> None:
    message = MessageORM(
        id=uuid.uuid4(),
        business_id="msg_9999",
        support_ticket_id=uuid.uuid4(),
        direction="inbound",
        channel="phone",
        body="Missing ticket",
        status="sent",
        requires_approval=False,
        sent_at=datetime.now(tz=UTC),
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )
    db_session.add(message)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_seeded_counts_match_slice(db_session: Session) -> None:
    customers = db_session.execute(text("SELECT count(*) FROM customers")).scalar()
    locations = db_session.execute(
        text("SELECT count(*) FROM service_locations")
    ).scalar()
    work_orders = db_session.execute(text("SELECT count(*) FROM work_orders")).scalar()
    tickets = db_session.execute(text("SELECT count(*) FROM support_tickets")).scalar()
    messages = db_session.execute(text("SELECT count(*) FROM messages")).scalar()
    interactions = db_session.execute(
        text("SELECT count(*) FROM interactions")
    ).scalar()
    linked = db_session.execute(
        text(
            """
            SELECT count(*)
            FROM work_orders AS wo
            JOIN support_tickets AS st ON st.id = wo.support_ticket_id
            """
        )
    ).scalar()
    assert customers == 15
    assert locations == 20
    assert work_orders == 40
    assert tickets == 15
    assert messages == 17
    assert interactions == 15
    assert linked == 15
