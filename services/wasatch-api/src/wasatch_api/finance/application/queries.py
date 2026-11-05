"""Read use cases for invoices."""

from __future__ import annotations

from wasatch_api.finance.domain.entities import Invoice, InvoiceLine
from wasatch_api.finance.infrastructure.repository import InvoiceRepository
from wasatch_api.shared.errors import NotFoundError
from wasatch_api.shared.pagination import (
    PageRequest,
    parse_page,
    validate_invoice_line_type,
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

    def list_invoice_lines(
        self,
        invoice_id: str,
        *,
        page: int | None,
        page_size: int | None,
        line_type: str | None,
    ) -> tuple[list[InvoiceLine], int, PageRequest]:
        request = parse_page(page, page_size)
        result = self.repository.list_lines_for_invoice(
            invoice_id,
            request,
            line_type=validate_invoice_line_type(line_type),
        )
        if result is None:
            raise NotFoundError(f"invoice {invoice_id} was not found")
        items, total = result
        return items, total, request

    def get_invoice_line(self, invoice_line_id: str) -> InvoiceLine:
        line = self.repository.get_line_by_business_id(invoice_line_id)
        if line is None:
            raise NotFoundError(f"invoice line {invoice_line_id} was not found")
        return line
