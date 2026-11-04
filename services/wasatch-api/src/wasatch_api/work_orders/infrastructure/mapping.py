"""ORM to domain mapping for work orders."""

from __future__ import annotations

from wasatch_api.shared.database.models import (
    AppointmentORM,
    EmployeeORM,
    EquipmentORM,
    WorkOrderORM,
    WorkOrderTaskORM,
)
from wasatch_api.work_orders.domain.entities import (
    Appointment,
    EmployeeSummary,
    EquipmentSummary,
    WorkOrder,
    WorkOrderTask,
)


def employee_from_orm(row: EmployeeORM) -> EmployeeSummary:
    return EmployeeSummary(
        id=row.business_id,
        first_name=row.first_name,
        last_name=row.last_name,
        job_title=row.job_title,
        department=row.department,
        status=row.status,
    )


def equipment_from_orm(row: EquipmentORM) -> EquipmentSummary:
    return EquipmentSummary(
        id=row.business_id,
        asset_tag=row.asset_tag,
        name=row.name,
        equipment_type=row.equipment_type,
        status=row.status,
    )


def task_from_orm(row: WorkOrderTaskORM) -> WorkOrderTask:
    assigned = row.assigned_employee.business_id if row.assigned_employee else None
    return WorkOrderTask(
        id=row.business_id,
        sequence=row.sequence,
        description=row.description,
        status=row.status,
        assigned_employee_id=assigned,
        completed_at=row.completed_at,
        blocked_reason=row.blocked_reason,
    )


def appointment_from_orm(row: AppointmentORM) -> Appointment:
    replaces = (
        row.replaces_appointment.business_id if row.replaces_appointment else None
    )
    return Appointment(
        id=row.business_id,
        service_location_id=row.service_location.business_id,
        assigned_employee_id=row.assigned_employee.business_id,
        status=row.status,
        start_at=row.start_at,
        end_at=row.end_at,
        notes=row.notes,
        cancellation_reason=row.cancellation_reason,
        replaces_appointment_id=replaces,
    )


def work_order_from_orm(row: WorkOrderORM, *, detail: bool) -> WorkOrder:
    requested = row.requested_by.business_id if row.requested_by else None
    work_order = WorkOrder(
        id=row.business_id,
        customer_id=row.customer.business_id,
        service_location_id=row.service_location.business_id,
        status=row.status,
        priority=row.priority,
        work_type=row.work_type,
        summary=row.summary,
        description=row.description,
        requested_by_contact_id=requested,
        support_ticket_id=row.support_ticket_id,
        invoice_id=row.invoice_id,
        opened_at=row.opened_at,
        scheduled_for=row.scheduled_for,
        completed_at=row.completed_at,
        completion_notes=row.completion_notes,
        cancelled_reason=row.cancelled_reason,
        reopen_reason=row.reopen_reason,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
    if detail:
        work_order.assigned_employees = [
            employee_from_orm(item) for item in row.assigned_employees
        ]
        work_order.equipment = [equipment_from_orm(item) for item in row.equipment]
        work_order.tasks = [task_from_orm(item) for item in row.tasks]
        work_order.appointments = [
            appointment_from_orm(item) for item in row.appointments
        ]
    else:
        work_order.assigned_employees = [
            employee_from_orm(item) for item in row.assigned_employees
        ]
    return work_order
