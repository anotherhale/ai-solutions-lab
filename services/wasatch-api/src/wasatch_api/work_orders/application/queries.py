"""Read use cases for work orders."""

from __future__ import annotations

from wasatch_api.shared.errors import NotFoundError
from wasatch_api.shared.pagination import (
    PageRequest,
    parse_page,
    validate_work_order_status,
)
from wasatch_api.work_orders.domain.entities import WorkOrder
from wasatch_api.work_orders.infrastructure.repository import WorkOrderRepository


class WorkOrderQueries:
    def __init__(self, repository: WorkOrderRepository) -> None:
        self.repository = repository

    def list_work_orders(
        self,
        *,
        page: int | None,
        page_size: int | None,
        customer_id: str | None,
        status: str | None,
        assigned_employee_id: str | None,
        service_location_id: str | None,
    ) -> tuple[list[WorkOrder], int, PageRequest]:
        request = parse_page(page, page_size)
        items, total = self.repository.list_work_orders(
            request,
            customer_id=customer_id,
            status=validate_work_order_status(status),
            assigned_employee_id=assigned_employee_id,
            service_location_id=service_location_id,
        )
        return items, total, request

    def get_work_order(self, work_order_id: str) -> WorkOrder:
        work_order = self.repository.get_by_business_id(work_order_id)
        if work_order is None:
            raise NotFoundError(f"work order {work_order_id} was not found")
        return work_order
