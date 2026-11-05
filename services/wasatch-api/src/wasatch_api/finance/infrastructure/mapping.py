"""Map invoice ORM rows to domain entities."""

from __future__ import annotations

from wasatch_api.finance.domain.entities import Invoice, InvoiceLine, Money, Payment
from wasatch_api.shared.database.models import InvoiceLineORM, InvoiceORM, PaymentORM


def invoice_from_orm(row: InvoiceORM) -> Invoice:
    return Invoice(
        id=row.business_id,
        customer_id=row.customer.business_id,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def invoice_line_from_orm(row: InvoiceLineORM) -> InvoiceLine:
    work_order_id = row.work_order.business_id if row.work_order is not None else None
    return InvoiceLine(
        id=row.business_id,
        invoice_id=row.invoice.business_id,
        work_order_id=work_order_id,
        description=row.description,
        quantity=row.quantity,
        unit_price=Money(
            amount=row.unit_price_amount,
            currency=row.unit_price_currency,
        ),
        line_total=Money(
            amount=row.line_total_amount,
            currency=row.line_total_currency,
        ),
        line_type=row.line_type,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def payment_from_orm(row: PaymentORM) -> Payment:
    received_by = row.received_by.business_id if row.received_by is not None else None
    return Payment(
        id=row.business_id,
        invoice_id=row.invoice.business_id,
        amount=Money(amount=row.amount, currency=row.amount_currency),
        method=row.method,
        status=row.status,
        received_on=row.received_on,
        reference=row.reference,
        received_by_employee_id=received_by,
        notes=row.notes,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
