"""Read use cases for customers and service locations."""

from __future__ import annotations

from wasatch_api.customers.domain.entities import Customer, ServiceLocationDetail
from wasatch_api.customers.infrastructure.repository import CustomerRepository
from wasatch_api.shared.errors import NotFoundError
from wasatch_api.shared.pagination import (
    PageRequest,
    parse_page,
    validate_customer_status,
)


class CustomerQueries:
    def __init__(self, repository: CustomerRepository) -> None:
        self.repository = repository

    def list_customers(
        self,
        *,
        page: int | None,
        page_size: int | None,
        query: str | None,
        status: str | None,
    ) -> tuple[list[Customer], int, PageRequest]:
        request = parse_page(page, page_size)
        customers, total = self.repository.list_customers(
            request,
            query=query.strip() if query else None,
            status=validate_customer_status(status),
        )
        return customers, total, request

    def get_customer(self, customer_id: str) -> Customer:
        customer = self.repository.get_by_business_id(customer_id)
        if customer is None:
            raise NotFoundError(f"customer {customer_id} was not found")
        return customer

    def get_location(self, location_id: str) -> ServiceLocationDetail:
        detail = self.repository.get_location(location_id)
        if detail is None:
            raise NotFoundError(f"service location {location_id} was not found")
        return detail
