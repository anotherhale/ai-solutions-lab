"""PostgreSQL adapter for work-order queries."""

from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from wasatch_api.shared.database.models import (
    AppointmentORM,
    EmployeeORM,
    WorkOrderORM,
    WorkOrderTaskORM,
    work_order_assignments,
)
from wasatch_api.shared.pagination import PageRequest
from wasatch_api.work_orders.domain.entities import WorkOrder
from wasatch_api.work_orders.infrastructure.mapping import work_order_from_orm


class WorkOrderRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_business_id(self, business_id: str) -> WorkOrder | None:
        stmt = (
            select(WorkOrderORM)
            .options(
                selectinload(WorkOrderORM.customer),
                selectinload(WorkOrderORM.service_location),
                selectinload(WorkOrderORM.requested_by),
                selectinload(WorkOrderORM.support_ticket),
                selectinload(WorkOrderORM.assigned_employees),
                selectinload(WorkOrderORM.equipment),
                selectinload(WorkOrderORM.tasks).selectinload(
                    WorkOrderTaskORM.assigned_employee
                ),
                selectinload(WorkOrderORM.appointments).selectinload(
                    AppointmentORM.service_location
                ),
                selectinload(WorkOrderORM.appointments).selectinload(
                    AppointmentORM.assigned_employee
                ),
                selectinload(WorkOrderORM.appointments).selectinload(
                    AppointmentORM.replaces_appointment
                ),
            )
            .where(WorkOrderORM.business_id == business_id)
        )
        row = self.session.scalar(stmt)
        if row is None:
            return None
        return work_order_from_orm(row, detail=True)

    def list_work_orders(
        self,
        page: PageRequest,
        *,
        customer_id: str | None = None,
        status: str | None = None,
        assigned_employee_id: str | None = None,
        service_location_id: str | None = None,
        invoice_id: str | None = None,
    ) -> tuple[list[WorkOrder], int]:
        stmt: Select[tuple[WorkOrderORM]] = select(WorkOrderORM).options(
            selectinload(WorkOrderORM.customer),
            selectinload(WorkOrderORM.service_location),
            selectinload(WorkOrderORM.requested_by),
            selectinload(WorkOrderORM.support_ticket),
            selectinload(WorkOrderORM.assigned_employees),
        )
        count_stmt = select(func.count()).select_from(WorkOrderORM)
        if customer_id:
            stmt = stmt.where(WorkOrderORM.customer.has(business_id=customer_id))
            count_stmt = count_stmt.where(
                WorkOrderORM.customer.has(business_id=customer_id)
            )
        if status:
            stmt = stmt.where(WorkOrderORM.status == status)
            count_stmt = count_stmt.where(WorkOrderORM.status == status)
        if service_location_id:
            stmt = stmt.where(
                WorkOrderORM.service_location.has(business_id=service_location_id)
            )
            count_stmt = count_stmt.where(
                WorkOrderORM.service_location.has(business_id=service_location_id)
            )
        if assigned_employee_id:
            assignment_filter = WorkOrderORM.id.in_(
                select(work_order_assignments.c.work_order_id).where(
                    work_order_assignments.c.employee_id.in_(
                        select(EmployeeORM.id).where(
                            EmployeeORM.business_id == assigned_employee_id
                        )
                    )
                )
            )
            stmt = stmt.where(assignment_filter)
            count_stmt = count_stmt.where(assignment_filter)
        if invoice_id:
            stmt = stmt.where(WorkOrderORM.invoice_id == invoice_id)
            count_stmt = count_stmt.where(WorkOrderORM.invoice_id == invoice_id)
        total = int(self.session.scalar(count_stmt) or 0)
        rows = self.session.scalars(
            stmt.order_by(WorkOrderORM.business_id)
            .offset(page.offset)
            .limit(page.page_size)
        ).all()
        return [work_order_from_orm(row, detail=False) for row in rows], total
