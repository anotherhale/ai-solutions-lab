"""Synthetic invoices, invoice lines, and payments.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-04

Replaces work_orders.invoice_id string storage with a foreign key to
invoices.id. Existing values are matched to invoices.business_id. A business
id with no invoice row becomes NULL; seed restores it.

documents.invoice_id stays a string. This revision does not post a payment,
change a total, or add a vector column.

Downgrade copies invoice business ids back onto work_orders.invoice_id and
drops payments, invoice_lines, and invoices. That is safe on the synthetic
database.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)

BACKFILL_WORK_ORDER_INVOICES = """
UPDATE work_orders AS wo
SET invoice_row_id = inv.id
FROM invoices AS inv
WHERE wo.invoice_id = inv.business_id
"""

RESTORE_WORK_ORDER_INVOICE_BUSINESS_IDS = """
UPDATE work_orders AS wo
SET invoice_business_id = inv.business_id
FROM invoices AS inv
WHERE wo.invoice_id = inv.id
"""


def _money(name: str) -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(f"{name}_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(f"{name}_currency", sa.String(3), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "invoices",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", sa.String(16), nullable=False, unique=True),
        sa.Column(
            "customer_id",
            UUID,
            sa.ForeignKey(
                "customers.id",
                name="fk_invoices_customer",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "work_order_id",
            UUID,
            sa.ForeignKey(
                "work_orders.id",
                name="fk_invoices_work_order",
                ondelete="SET NULL",
            ),
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("issued_on", sa.Date(), nullable=True),
        sa.Column("due_on", sa.Date(), nullable=True),
        sa.Column("voided_on", sa.Date(), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
        *_money("subtotal"),
        *_money("tax"),
        *_money("adjustments"),
        *_money("total"),
        *_money("amount_paid"),
        *_money("balance"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_invoices_customer_id", "invoices", ["customer_id"])
    op.create_index("ix_invoices_work_order_id", "invoices", ["work_order_id"])
    op.create_index("ix_invoices_status", "invoices", ["status"])

    op.create_table(
        "invoice_lines",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", sa.String(16), nullable=False, unique=True),
        sa.Column(
            "invoice_id",
            UUID,
            sa.ForeignKey(
                "invoices.id",
                name="fk_invoice_lines_invoice",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "work_order_id",
            UUID,
            sa.ForeignKey(
                "work_orders.id",
                name="fk_invoice_lines_work_order",
                ondelete="SET NULL",
            ),
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        *_money("unit_price"),
        *_money("line_total"),
        sa.Column("line_type", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_invoice_lines_invoice_id", "invoice_lines", ["invoice_id"])
    op.create_index(
        "ix_invoice_lines_work_order_id", "invoice_lines", ["work_order_id"]
    )
    op.create_index("ix_invoice_lines_line_type", "invoice_lines", ["line_type"])

    op.create_table(
        "payments",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", sa.String(16), nullable=False, unique=True),
        sa.Column(
            "invoice_id",
            UUID,
            sa.ForeignKey(
                "invoices.id",
                name="fk_payments_invoice",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        *_money("amount"),
        sa.Column("method", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column("reference", sa.String(128), nullable=True),
        sa.Column(
            "received_by_employee_id",
            UUID,
            sa.ForeignKey(
                "employees.id",
                name="fk_payments_received_by",
                ondelete="SET NULL",
            ),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_payments_invoice_id", "payments", ["invoice_id"])
    op.create_index("ix_payments_status", "payments", ["status"])
    op.create_index(
        "ix_payments_received_by_employee_id",
        "payments",
        ["received_by_employee_id"],
    )
    replace_work_order_invoice_column()


def replace_work_order_invoice_column() -> None:
    op.add_column("work_orders", sa.Column("invoice_row_id", UUID))
    op.execute(BACKFILL_WORK_ORDER_INVOICES)
    op.drop_column("work_orders", "invoice_id")
    op.alter_column(
        "work_orders",
        "invoice_row_id",
        new_column_name="invoice_id",
        existing_type=UUID,
        existing_nullable=True,
    )
    op.create_foreign_key(
        "fk_work_orders_invoice",
        "work_orders",
        "invoices",
        ["invoice_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_work_orders_invoice_id", "work_orders", ["invoice_id"])


def downgrade() -> None:
    op.add_column("work_orders", sa.Column("invoice_business_id", sa.String(16)))
    op.execute(RESTORE_WORK_ORDER_INVOICE_BUSINESS_IDS)
    op.drop_index("ix_work_orders_invoice_id", table_name="work_orders")
    op.drop_constraint("fk_work_orders_invoice", "work_orders", type_="foreignkey")
    op.drop_column("work_orders", "invoice_id")
    op.alter_column(
        "work_orders",
        "invoice_business_id",
        new_column_name="invoice_id",
        existing_type=sa.String(16),
        existing_nullable=True,
    )
    op.drop_index(
        "ix_payments_received_by_employee_id",
        table_name="payments",
    )
    op.drop_index("ix_payments_status", table_name="payments")
    op.drop_index("ix_payments_invoice_id", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_invoice_lines_line_type", table_name="invoice_lines")
    op.drop_index("ix_invoice_lines_work_order_id", table_name="invoice_lines")
    op.drop_index("ix_invoice_lines_invoice_id", table_name="invoice_lines")
    op.drop_table("invoice_lines")
    op.drop_index("ix_invoices_status", table_name="invoices")
    op.drop_index("ix_invoices_work_order_id", table_name="invoices")
    op.drop_index("ix_invoices_customer_id", table_name="invoices")
    op.drop_table("invoices")
