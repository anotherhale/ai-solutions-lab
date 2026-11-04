"""Pydantic HTTP models. These are not the JSON Schema contracts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from wasatch_api.customers.domain.entities import (
    Address,
    Contact,
    Customer,
    CustomerSummary,
    ServiceLocation,
    ServiceLocationDetail,
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


class PageOut[T](BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[T]
    page: int
    page_size: int
    total: int
