"""Customer-service domain records used by application services."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Message:
    id: str
    support_ticket_id: str
    direction: str
    channel: str
    body: str
    status: str
    sent_at: datetime
    created_at: datetime
    updated_at: datetime
    author_employee_id: str | None = None
    author_contact_id: str | None = None
    requires_approval: bool = False
    approval_request_id: str | None = None


@dataclass
class SupportTicket:
    id: str
    customer_id: str
    status: str
    priority: str
    channel: str
    subject: str
    opened_at: datetime
    created_at: datetime
    updated_at: datetime
    contact_id: str | None = None
    service_location_id: str | None = None
    work_order_id: str | None = None
    assigned_employee_id: str | None = None
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    related_document_ids: list[str] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)


@dataclass(frozen=True)
class Interaction:
    id: str
    customer_id: str
    channel: str
    occurred_at: datetime
    summary: str
    employee_id: str
    outcome: str
    created_at: datetime
    updated_at: datetime
    contact_id: str | None = None
    support_ticket_id: str | None = None
    work_order_id: str | None = None
