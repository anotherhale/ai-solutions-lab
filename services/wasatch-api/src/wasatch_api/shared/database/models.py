"""SQLAlchemy mappings for the first Wasatch vertical slice.

Cross-module foreign keys stay in one module so Alembic and repositories share
a single metadata graph. API and domain types remain separate.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wasatch_api.shared.database.base import Base

work_order_assignments = Table(
    "work_order_assignments",
    Base.metadata,
    Column(
        "work_order_id",
        Uuid,
        ForeignKey("work_orders.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "employee_id",
        Uuid,
        ForeignKey("employees.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

work_order_equipment = Table(
    "work_order_equipment",
    Base.metadata,
    Column(
        "work_order_id",
        Uuid,
        ForeignKey("work_orders.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "equipment_id",
        Uuid,
        ForeignKey("equipment.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class CustomerORM(Base):
    __tablename__ = "customers"
    __table_args__ = (Index("ix_customers_legal_name", "legal_name"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[str] = mapped_column(String(16), unique=True)
    legal_name: Mapped[str] = mapped_column(String(255))
    trade_name: Mapped[str | None] = mapped_column(String(255))
    account_number: Mapped[str] = mapped_column(String(16), unique=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    customer_type: Mapped[str] = mapped_column(String(32))
    billing_line1: Mapped[str] = mapped_column(String(255))
    billing_line2: Mapped[str | None] = mapped_column(String(255))
    billing_city: Mapped[str] = mapped_column(String(128))
    billing_state: Mapped[str] = mapped_column(String(8))
    billing_postal_code: Mapped[str] = mapped_column(String(16))
    billing_country: Mapped[str] = mapped_column(String(8))
    billing_email: Mapped[str | None] = mapped_column(String(255))
    billing_phone: Mapped[str | None] = mapped_column(String(32))
    payment_terms: Mapped[str] = mapped_column(String(32))
    service_agreement: Mapped[str] = mapped_column(String(32))
    agreement_expires_on: Mapped[date | None] = mapped_column(Date)
    primary_contact_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "contacts.id",
            use_alter=True,
            name="fk_customers_primary_contact",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    contacts: Mapped[list[ContactORM]] = relationship(
        back_populates="customer",
        foreign_keys="ContactORM.customer_id",
    )
    service_locations: Mapped[list[ServiceLocationORM]] = relationship(
        back_populates="customer"
    )


class ContactORM(Base):
    __tablename__ = "contacts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[str] = mapped_column(String(16), unique=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    first_name: Mapped[str] = mapped_column(String(128))
    last_name: Mapped[str] = mapped_column(String(128))
    title: Mapped[str | None] = mapped_column(String(128))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32))
    contact_role: Mapped[str] = mapped_column(String(32))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    customer: Mapped[CustomerORM] = relationship(
        back_populates="contacts", foreign_keys=[customer_id]
    )


class ServiceLocationORM(Base):
    __tablename__ = "service_locations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[str] = mapped_column(String(16), unique=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    line1: Mapped[str] = mapped_column(String(255))
    line2: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(128))
    state: Mapped[str] = mapped_column(String(8))
    postal_code: Mapped[str] = mapped_column(String(16))
    country: Mapped[str] = mapped_column(String(8))
    site_type: Mapped[str] = mapped_column(String(32))
    timezone: Mapped[str] = mapped_column(String(64))
    access_notes: Mapped[str | None] = mapped_column(Text)
    square_footage: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    customer: Mapped[CustomerORM] = relationship(back_populates="service_locations")
    equipment: Mapped[list[EquipmentORM]] = relationship(back_populates="location")


class EmployeeORM(Base):
    __tablename__ = "employees"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[str] = mapped_column(String(16), unique=True)
    employee_number: Mapped[str] = mapped_column(String(16), unique=True)
    first_name: Mapped[str] = mapped_column(String(128))
    last_name: Mapped[str] = mapped_column(String(128))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    phone: Mapped[str | None] = mapped_column(String(32))
    role_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("roles.id", name="fk_employees_role", ondelete="RESTRICT"),
        index=True,
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("teams.id", name="fk_employees_team", ondelete="SET NULL"),
        index=True,
    )
    department: Mapped[str] = mapped_column(String(32), index=True)
    job_title: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), index=True)
    hire_date: Mapped[date] = mapped_column(Date)
    certifications: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    role: Mapped[RoleORM | None] = relationship(back_populates="employees")
    team: Mapped[TeamORM | None] = relationship(
        back_populates="members",
        foreign_keys=[team_id],
    )


class RoleORM(Base):
    """Job classification. is_approver lives here, not on the employee."""

    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    department: Mapped[str] = mapped_column(String(32), index=True)
    is_approver: Mapped[bool] = mapped_column(Boolean)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    employees: Mapped[list[EmployeeORM]] = relationship(back_populates="role")


class TeamORM(Base):
    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    department: Mapped[str] = mapped_column(String(32), index=True)
    service_area: Mapped[str | None] = mapped_column(String(255))
    lead_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "employees.id",
            use_alter=True,
            name="fk_teams_lead_employee",
            ondelete="SET NULL",
        ),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    lead: Mapped[EmployeeORM | None] = relationship(foreign_keys=[lead_employee_id])
    members: Mapped[list[EmployeeORM]] = relationship(
        back_populates="team",
        foreign_keys="EmployeeORM.team_id",
    )


class EquipmentORM(Base):
    __tablename__ = "equipment"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[str] = mapped_column(String(16), unique=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    service_location_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("service_locations.id", ondelete="CASCADE"), index=True
    )
    asset_tag: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    equipment_type: Mapped[str] = mapped_column(String(32))
    manufacturer: Mapped[str | None] = mapped_column(String(128))
    model: Mapped[str | None] = mapped_column(String(128))
    serial_number: Mapped[str | None] = mapped_column(String(128))
    installed_on: Mapped[date | None] = mapped_column(Date)
    warranty_expires_on: Mapped[date | None] = mapped_column(Date)
    last_service_on: Mapped[date | None] = mapped_column(Date)
    next_maintenance_on: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    location: Mapped[ServiceLocationORM] = relationship(back_populates="equipment")


class WorkOrderORM(Base):
    __tablename__ = "work_orders"
    __table_args__ = (Index("ix_work_orders_customer_status", "customer_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[str] = mapped_column(String(16), unique=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    service_location_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("service_locations.id", ondelete="RESTRICT"), index=True
    )
    support_ticket_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "support_tickets.id",
            use_alter=True,
            name="fk_work_orders_support_ticket",
            ondelete="SET NULL",
        ),
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), index=True)
    priority: Mapped[str] = mapped_column(String(32))
    work_type: Mapped[str] = mapped_column(String(32))
    summary: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    requested_by_contact_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("contacts.id", ondelete="SET NULL")
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completion_notes: Mapped[str | None] = mapped_column(Text)
    invoice_id: Mapped[str | None] = mapped_column(String(16))
    cancelled_reason: Mapped[str | None] = mapped_column(Text)
    reopen_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    customer: Mapped[CustomerORM] = relationship()
    service_location: Mapped[ServiceLocationORM] = relationship()
    requested_by: Mapped[ContactORM | None] = relationship()
    support_ticket: Mapped[SupportTicketORM | None] = relationship(
        "SupportTicketORM",
        foreign_keys=[support_ticket_id],
    )
    assigned_employees: Mapped[list[EmployeeORM]] = relationship(
        secondary=work_order_assignments
    )
    equipment: Mapped[list[EquipmentORM]] = relationship(secondary=work_order_equipment)
    tasks: Mapped[list[WorkOrderTaskORM]] = relationship(
        back_populates="work_order", order_by="WorkOrderTaskORM.sequence"
    )
    appointments: Mapped[list[AppointmentORM]] = relationship(
        back_populates="work_order"
    )


class WorkOrderTaskORM(Base):
    __tablename__ = "work_order_tasks"
    __table_args__ = (
        UniqueConstraint("work_order_id", "sequence", name="uq_work_order_task_seq"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[str] = mapped_column(String(16), unique=True)
    work_order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("work_orders.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32))
    assigned_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("employees.id", ondelete="SET NULL")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    blocked_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    work_order: Mapped[WorkOrderORM] = relationship(back_populates="tasks")
    assigned_employee: Mapped[EmployeeORM | None] = relationship()


class AppointmentORM(Base):
    __tablename__ = "appointments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[str] = mapped_column(String(16), unique=True)
    work_order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("work_orders.id", ondelete="CASCADE"), index=True
    )
    service_location_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("service_locations.id", ondelete="RESTRICT"), index=True
    )
    assigned_employee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("employees.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    replaces_appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("appointments.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    work_order: Mapped[WorkOrderORM] = relationship(back_populates="appointments")
    service_location: Mapped[ServiceLocationORM] = relationship()
    assigned_employee: Mapped[EmployeeORM] = relationship()
    replaces_appointment: Mapped[AppointmentORM | None] = relationship(
        remote_side="AppointmentORM.id",
        foreign_keys=[replaces_appointment_id],
    )


class SupportTicketORM(Base):
    __tablename__ = "support_tickets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[str] = mapped_column(String(16), unique=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("contacts.id", ondelete="SET NULL")
    )
    service_location_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("service_locations.id", ondelete="SET NULL"), index=True
    )
    work_order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("work_orders.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), index=True)
    priority: Mapped[str] = mapped_column(String(32))
    channel: Mapped[str] = mapped_column(String(32))
    subject: Mapped[str] = mapped_column(String(255))
    assigned_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("employees.id", ondelete="SET NULL"), index=True
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    related_document_ids: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    customer: Mapped[CustomerORM] = relationship()
    contact: Mapped[ContactORM | None] = relationship()
    service_location: Mapped[ServiceLocationORM | None] = relationship()
    work_order: Mapped[WorkOrderORM | None] = relationship(foreign_keys=[work_order_id])
    assigned_employee: Mapped[EmployeeORM | None] = relationship()
    messages: Mapped[list[MessageORM]] = relationship(
        back_populates="support_ticket",
        order_by="MessageORM.sent_at",
    )


class MessageORM(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[str] = mapped_column(String(16), unique=True)
    support_ticket_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("support_tickets.id", ondelete="CASCADE"), index=True
    )
    direction: Mapped[str] = mapped_column(String(32))
    channel: Mapped[str] = mapped_column(String(32))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), index=True)
    author_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("employees.id", ondelete="SET NULL")
    )
    author_contact_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("contacts.id", ondelete="SET NULL")
    )
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    approval_request_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "approval_requests.id",
            name="fk_messages_approval_request",
            ondelete="RESTRICT",
        ),
        index=True,
    )
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    support_ticket: Mapped[SupportTicketORM] = relationship(back_populates="messages")
    author_employee: Mapped[EmployeeORM | None] = relationship()
    author_contact: Mapped[ContactORM | None] = relationship()
    approval_request: Mapped[ApprovalRequestORM | None] = relationship(
        "ApprovalRequestORM",
        foreign_keys=[approval_request_id],
    )


class InteractionORM(Base):
    __tablename__ = "interactions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[str] = mapped_column(String(16), unique=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("contacts.id", ondelete="SET NULL")
    )
    support_ticket_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("support_tickets.id", ondelete="SET NULL"), index=True
    )
    work_order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("work_orders.id", ondelete="SET NULL"), index=True
    )
    channel: Mapped[str] = mapped_column(String(32))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    summary: Mapped[str] = mapped_column(Text)
    employee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("employees.id", ondelete="RESTRICT"), index=True
    )
    outcome: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    customer: Mapped[CustomerORM] = relationship()
    contact: Mapped[ContactORM | None] = relationship()
    support_ticket: Mapped[SupportTicketORM | None] = relationship()
    work_order: Mapped[WorkOrderORM | None] = relationship()
    employee: Mapped[EmployeeORM] = relationship()


class ApprovalRequestORM(Base):
    __tablename__ = "approval_requests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[str] = mapped_column(String(16), unique=True)
    action_type: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    requested_by_employee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("employees.id", ondelete="RESTRICT"), index=True
    )
    reviewer_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("employees.id", ondelete="SET NULL"), index=True
    )
    subject_type: Mapped[str] = mapped_column(String(32))
    subject_id: Mapped[str] = mapped_column(String(16))
    rationale: Mapped[str] = mapped_column(Text)
    decision_notes: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    requested_by: Mapped[EmployeeORM] = relationship(
        foreign_keys=[requested_by_employee_id]
    )
    reviewer: Mapped[EmployeeORM | None] = relationship(
        foreign_keys=[reviewer_employee_id]
    )
    decision_history: Mapped[list[ApprovalDecisionORM]] = relationship(
        back_populates="approval_request",
        cascade="all, delete-orphan",
        order_by="ApprovalDecisionORM.position",
    )


class ApprovalDecisionORM(Base):
    """One append-only transition on an approval request. Not an audit event."""

    __tablename__ = "approval_decision_history"
    __table_args__ = (
        UniqueConstraint(
            "approval_request_id",
            "position",
            name="uq_approval_decision_position",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    approval_request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("approval_requests.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor_employee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("employees.id", ondelete="RESTRICT")
    )
    from_status: Mapped[str] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32))
    note: Mapped[str | None] = mapped_column(Text)

    approval_request: Mapped[ApprovalRequestORM] = relationship(
        back_populates="decision_history"
    )
    actor: Mapped[EmployeeORM] = relationship()


class AuditEventORM(Base):
    """Insert-only audit row. Callers do not update or delete it."""

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[str] = mapped_column(String(16), unique=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor_type: Mapped[str] = mapped_column(String(32))
    actor_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("employees.id", ondelete="RESTRICT"), index=True
    )
    action: Mapped[str] = mapped_column(String(128))
    subject_type: Mapped[str] = mapped_column(String(32))
    subject_id: Mapped[str] = mapped_column(String(16))
    outcome: Mapped[str] = mapped_column(String(32), index=True)
    approval_request_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "approval_requests.id",
            name="fk_audit_events_approval_request",
            ondelete="RESTRICT",
        ),
        index=True,
    )
    details: Mapped[dict | None] = mapped_column(JSONB)

    actor_employee: Mapped[EmployeeORM | None] = relationship()
    approval_request: Mapped[ApprovalRequestORM | None] = relationship()
