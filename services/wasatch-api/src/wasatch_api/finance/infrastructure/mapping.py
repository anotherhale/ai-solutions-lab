"""ORM to domain mapping for invoices, lines, and payments."""

from __future__ import annotations

from decimal import Decimal

from wasatch_api.finance.domain.entities import Invoice, InvoiceLine, Money, Payment
from wasatch_api.shared.database.models import InvoiceLineORM, InvoiceORM, PaymentORM


def money_from_columns(amount: Decimal, currency: str) -> Money:
    return Money(amount=f"{amount:.2f}", currency=currency)


def invoice_line_from_orm(row: InvoiceLineORM) -> InvoiceLine:
    work_order = row.work_order.business_id if row.work_order else None
    return InvoiceLine(
        id=row.business_id,
        invoice_id=row.invoice.business_id,
        description=row.description,
        quantity=row.quantity,
        unit_price=money_from_columns(row.unit_price_amount, row.unit_price_currency),
        line_total=money_from_columns(row.line_total_amount, row.line_total_currency),
        line_type=row.line_type,
        created_at=row.created_at,
        updated_at=row.updated_at,
        work_order_id=work_order,
    )


def payment_from_orm(row: PaymentORM) -> Payment:
    employee = row.received_by.business_id if row.received_by else None
    return Payment(
        id=row.business_id,
        invoice_id=row.invoice.business_id,
        amount=money_from_columns(row.amount_amount, row.amount_currency),
        method=row.method,
        status=row.status,
        received_on=row.received_on,
        created_at=row.created_at,
        updated_at=row.updated_at,
        reference=row.reference,
        received_by_employee_id=employee,
        notes=row.notes,
    )


def invoice_from_orm(row: InvoiceORM, *, detail: bool) -> Invoice:
    work_order = row.work_order.business_id if row.work_order else None
    invoice = Invoice(
        id=row.business_id,
        customer_id=row.customer.business_id,
        status=row.status,
        subtotal=money_from_columns(row.subtotal_amount, row.subtotal_currency),
        tax=money_from_columns(row.tax_amount, row.tax_currency),
        adjustments=money_from_columns(
            row.adjustments_amount, row.adjustments_currency
        ),
        total=money_from_columns(row.total_amount, row.total_currency),
        amount_paid=money_from_columns(
            row.amount_paid_amount, row.amount_paid_currency
        ),
        balance=money_from_columns(row.balance_amount, row.balance_currency),
        created_at=row.created_at,
        updated_at=row.updated_at,
        work_order_id=work_order,
        issued_on=row.issued_on,
        due_on=row.due_on,
        voided_on=row.voided_on,
        void_reason=row.void_reason,
        notes=row.notes,
    )
    if detail:
        invoice.lines = [invoice_line_from_orm(item) for item in row.lines]
        invoice.payments = [payment_from_orm(item) for item in row.payments]
    return invoice
