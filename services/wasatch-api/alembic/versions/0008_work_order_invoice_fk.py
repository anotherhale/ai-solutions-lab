"""Invoice reference rows and work_orders.invoice_id foreign key.

Revision ID: 0008
Revises: 0007

Documents keep a string invoice_id. Only work_orders gain a foreign key to
invoices.business_id so invoiced work must reference a persisted invoice row.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def _parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _backfill_invoices() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    payload = json.loads(
        (repo_root / "data" / "fixtures" / "valid" / "invoices.json").read_text(
            encoding="utf-8"
        )
    )
    records = payload["records"]
    connection = op.get_bind()
    for record in records:
        connection.execute(
            sa.text(
                """
                INSERT INTO invoices (
                    id, business_id, customer_id, status, created_at, updated_at
                )
                SELECT
                    CAST(:row_id AS uuid),
                    :business_id,
                    customers.id,
                    :status,
                    :created_at,
                    :updated_at
                FROM customers
                WHERE customers.business_id = :customer_id
                ON CONFLICT (business_id) DO NOTHING
                """
            ),
            {
                "row_id": str(uuid.uuid4()),
                "business_id": record["id"],
                "customer_id": record["customer_id"],
                "status": record["status"],
                "created_at": _parse_datetime(record["created_at"]),
                "updated_at": _parse_datetime(record["updated_at"]),
            },
        )


def upgrade() -> None:
    op.create_table(
        "invoices",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", sa.String(16), nullable=False, unique=True),
        sa.Column(
            "customer_id",
            UUID,
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_invoices_customer_id", "invoices", ["customer_id"])
    op.create_index("ix_invoices_status", "invoices", ["status"])
    _backfill_invoices()
    op.create_foreign_key(
        "fk_work_orders_invoice",
        "work_orders",
        "invoices",
        ["invoice_id"],
        ["business_id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_work_orders_invoice_id", "work_orders", ["invoice_id"])


def downgrade() -> None:
    op.drop_index("ix_work_orders_invoice_id", table_name="work_orders")
    op.drop_constraint("fk_work_orders_invoice", "work_orders", type_="foreignkey")
    op.drop_index("ix_invoices_status", table_name="invoices")
    op.drop_index("ix_invoices_customer_id", table_name="invoices")
    op.drop_table("invoices")
