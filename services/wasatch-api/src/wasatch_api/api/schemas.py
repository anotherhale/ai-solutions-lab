"""Pydantic HTTP models. These are not the JSON Schema contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from wasatch_api.customer_service.domain.entities import (
    Interaction,
    Message,
    SupportTicket,
)
from wasatch_api.customer_service.domain.retrieval import (
    HistoryPassage,
    ProcedurePage,
    RetrievalResult,
)
from wasatch_api.customers.domain.entities import (
    Address,
    Contact,
    Customer,
    CustomerSummary,
    ServiceLocation,
    ServiceLocationDetail,
)
from wasatch_api.governance.domain.entities import (
    ApprovalDecision,
    ApprovalRequest,
    AuditEvent,
)
from wasatch_api.shared.time import dump_date, dump_datetime
from wasatch_api.work_orders.domain.entities import (
    Appointment,
    EmployeeSummary,
    EquipmentSummary,
    WorkOrder,
    WorkOrderTask,
)


class AddressOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line1: str
    line2: str | None = None
    city: str
    state: str
    postal_code: str
    country: str

    @classmethod
    def from_domain(cls, address: Address) -> AddressOut:
        return cls(
            line1=address.line1,
            line2=address.line2,
            city=address.city,
            state=address.state,
            postal_code=address.postal_code,
            country=address.country,
        )


class ContactOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    customer_id: str
    first_name: str
    last_name: str
    title: str | None = None
    email: str | None = None
    phone: str | None = None
    contact_role: str
    is_primary: bool
    status: str

    @classmethod
    def from_domain(cls, contact: Contact) -> ContactOut:
        return cls(**contact.__dict__)


class ServiceLocationOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    customer_id: str
    name: str
    address: AddressOut
    site_type: str
    timezone: str
    access_notes: str | None = None
    square_footage: int | None = None
    status: str

    @classmethod
    def from_domain(cls, location: ServiceLocation) -> ServiceLocationOut:
        return cls(
            id=location.id,
            customer_id=location.customer_id,
            name=location.name,
            address=AddressOut.from_domain(location.address),
            site_type=location.site_type,
            timezone=location.timezone,
            access_notes=location.access_notes,
            square_footage=location.square_footage,
            status=location.status,
        )


class CustomerSummaryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    legal_name: str
    trade_name: str | None = None
    account_number: str
    status: str
    customer_type: str

    @classmethod
    def from_domain(cls, customer: CustomerSummary) -> CustomerSummaryOut:
        return cls(**customer.__dict__)


class CustomerListItemOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    legal_name: str
    trade_name: str | None = None
    account_number: str
    status: str
    customer_type: str
    payment_terms: str
    service_agreement: str

    @classmethod
    def from_domain(cls, customer: Customer) -> CustomerListItemOut:
        return cls(
            id=customer.id,
            legal_name=customer.legal_name,
            trade_name=customer.trade_name,
            account_number=customer.account_number,
            status=customer.status,
            customer_type=customer.customer_type,
            payment_terms=customer.payment_terms,
            service_agreement=customer.service_agreement,
        )


class CustomerDetailOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    legal_name: str
    trade_name: str | None = None
    account_number: str
    status: str
    customer_type: str
    billing_address: AddressOut
    billing_email: str | None = None
    billing_phone: str | None = None
    payment_terms: str
    service_agreement: str
    agreement_expires_on: str | None = None
    primary_contact_id: str | None = None
    notes: str | None = None
    created_at: str
    updated_at: str
    contacts: list[ContactOut]
    service_locations: list[ServiceLocationOut]

    @classmethod
    def from_domain(cls, customer: Customer) -> CustomerDetailOut:
        return cls(
            id=customer.id,
            legal_name=customer.legal_name,
            trade_name=customer.trade_name,
            account_number=customer.account_number,
            status=customer.status,
            customer_type=customer.customer_type,
            billing_address=AddressOut.from_domain(customer.billing_address),
            billing_email=customer.billing_email,
            billing_phone=customer.billing_phone,
            payment_terms=customer.payment_terms,
            service_agreement=customer.service_agreement,
            agreement_expires_on=dump_date(customer.agreement_expires_on),
            primary_contact_id=customer.primary_contact_id,
            notes=customer.notes,
            created_at=dump_datetime(customer.created_at),
            updated_at=dump_datetime(customer.updated_at),
            contacts=[ContactOut.from_domain(item) for item in customer.contacts],
            service_locations=[
                ServiceLocationOut.from_domain(item)
                for item in customer.service_locations
            ],
        )


class ServiceLocationDetailOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    customer_id: str
    name: str
    address: AddressOut
    site_type: str
    timezone: str
    access_notes: str | None = None
    square_footage: int | None = None
    status: str
    customer: CustomerSummaryOut

    @classmethod
    def from_domain(cls, detail: ServiceLocationDetail) -> ServiceLocationDetailOut:
        location = detail.location
        return cls(
            id=location.id,
            customer_id=location.customer_id,
            name=location.name,
            address=AddressOut.from_domain(location.address),
            site_type=location.site_type,
            timezone=location.timezone,
            access_notes=location.access_notes,
            square_footage=location.square_footage,
            status=location.status,
            customer=CustomerSummaryOut.from_domain(detail.customer),
        )


class EmployeeSummaryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    first_name: str
    last_name: str
    job_title: str
    department: str
    status: str

    @classmethod
    def from_domain(cls, employee: EmployeeSummary) -> EmployeeSummaryOut:
        return cls(**employee.__dict__)


class EquipmentSummaryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    asset_tag: str
    name: str
    equipment_type: str
    status: str

    @classmethod
    def from_domain(cls, equipment: EquipmentSummary) -> EquipmentSummaryOut:
        return cls(**equipment.__dict__)


class WorkOrderTaskOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    sequence: int
    description: str
    status: str
    assigned_employee_id: str | None = None
    completed_at: str | None = None
    blocked_reason: str | None = None

    @classmethod
    def from_domain(cls, task: WorkOrderTask) -> WorkOrderTaskOut:
        return cls(
            id=task.id,
            sequence=task.sequence,
            description=task.description,
            status=task.status,
            assigned_employee_id=task.assigned_employee_id,
            completed_at=dump_datetime(task.completed_at)
            if task.completed_at
            else None,
            blocked_reason=task.blocked_reason,
        )


class AppointmentOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    service_location_id: str
    assigned_employee_id: str
    status: str
    start_at: str
    end_at: str
    notes: str | None = None
    cancellation_reason: str | None = None
    replaces_appointment_id: str | None = None

    @classmethod
    def from_domain(cls, appointment: Appointment) -> AppointmentOut:
        return cls(
            id=appointment.id,
            service_location_id=appointment.service_location_id,
            assigned_employee_id=appointment.assigned_employee_id,
            status=appointment.status,
            start_at=dump_datetime(appointment.start_at),
            end_at=dump_datetime(appointment.end_at),
            notes=appointment.notes,
            cancellation_reason=appointment.cancellation_reason,
            replaces_appointment_id=appointment.replaces_appointment_id,
        )


class WorkOrderListItemOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    customer_id: str
    service_location_id: str
    status: str
    priority: str
    work_type: str
    summary: str
    opened_at: str
    assigned_employee_ids: list[str] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, work_order: WorkOrder) -> WorkOrderListItemOut:
        return cls(
            id=work_order.id,
            customer_id=work_order.customer_id,
            service_location_id=work_order.service_location_id,
            status=work_order.status,
            priority=work_order.priority,
            work_type=work_order.work_type,
            summary=work_order.summary,
            opened_at=dump_datetime(work_order.opened_at),
            assigned_employee_ids=[item.id for item in work_order.assigned_employees],
        )


class WorkOrderDetailOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    customer_id: str
    service_location_id: str
    status: str
    priority: str
    work_type: str
    summary: str
    description: str | None = None
    requested_by_contact_id: str | None = None
    support_ticket_id: str | None = None
    invoice_id: str | None = None
    opened_at: str
    scheduled_for: str | None = None
    completed_at: str | None = None
    completion_notes: str | None = None
    cancelled_reason: str | None = None
    reopen_reason: str | None = None
    created_at: str
    updated_at: str
    assigned_employees: list[EmployeeSummaryOut]
    equipment: list[EquipmentSummaryOut]
    tasks: list[WorkOrderTaskOut]
    appointments: list[AppointmentOut]

    @classmethod
    def from_domain(cls, work_order: WorkOrder) -> WorkOrderDetailOut:
        return cls(
            id=work_order.id,
            customer_id=work_order.customer_id,
            service_location_id=work_order.service_location_id,
            status=work_order.status,
            priority=work_order.priority,
            work_type=work_order.work_type,
            summary=work_order.summary,
            description=work_order.description,
            requested_by_contact_id=work_order.requested_by_contact_id,
            support_ticket_id=work_order.support_ticket_id,
            invoice_id=work_order.invoice_id,
            opened_at=dump_datetime(work_order.opened_at),
            scheduled_for=dump_datetime(work_order.scheduled_for)
            if work_order.scheduled_for
            else None,
            completed_at=dump_datetime(work_order.completed_at)
            if work_order.completed_at
            else None,
            completion_notes=work_order.completion_notes,
            cancelled_reason=work_order.cancelled_reason,
            reopen_reason=work_order.reopen_reason,
            created_at=dump_datetime(work_order.created_at),
            updated_at=dump_datetime(work_order.updated_at),
            assigned_employees=[
                EmployeeSummaryOut.from_domain(item)
                for item in work_order.assigned_employees
            ],
            equipment=[
                EquipmentSummaryOut.from_domain(item) for item in work_order.equipment
            ],
            tasks=[WorkOrderTaskOut.from_domain(item) for item in work_order.tasks],
            appointments=[
                AppointmentOut.from_domain(item) for item in work_order.appointments
            ],
        )


class ApprovalDecisionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    at: str
    actor_employee_id: str
    from_status: str
    to_status: str
    note: str | None = None

    @classmethod
    def from_domain(cls, decision: ApprovalDecision) -> ApprovalDecisionOut:
        return cls(
            at=dump_datetime(decision.at),
            actor_employee_id=decision.actor_employee_id,
            from_status=decision.from_status,
            to_status=decision.to_status,
            note=decision.note,
        )


class ApprovalRequestOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    action_type: str
    status: str
    requested_by_employee_id: str
    subject_type: str
    subject_id: str
    rationale: str
    requested_at: str
    created_at: str
    updated_at: str
    decision_history: list[ApprovalDecisionOut] = Field(default_factory=list)
    reviewer_employee_id: str | None = None
    decision_notes: str | None = None
    decided_at: str | None = None
    executed_at: str | None = None

    @classmethod
    def from_domain(cls, approval: ApprovalRequest) -> ApprovalRequestOut:
        return cls(
            id=approval.id,
            action_type=approval.action_type,
            status=approval.status,
            requested_by_employee_id=approval.requested_by_employee_id,
            reviewer_employee_id=approval.reviewer_employee_id,
            subject_type=approval.subject_type,
            subject_id=approval.subject_id,
            rationale=approval.rationale,
            decision_notes=approval.decision_notes,
            requested_at=dump_datetime(approval.requested_at),
            decided_at=dump_datetime(approval.decided_at)
            if approval.decided_at
            else None,
            executed_at=(
                dump_datetime(approval.executed_at) if approval.executed_at else None
            ),
            decision_history=[
                ApprovalDecisionOut.from_domain(item)
                for item in approval.decision_history
            ],
            created_at=dump_datetime(approval.created_at),
            updated_at=dump_datetime(approval.updated_at),
        )


class AuditEventOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    occurred_at: str
    actor_type: str
    action: str
    subject_type: str
    subject_id: str
    outcome: str
    actor_employee_id: str | None = None
    approval_request_id: str | None = None
    details: dict | None = None

    @classmethod
    def from_domain(cls, event: AuditEvent) -> AuditEventOut:
        return cls(
            id=event.id,
            occurred_at=dump_datetime(event.occurred_at),
            actor_type=event.actor_type,
            actor_employee_id=event.actor_employee_id,
            action=event.action,
            subject_type=event.subject_type,
            subject_id=event.subject_id,
            outcome=event.outcome,
            approval_request_id=event.approval_request_id,
            details=event.details,
        )


class MessageOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    support_ticket_id: str
    direction: str
    channel: str
    body: str
    status: str
    sent_at: str
    created_at: str
    updated_at: str
    author_employee_id: str | None = None
    author_contact_id: str | None = None
    requires_approval: bool = False
    approval_request_id: str | None = None
    approval_request: ApprovalRequestOut | None = None

    @classmethod
    def from_domain(cls, message: Message) -> MessageOut:
        return cls(
            id=message.id,
            support_ticket_id=message.support_ticket_id,
            direction=message.direction,
            channel=message.channel,
            body=message.body,
            status=message.status,
            sent_at=dump_datetime(message.sent_at),
            created_at=dump_datetime(message.created_at),
            updated_at=dump_datetime(message.updated_at),
            author_employee_id=message.author_employee_id,
            author_contact_id=message.author_contact_id,
            requires_approval=message.requires_approval,
            approval_request_id=message.approval_request_id,
            approval_request=(
                ApprovalRequestOut.from_domain(message.approval_request)
                if message.approval_request
                else None
            ),
        )


class SupportTicketListItemOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    customer_id: str
    status: str
    priority: str
    channel: str
    subject: str
    opened_at: str
    service_location_id: str | None = None
    assigned_employee_id: str | None = None

    @classmethod
    def from_domain(cls, ticket: SupportTicket) -> SupportTicketListItemOut:
        return cls(
            id=ticket.id,
            customer_id=ticket.customer_id,
            status=ticket.status,
            priority=ticket.priority,
            channel=ticket.channel,
            subject=ticket.subject,
            opened_at=dump_datetime(ticket.opened_at),
            service_location_id=ticket.service_location_id,
            assigned_employee_id=ticket.assigned_employee_id,
        )


class SupportTicketDetailOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    customer_id: str
    status: str
    priority: str
    channel: str
    subject: str
    opened_at: str
    created_at: str
    updated_at: str
    contact_id: str | None = None
    service_location_id: str | None = None
    work_order_id: str | None = None
    assigned_employee_id: str | None = None
    resolved_at: str | None = None
    closed_at: str | None = None
    related_document_ids: list[str] = Field(default_factory=list)
    messages: list[MessageOut] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, ticket: SupportTicket) -> SupportTicketDetailOut:
        return cls(
            id=ticket.id,
            customer_id=ticket.customer_id,
            status=ticket.status,
            priority=ticket.priority,
            channel=ticket.channel,
            subject=ticket.subject,
            opened_at=dump_datetime(ticket.opened_at),
            created_at=dump_datetime(ticket.created_at),
            updated_at=dump_datetime(ticket.updated_at),
            contact_id=ticket.contact_id,
            service_location_id=ticket.service_location_id,
            work_order_id=ticket.work_order_id,
            assigned_employee_id=ticket.assigned_employee_id,
            resolved_at=dump_datetime(ticket.resolved_at)
            if ticket.resolved_at
            else None,
            closed_at=dump_datetime(ticket.closed_at) if ticket.closed_at else None,
            related_document_ids=list(ticket.related_document_ids),
            messages=[MessageOut.from_domain(item) for item in ticket.messages],
        )


class InteractionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    customer_id: str
    channel: str
    occurred_at: str
    summary: str
    employee_id: str
    outcome: str
    created_at: str
    updated_at: str
    contact_id: str | None = None
    support_ticket_id: str | None = None
    work_order_id: str | None = None

    @classmethod
    def from_domain(cls, interaction: Interaction) -> InteractionOut:
        return cls(
            id=interaction.id,
            customer_id=interaction.customer_id,
            channel=interaction.channel,
            occurred_at=dump_datetime(interaction.occurred_at),
            summary=interaction.summary,
            employee_id=interaction.employee_id,
            outcome=interaction.outcome,
            created_at=dump_datetime(interaction.created_at),
            updated_at=dump_datetime(interaction.updated_at),
            contact_id=interaction.contact_id,
            support_ticket_id=interaction.support_ticket_id,
            work_order_id=interaction.work_order_id,
        )


class HistoryPassageOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    source_id: str
    text: str

    @classmethod
    def from_domain(cls, passage: HistoryPassage) -> HistoryPassageOut:
        return cls(
            source=passage.source,
            source_id=passage.source_id,
            text=passage.text,
        )


class ProcedurePageOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    path: str
    text: str
    synthetic: Literal[True]

    @classmethod
    def from_domain(cls, page: ProcedurePage) -> ProcedurePageOut:
        return cls(
            id=page.id,
            title=page.title,
            path=page.path,
            text=page.text,
            synthetic=page.synthetic,
        )


class TicketRetrievalOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    support_ticket_id: str
    customer_id: str
    history: list[HistoryPassageOut]
    procedures: list[ProcedurePageOut]

    @classmethod
    def from_domain(cls, result: RetrievalResult) -> TicketRetrievalOut:
        return cls(
            support_ticket_id=result.support_ticket_id,
            customer_id=result.customer_id,
            history=[HistoryPassageOut.from_domain(item) for item in result.history],
            procedures=[
                ProcedurePageOut.from_domain(item) for item in result.procedures
            ],
        )


class PageOut[T](BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[T]
    page: int
    page_size: int
    total: int
