"""Read-only work-order routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from wasatch_api.api.dependencies import db_session, work_order_queries
from wasatch_api.api.schemas import PageOut, WorkOrderDetailOut, WorkOrderListItemOut
from wasatch_api.work_orders.application.queries import WorkOrderQueries

router = APIRouter(prefix="/api/v1", tags=["work-orders"])

SessionDep = Annotated[Session, Depends(db_session)]


def queries(session: SessionDep) -> WorkOrderQueries:
    return work_order_queries(session)


QueriesDep = Annotated[WorkOrderQueries, Depends(queries)]


@router.get("/work-orders", response_model=PageOut[WorkOrderListItemOut])
def list_work_orders(
    service: QueriesDep,
    customer_id: str | None = None,
    status: str | None = None,
    assigned_employee_id: str | None = None,
    service_location_id: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=100),
) -> PageOut[WorkOrderListItemOut]:
    items, total, request = service.list_work_orders(
        page=page,
        page_size=page_size,
        customer_id=customer_id,
        status=status,
        assigned_employee_id=assigned_employee_id,
        service_location_id=service_location_id,
    )
    return PageOut(
        items=[WorkOrderListItemOut.from_domain(item) for item in items],
        page=request.page,
        page_size=request.page_size,
        total=total,
    )


@router.get("/work-orders/{work_order_id}", response_model=WorkOrderDetailOut)
def get_work_order(work_order_id: str, service: QueriesDep) -> WorkOrderDetailOut:
    return WorkOrderDetailOut.from_domain(service.get_work_order(work_order_id))
