"""Map invoice ORM rows to domain entities."""

from __future__ import annotations

from wasatch_api.finance.domain.entities import Invoice, InvoiceLine, Money
from wasatch_api.shared.database.models import InvoiceLineORM, InvoiceORM


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
