"""Read use cases for synthetic invoices, lines, and payments."""

from __future__ import annotations

from wasatch_api.finance.domain.entities import Invoice, InvoiceLine, Payment
from wasatch_api.finance.infrastructure.repository import FinanceRepository
from wasatch_api.shared.errors import NotFoundError
from wasatch_api.shared.pagination import (
    PageRequest,
    parse_page,
    validate_invoice_line_type,
    validate_invoice_status,
    validate_payment_status,
)


class FinanceQueries:
    def __init__(self, repository: FinanceRepository) -> None:
        self.repository = repository

    def list_invoices(
        self,
        *,
        page: int | None,
        page_size: int | None,
        status: str | None,
        customer_id: str | None,
    ) -> tuple[list[Invoice], int, PageRequest]:
        request = parse_page(page, page_size)
        items, total = self.repository.list_invoices(
            request,
            status=validate_invoice_status(status),
            customer_id=customer_id,
        )
        return items, total, request

    def get_invoice(self, invoice_id: str) -> Invoice:
        invoice = self.repository.get_invoice(invoice_id)
        if invoice is None:
            raise NotFoundError(f"invoice {invoice_id} was not found")
        return invoice

    def list_invoice_lines(
        self,
        *,
        page: int | None,
        page_size: int | None,
        invoice_id: str | None,
        line_type: str | None,
    ) -> tuple[list[InvoiceLine], int, PageRequest]:
        request = parse_page(page, page_size)
        items, total = self.repository.list_invoice_lines(
            request,
            invoice_id=invoice_id,
            line_type=validate_invoice_line_type(line_type),
        )
        return items, total, request

    def get_invoice_line(self, line_id: str) -> InvoiceLine:
        line = self.repository.get_invoice_line(line_id)
        if line is None:
            raise NotFoundError(f"invoice line {line_id} was not found")
        return line

    def list_payments(
        self,
        *,
        page: int | None,
        page_size: int | None,
        status: str | None,
        invoice_id: str | None,
    ) -> tuple[list[Payment], int, PageRequest]:
        request = parse_page(page, page_size)
        items, total = self.repository.list_payments(
            request,
            status=validate_payment_status(status),
            invoice_id=invoice_id,
        )
        return items, total, request

    def get_payment(self, payment_id: str) -> Payment:
        payment = self.repository.get_payment(payment_id)
        if payment is None:
            raise NotFoundError(f"payment {payment_id} was not found")
        return payment
