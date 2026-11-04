"""Read-only customer and service-location routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from wasatch_api.api.dependencies import (
    customer_queries,
    db_session,
    require_laboratory_actor,
)
from wasatch_api.api.schemas import (
    CustomerDetailOut,
    CustomerListItemOut,
    PageOut,
    ServiceLocationDetailOut,
)
from wasatch_api.customers.application.queries import CustomerQueries

router = APIRouter(
    prefix="/api/v1",
    tags=["customers"],
    dependencies=[Depends(require_laboratory_actor)],
)

SessionDep = Annotated[Session, Depends(db_session)]


def queries(session: SessionDep) -> CustomerQueries:
    return customer_queries(session)


QueriesDep = Annotated[CustomerQueries, Depends(queries)]


@router.get("/customers", response_model=PageOut[CustomerListItemOut])
def list_customers(
    service: QueriesDep,
    q: str | None = Query(default=None, description="Search legal or trade name"),
    status: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=100),
) -> PageOut[CustomerListItemOut]:
    items, total, request = service.list_customers(
        page=page, page_size=page_size, query=q, status=status
    )
    return PageOut(
        items=[CustomerListItemOut.from_domain(item) for item in items],
        page=request.page,
        page_size=request.page_size,
        total=total,
    )


@router.get("/customers/{customer_id}", response_model=CustomerDetailOut)
def get_customer(customer_id: str, service: QueriesDep) -> CustomerDetailOut:
    return CustomerDetailOut.from_domain(service.get_customer(customer_id))


@router.get(
    "/service-locations/{location_id}",
    response_model=ServiceLocationDetailOut,
)
def get_service_location(
    location_id: str, service: QueriesDep
) -> ServiceLocationDetailOut:
    return ServiceLocationDetailOut.from_domain(service.get_location(location_id))
