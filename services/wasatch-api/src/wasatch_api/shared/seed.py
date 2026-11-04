"""Idempotent loader for valid Wasatch synthetic fixtures.

Audit events are insert-only. A later seed skips an audit row that already exists.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from wasatch_api.shared.database.models import (
    AppointmentORM,
    ApprovalDecisionORM,
    ApprovalRequestORM,
    AuditEventORM,
    ContactORM,
    CustomerORM,
    EmployeeORM,
    EquipmentORM,
    InteractionORM,
    MessageORM,
    RoleORM,
    ServiceLocationORM,
    SupportTicketORM,
    TeamORM,
    WorkOrderORM,
    WorkOrderTaskORM,
)
from wasatch_api.shared.time import parse_date, parse_datetime

QUALITY_DIR_NAME = "quality-issues"


class SeedError(ValueError):
    """Fixture data cannot be loaded."""


def _load_records(fixtures_dir: Path, filename: str) -> list[dict]:
    path = fixtures_dir / filename
    if QUALITY_DIR_NAME in path.parts:
        raise SeedError("refusing to load quality-issue fixtures")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("synthetic") is not True:
        raise SeedError(f"{filename} is not labeled synthetic")
    records = payload.get("records")
    if not isinstance(records, list):
        raise SeedError(f"{filename} records must be an array")
    return records


def _get_by_business_id(session: Session, model, business_id: str):
    return session.scalar(select(model).where(model.business_id == business_id))


def _upsert(session: Session, model, business_id: str, values: dict) -> str:
    existing = _get_by_business_id(session, model, business_id)
    if existing is None:
        row = model(id=uuid.uuid4(), business_id=business_id, **values)
        session.add(row)
        session.flush()
        return "created"
    for key, value in values.items():
        setattr(existing, key, value)
    return "updated"


def _insert_if_absent(session: Session, model, business_id: str, values: dict) -> str:
    """Insert a row once. Existing rows are left unchanged.

    Audit events use this path. The table rejects UPDATE and DELETE.
    """

    existing = _get_by_business_id(session, model, business_id)
    if existing is not None:
        return "skipped"
    row = model(id=uuid.uuid4(), business_id=business_id, **values)
    session.add(row)
    session.flush()
    return "created"


def _address(payload: dict, prefix: str = "") -> dict:
    if prefix:
        return {
            f"{prefix}line1": payload["line1"],
            f"{prefix}line2": payload.get("line2"),
            f"{prefix}city": payload["city"],
            f"{prefix}state": payload["state"],
            f"{prefix}postal_code": payload["postal_code"],
            f"{prefix}country": payload["country"],
        }
    return {
        "line1": payload["line1"],
        "line2": payload.get("line2"),
        "city": payload["city"],
        "state": payload["state"],
        "postal_code": payload["postal_code"],
        "country": payload["country"],
    }


def _require(index: dict[str, object], key: str, label: str):
    value = index.get(key)
    if value is None:
        raise SeedError(f"missing {label} {key}")
    return value


def _link(index: dict[str, uuid.UUID], business_id: str | None, label: str):
    if not business_id:
        return None
    return _require(index, business_id, label)


def seed_valid_fixtures(
    session: Session, fixtures_dir: Path
) -> dict[str, dict[str, int]]:
    fixtures_dir = fixtures_dir.resolve()
    if fixtures_dir.name == QUALITY_DIR_NAME:
        raise SeedError("refusing to load quality-issue fixtures")

    counts: dict[str, dict[str, int]] = {}

    def tally(entity: str, action: str) -> None:
        bucket = counts.setdefault(entity, {"created": 0, "updated": 0, "skipped": 0})
        bucket[action] += 1

    customers = _load_records(fixtures_dir, "customers.json")
    customer_ids: dict[str, uuid.UUID] = {}
    for record in customers:
        action = _upsert(
            session,
            CustomerORM,
            record["id"],
            {
                "legal_name": record["legal_name"],
                "trade_name": record.get("trade_name"),
                "account_number": record["account_number"],
                "status": record["status"],
                "customer_type": record["customer_type"],
                **_address(record["billing_address"], "billing_"),
                "billing_email": record.get("billing_email"),
                "billing_phone": record.get("billing_phone"),
                "payment_terms": record["payment_terms"],
                "service_agreement": record["service_agreement"],
                "agreement_expires_on": parse_date(record.get("agreement_expires_on")),
                "notes": record.get("notes"),
                "created_at": parse_datetime(record["created_at"]),
                "updated_at": parse_datetime(record["updated_at"]),
            },
        )
        tally("customer", action)
        customer_ids[record["id"]] = _get_by_business_id(
            session, CustomerORM, record["id"]
        ).id

    contact_ids: dict[str, uuid.UUID] = {}
    for record in _load_records(fixtures_dir, "contacts.json"):
        action = _upsert(
            session,
            ContactORM,
            record["id"],
            {
                "customer_id": _require(
                    customer_ids, record["customer_id"], "customer"
                ),
                "first_name": record["first_name"],
                "last_name": record["last_name"],
                "title": record.get("title"),
                "email": record.get("email"),
                "phone": record.get("phone"),
                "contact_role": record["contact_role"],
                "is_primary": record["is_primary"],
                "status": record["status"],
                "created_at": parse_datetime(record["created_at"]),
                "updated_at": parse_datetime(record["updated_at"]),
            },
        )
        tally("contact", action)
        contact_ids[record["id"]] = _get_by_business_id(
            session, ContactORM, record["id"]
        ).id

    for record in customers:
        primary = record.get("primary_contact_id")
        customer = _get_by_business_id(session, CustomerORM, record["id"])
        customer.primary_contact_id = contact_ids.get(primary) if primary else None

    location_ids: dict[str, uuid.UUID] = {}
    for record in _load_records(fixtures_dir, "service_locations.json"):
        action = _upsert(
            session,
            ServiceLocationORM,
            record["id"],
            {
                "customer_id": _require(
                    customer_ids, record["customer_id"], "customer"
                ),
                "name": record["name"],
                **_address(record["address"]),
                "site_type": record["site_type"],
                "timezone": record["timezone"],
                "access_notes": record.get("access_notes"),
                "square_footage": record.get("square_footage"),
                "status": record["status"],
                "created_at": parse_datetime(record["created_at"]),
                "updated_at": parse_datetime(record["updated_at"]),
            },
        )
        tally("service_location", action)
        location_ids[record["id"]] = _get_by_business_id(
            session, ServiceLocationORM, record["id"]
        ).id

    role_ids: dict[str, uuid.UUID] = {}
    for record in _load_records(fixtures_dir, "roles.json"):
        action = _upsert(
            session,
            RoleORM,
            record["id"],
            {
                "name": record["name"],
                "department": record["department"],
                "is_approver": bool(record["is_approver"]),
                "description": record.get("description"),
                "created_at": parse_datetime(record["created_at"]),
                "updated_at": parse_datetime(record["updated_at"]),
            },
        )
        tally("role", action)
        role_ids[record["id"]] = _get_by_business_id(session, RoleORM, record["id"]).id

    team_records = _load_records(fixtures_dir, "teams.json")
    team_ids: dict[str, uuid.UUID] = {}
    for record in team_records:
        action = _upsert(
            session,
            TeamORM,
            record["id"],
            {
                "name": record["name"],
                "department": record["department"],
                "service_area": record.get("service_area"),
                "created_at": parse_datetime(record["created_at"]),
                "updated_at": parse_datetime(record["updated_at"]),
            },
        )
        tally("team", action)
        team_ids[record["id"]] = _get_by_business_id(session, TeamORM, record["id"]).id

    employee_ids: dict[str, uuid.UUID] = {}
    for record in _load_records(fixtures_dir, "employees.json"):
        action = _upsert(
            session,
            EmployeeORM,
            record["id"],
            {
                "employee_number": record["employee_number"],
                "first_name": record["first_name"],
                "last_name": record["last_name"],
                "email": record["email"],
                "phone": record.get("phone"),
                "role_id": _require(role_ids, record["role_id"], "role"),
                "team_id": _link(team_ids, record.get("team_id"), "team"),
                "department": record["department"],
                "job_title": record["job_title"],
                "status": record["status"],
                "hire_date": parse_date(record["hire_date"]),
                "certifications": list(record.get("certifications") or []),
                "created_at": parse_datetime(record["created_at"]),
                "updated_at": parse_datetime(record["updated_at"]),
            },
        )
        tally("employee", action)
        employee_ids[record["id"]] = _get_by_business_id(
            session, EmployeeORM, record["id"]
        ).id

    for record in team_records:
        team = _get_by_business_id(session, TeamORM, record["id"])
        team.lead_employee_id = _link(
            employee_ids, record.get("lead_employee_id"), "employee"
        )

    equipment_ids: dict[str, uuid.UUID] = {}
    for record in _load_records(fixtures_dir, "equipment.json"):
        action = _upsert(
            session,
            EquipmentORM,
            record["id"],
            {
                "customer_id": _require(
                    customer_ids, record["customer_id"], "customer"
                ),
                "service_location_id": _require(
                    location_ids, record["service_location_id"], "service location"
                ),
                "asset_tag": record["asset_tag"],
                "name": record["name"],
                "equipment_type": record["equipment_type"],
                "manufacturer": record.get("manufacturer"),
                "model": record.get("model"),
                "serial_number": record.get("serial_number"),
                "installed_on": parse_date(record.get("installed_on")),
                "warranty_expires_on": parse_date(record.get("warranty_expires_on")),
                "last_service_on": parse_date(record.get("last_service_on")),
                "next_maintenance_on": parse_date(record.get("next_maintenance_on")),
                "status": record["status"],
                "notes": record.get("notes"),
                "created_at": parse_datetime(record["created_at"]),
                "updated_at": parse_datetime(record["updated_at"]),
            },
        )
        tally("equipment", action)
        equipment_ids[record["id"]] = _get_by_business_id(
            session, EquipmentORM, record["id"]
        ).id

    work_order_ids: dict[str, uuid.UUID] = {}
    work_order_records = _load_records(fixtures_dir, "work_orders.json")
    for record in work_order_records:
        requested = record.get("requested_by_contact_id")
        action = _upsert(
            session,
            WorkOrderORM,
            record["id"],
            {
                "customer_id": _require(
                    customer_ids, record["customer_id"], "customer"
                ),
                "service_location_id": _require(
                    location_ids, record["service_location_id"], "service location"
                ),
                "status": record["status"],
                "priority": record["priority"],
                "work_type": record["work_type"],
                "summary": record["summary"],
                "description": record.get("description"),
                "requested_by_contact_id": contact_ids.get(requested)
                if requested
                else None,
                "opened_at": parse_datetime(record["opened_at"]),
                "scheduled_for": parse_datetime(record["scheduled_for"])
                if record.get("scheduled_for")
                else None,
                "completed_at": parse_datetime(record["completed_at"])
                if record.get("completed_at")
                else None,
                "completion_notes": record.get("completion_notes"),
                "invoice_id": record.get("invoice_id"),
                "cancelled_reason": record.get("cancelled_reason"),
                "reopen_reason": record.get("reopen_reason"),
                "created_at": parse_datetime(record["created_at"]),
                "updated_at": parse_datetime(record["updated_at"]),
            },
        )
        tally("work_order", action)
        work_order = _get_by_business_id(session, WorkOrderORM, record["id"])
        work_order_ids[record["id"]] = work_order.id
        work_order.assigned_employees = [
            _get_by_business_id(session, EmployeeORM, item)
            for item in record.get("assigned_employee_ids", [])
            if _require(employee_ids, item, "employee")
        ]
        work_order.equipment = [
            _get_by_business_id(session, EquipmentORM, item)
            for item in record.get("equipment_ids", [])
            if _require(equipment_ids, item, "equipment")
        ]

    for record in _load_records(fixtures_dir, "work_order_tasks.json"):
        assigned = record.get("assigned_employee_id")
        action = _upsert(
            session,
            WorkOrderTaskORM,
            record["id"],
            {
                "work_order_id": _require(
                    work_order_ids, record["work_order_id"], "work order"
                ),
                "sequence": record["sequence"],
                "description": record["description"],
                "status": record["status"],
                "assigned_employee_id": employee_ids.get(assigned)
                if assigned
                else None,
                "completed_at": parse_datetime(record["completed_at"])
                if record.get("completed_at")
                else None,
                "blocked_reason": record.get("blocked_reason"),
                "created_at": parse_datetime(record["created_at"]),
                "updated_at": parse_datetime(record["updated_at"]),
            },
        )
        tally("work_order_task", action)

    appointment_ids: dict[str, uuid.UUID] = {}
    appointments = _load_records(fixtures_dir, "appointments.json")
    for record in appointments:
        action = _upsert(
            session,
            AppointmentORM,
            record["id"],
            {
                "work_order_id": _require(
                    work_order_ids, record["work_order_id"], "work order"
                ),
                "service_location_id": _require(
                    location_ids, record["service_location_id"], "service location"
                ),
                "assigned_employee_id": _require(
                    employee_ids, record["assigned_employee_id"], "employee"
                ),
                "status": record["status"],
                "start_at": parse_datetime(record["start_at"]),
                "end_at": parse_datetime(record["end_at"]),
                "notes": record.get("notes"),
                "cancellation_reason": record.get("cancellation_reason"),
                "created_at": parse_datetime(record["created_at"]),
                "updated_at": parse_datetime(record["updated_at"]),
            },
        )
        tally("appointment", action)
        appointment_ids[record["id"]] = _get_by_business_id(
            session, AppointmentORM, record["id"]
        ).id

    for record in appointments:
        replaces = record.get("replaces_appointment_id")
        appointment = _get_by_business_id(session, AppointmentORM, record["id"])
        appointment.replaces_appointment_id = (
            appointment_ids.get(replaces) if replaces else None
        )

    ticket_ids: dict[str, uuid.UUID] = {}
    for record in _load_records(fixtures_dir, "support_tickets.json"):
        action = _upsert(
            session,
            SupportTicketORM,
            record["id"],
            {
                "customer_id": _require(
                    customer_ids, record["customer_id"], "customer"
                ),
                "contact_id": _link(contact_ids, record.get("contact_id"), "contact"),
                "service_location_id": _link(
                    location_ids,
                    record.get("service_location_id"),
                    "service location",
                ),
                "work_order_id": _link(
                    work_order_ids, record.get("work_order_id"), "work order"
                ),
                "status": record["status"],
                "priority": record["priority"],
                "channel": record["channel"],
                "subject": record["subject"],
                "assigned_employee_id": _link(
                    employee_ids, record.get("assigned_employee_id"), "employee"
                ),
                "opened_at": parse_datetime(record["opened_at"]),
                "resolved_at": parse_datetime(record["resolved_at"])
                if record.get("resolved_at")
                else None,
                "closed_at": parse_datetime(record["closed_at"])
                if record.get("closed_at")
                else None,
                "related_document_ids": list(record.get("related_document_ids") or []),
                "created_at": parse_datetime(record["created_at"]),
                "updated_at": parse_datetime(record["updated_at"]),
            },
        )
        tally("support_ticket", action)
        ticket_ids[record["id"]] = _get_by_business_id(
            session, SupportTicketORM, record["id"]
        ).id

    for record in work_order_records:
        work_order = _get_by_business_id(session, WorkOrderORM, record["id"])
        work_order.support_ticket_id = _link(
            ticket_ids, record.get("support_ticket_id"), "support ticket"
        )

    approval_ids: dict[str, uuid.UUID] = {}
    for record in _load_records(fixtures_dir, "approval_requests.json"):
        action = _upsert(
            session,
            ApprovalRequestORM,
            record["id"],
            {
                "action_type": record["action_type"],
                "status": record["status"],
                "requested_by_employee_id": _require(
                    employee_ids, record["requested_by_employee_id"], "employee"
                ),
                "reviewer_employee_id": _link(
                    employee_ids, record.get("reviewer_employee_id"), "employee"
                ),
                "subject_type": record["subject_type"],
                "subject_id": record["subject_id"],
                "rationale": record["rationale"],
                "decision_notes": record.get("decision_notes"),
                "requested_at": parse_datetime(record["requested_at"]),
                "decided_at": parse_datetime(record["decided_at"])
                if record.get("decided_at")
                else None,
                "executed_at": parse_datetime(record["executed_at"])
                if record.get("executed_at")
                else None,
                "created_at": parse_datetime(record["created_at"]),
                "updated_at": parse_datetime(record["updated_at"]),
            },
        )
        tally("approval_request", action)
        approval = _get_by_business_id(session, ApprovalRequestORM, record["id"])
        approval_ids[record["id"]] = approval.id
        approval.decision_history.clear()
        session.flush()
        for position, entry in enumerate(record.get("decision_history") or []):
            approval.decision_history.append(
                ApprovalDecisionORM(
                    id=uuid.uuid4(),
                    approval_request_id=approval.id,
                    position=position,
                    at=parse_datetime(entry["at"]),
                    actor_employee_id=_require(
                        employee_ids, entry["actor_employee_id"], "employee"
                    ),
                    from_status=entry["from_status"],
                    to_status=entry["to_status"],
                    note=entry.get("note"),
                )
            )

    for record in _load_records(fixtures_dir, "messages.json"):
        action = _upsert(
            session,
            MessageORM,
            record["id"],
            {
                "support_ticket_id": _require(
                    ticket_ids, record["support_ticket_id"], "support ticket"
                ),
                "direction": record["direction"],
                "channel": record["channel"],
                "body": record["body"],
                "status": record["status"],
                "author_employee_id": _link(
                    employee_ids, record.get("author_employee_id"), "employee"
                ),
                "author_contact_id": _link(
                    contact_ids, record.get("author_contact_id"), "contact"
                ),
                "requires_approval": bool(record.get("requires_approval", False)),
                "approval_request_id": _link(
                    approval_ids, record.get("approval_request_id"), "approval request"
                ),
                "sent_at": parse_datetime(record["sent_at"]),
                "created_at": parse_datetime(record["created_at"]),
                "updated_at": parse_datetime(record["updated_at"]),
            },
        )
        tally("message", action)

    for record in _load_records(fixtures_dir, "interactions.json"):
        action = _upsert(
            session,
            InteractionORM,
            record["id"],
            {
                "customer_id": _require(
                    customer_ids, record["customer_id"], "customer"
                ),
                "contact_id": _link(contact_ids, record.get("contact_id"), "contact"),
                "support_ticket_id": _link(
                    ticket_ids, record.get("support_ticket_id"), "support ticket"
                ),
                "work_order_id": _link(
                    work_order_ids, record.get("work_order_id"), "work order"
                ),
                "channel": record["channel"],
                "occurred_at": parse_datetime(record["occurred_at"]),
                "summary": record["summary"],
                "employee_id": _require(
                    employee_ids, record["employee_id"], "employee"
                ),
                "outcome": record["outcome"],
                "created_at": parse_datetime(record["created_at"]),
                "updated_at": parse_datetime(record["updated_at"]),
            },
        )
        tally("interaction", action)

    for record in _load_records(fixtures_dir, "audit_events.json"):
        action = _insert_if_absent(
            session,
            AuditEventORM,
            record["id"],
            {
                "occurred_at": parse_datetime(record["occurred_at"]),
                "actor_type": record["actor_type"],
                "actor_employee_id": _link(
                    employee_ids, record.get("actor_employee_id"), "employee"
                ),
                "action": record["action"],
                "subject_type": record["subject_type"],
                "subject_id": record["subject_id"],
                "outcome": record["outcome"],
                "approval_request_id": _link(
                    approval_ids,
                    record.get("approval_request_id"),
                    "approval request",
                ),
                "details": record.get("details"),
            },
        )
        tally("audit_event", action)

    session.commit()
    return counts
