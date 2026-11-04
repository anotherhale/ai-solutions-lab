"""Work-order domain records."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class EmployeeSummary:
    id: str
    first_name: str
    last_name: str
    job_title: str
    department: str
    status: str


@dataclass(frozen=True)
class EquipmentSummary:
    id: str
    asset_tag: str
    name: str
    equipment_type: str
    status: str


@dataclass(frozen=True)
class WorkOrderTask:
    id: str
    sequence: int
    description: str
    status: str
    assigned_employee_id: str | None = None
    completed_at: datetime | None = None
    blocked_reason: str | None = None


@dataclass(frozen=True)
class Appointment:
    id: str
    service_location_id: str
    assigned_employee_id: str
    status: str
    start_at: datetime
    end_at: datetime
    notes: str | None = None
    cancellation_reason: str | None = None
    replaces_appointment_id: str | None = None


@dataclass
class WorkOrder:
    id: str
    customer_id: str
    service_location_id: str
    status: str
    priority: str
    work_type: str
    summary: str
    opened_at: datetime
    created_at: datetime
    updated_at: datetime
    description: str | None = None
    requested_by_contact_id: str | None = None
    support_ticket_id: str | None = None
    invoice_id: str | None = None
    scheduled_for: datetime | None = None
    completed_at: datetime | None = None
    completion_notes: str | None = None
    cancelled_reason: str | None = None
    reopen_reason: str | None = None
    assigned_employees: list[EmployeeSummary] = field(default_factory=list)
    equipment: list[EquipmentSummary] = field(default_factory=list)
    tasks: list[WorkOrderTask] = field(default_factory=list)
    appointments: list[Appointment] = field(default_factory=list)
