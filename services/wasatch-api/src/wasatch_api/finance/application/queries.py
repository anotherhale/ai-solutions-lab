"""Read use cases for invoices."""

from __future__ import annotations

from wasatch_api.finance.domain.entities import Invoice
from wasatch_api.finance.infrastructure.repository import InvoiceRepository
from wasatch_api.shared.errors import NotFoundError
from wasatch_api.shared.pagination import (
    PageRequest,
    parse_page,
    validate_invoice_status,
)


class InvoiceQueries:
    def __init__(self, repository: InvoiceRepository) -> None:
        self.repository = repository

    def list_invoices(
        self,
        *,
        page: int | None,
        page_size: int | None,
        customer_id: str | None,
        status: str | None,
    ) -> tuple[list[Invoice], int, PageRequest]:
        request = parse_page(page, page_size)
        items, total = self.repository.list_invoices(
            request,
            customer_id=customer_id,
            status=validate_invoice_status(status),
        )
        return items, total, request

    def get_invoice(self, invoice_id: str) -> Invoice:
        invoice = self.repository.get_by_business_id(invoice_id)
        if invoice is None:
            raise NotFoundError(f"invoice {invoice_id} was not found")
        return invoice
