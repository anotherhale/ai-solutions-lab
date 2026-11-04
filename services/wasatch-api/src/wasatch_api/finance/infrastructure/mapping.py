"""Map invoice ORM rows to domain entities."""

from __future__ import annotations

from wasatch_api.finance.domain.entities import Invoice
from wasatch_api.shared.database.models import InvoiceORM


def invoice_from_orm(row: InvoiceORM) -> Invoice:
    return Invoice(
        id=row.business_id,
        customer_id=row.customer.business_id,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
