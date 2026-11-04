from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from wasatch_api.config import REPO_ROOT
from wasatch_api.shared.database.models import EmployeeORM, MessageORM, WorkOrderORM
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
        "approval_requests",
        "approval_decision_history",
        "audit_events",
        "roles",
        "teams",
        "documents",
        "document_versions",
        "document_extractions",
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
    assert first["approval_request"]["created"] == 0
    assert first["approval_request"]["updated"] == 10
    assert first["audit_event"]["created"] == 0
    assert first["audit_event"]["updated"] == 0
    assert first["audit_event"]["skipped"] == 50
    assert second["approval_request"]["updated"] == 10
    assert second["audit_event"]["created"] == 0
    assert second["audit_event"]["updated"] == 0
    assert second["audit_event"]["skipped"] == 50
    assert first["role"]["created"] == 0
    assert first["role"]["updated"] == 12
    assert first["team"]["created"] == 0
    assert first["team"]["updated"] == 5
    assert second["role"]["created"] == 0
    assert second["role"]["updated"] == 12
    assert second["team"]["created"] == 0
    assert second["team"]["updated"] == 5
    assert first["document"]["created"] == 0
    assert first["document"]["updated"] == 30
    assert first["document_version"]["created"] == 0
    assert first["document_version"]["updated"] == 31
    assert first["document_extraction"]["created"] == 0
    assert first["document_extraction"]["updated"] == 18
    assert second["document"]["created"] == 0
    assert second["document"]["updated"] == 30
    assert second["document_version"]["created"] == 0
    assert second["document_extraction"]["created"] == 0
    assert second["document_extraction"]["updated"] == 18


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


def test_employee_role_foreign_key_is_enforced(db_session: Session) -> None:
    now = datetime.now(tz=UTC)
    employee = EmployeeORM(
        id=uuid.uuid4(),
        business_id="emp_9999",
        employee_number="E-9999",
        first_name="No",
        last_name="Role",
        email="no.role@wasatch-business-systems.test",
        role_id=uuid.uuid4(),
        department="dispatch",
        job_title="Dispatcher",
        status="active",
        hire_date=date(2026, 1, 1),
        certifications=[],
        created_at=now,
        updated_at=now,
    )
    db_session.add(employee)
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
    approvals = db_session.execute(
        text("SELECT count(*) FROM approval_requests")
    ).scalar()
    decisions = db_session.execute(
        text("SELECT count(*) FROM approval_decision_history")
    ).scalar()
    audits = db_session.execute(text("SELECT count(*) FROM audit_events")).scalar()
    pending_message = db_session.execute(
        text(
            """
            SELECT ar.business_id
            FROM messages AS msg
            JOIN approval_requests AS ar ON ar.id = msg.approval_request_id
            WHERE msg.business_id = 'msg_0016'
              AND msg.status = 'pending_approval'
              AND msg.requires_approval IS TRUE
            """
        )
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
    assert approvals == 10
    assert decisions == 11
    assert audits == 50
    assert pending_message == "apr_0001"
    roles = db_session.execute(text("SELECT count(*) FROM roles")).scalar()
    teams = db_session.execute(text("SELECT count(*) FROM teams")).scalar()
    approver = db_session.execute(
        text(
            """
            SELECT roles.is_approver
            FROM employees
            JOIN roles ON roles.id = employees.role_id
            WHERE employees.business_id = 'emp_0001'
            """
        )
    ).scalar()
    dispatcher = db_session.execute(
        text(
            """
            SELECT roles.business_id, roles.is_approver, teams.business_id
            FROM employees
            JOIN roles ON roles.id = employees.role_id
            LEFT JOIN teams ON teams.id = employees.team_id
            WHERE employees.business_id = 'emp_0004'
            """
        )
    ).one()
    lead = db_session.execute(
        text(
            """
            SELECT employees.business_id
            FROM teams
            JOIN employees ON employees.id = teams.lead_employee_id
            WHERE teams.business_id = 'team_0001'
            """
        )
    ).scalar()
    manager_team = db_session.execute(
        text("SELECT team_id FROM employees WHERE business_id = 'emp_0001'")
    ).scalar()
    assert roles == 12
    assert teams == 5
    assert approver is True
    assert tuple(dispatcher) == ("role_0004", False, "team_0003")
    assert lead == "emp_0010"
    assert manager_team is None
    documents = db_session.execute(text("SELECT count(*) FROM documents")).scalar()
    versions = db_session.execute(
        text("SELECT count(*) FROM document_versions")
    ).scalar()
    extractions = db_session.execute(
        text("SELECT count(*) FROM document_extractions")
    ).scalar()
    current_version = db_session.execute(
        text(
            """
            SELECT versions.business_id
            FROM documents
            JOIN document_versions AS versions
              ON versions.id = documents.current_version_id
            WHERE documents.business_id = 'doc_0004'
            """
        )
    ).scalar()
    version_count = db_session.execute(
        text(
            """
            SELECT count(*)
            FROM document_versions
            JOIN documents ON documents.id = document_versions.document_id
            WHERE documents.business_id = 'doc_0004'
            """
        )
    ).scalar()
    invoice_id = db_session.execute(
        text("SELECT invoice_id FROM documents WHERE business_id = 'doc_0005'")
    ).scalar()
    vector_columns = db_session.execute(
        text(
            """
            SELECT count(*)
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name IN (
                    'documents', 'document_versions', 'document_extractions'
              )
              AND udt_name = 'vector'
            """
        )
    ).scalar()
    assert documents == 30
    assert versions == 31
    assert extractions == 18
    assert current_version == "dv_0031"
    assert version_count == 2
    assert invoice_id == "inv_0005"
    assert vector_columns == 0
