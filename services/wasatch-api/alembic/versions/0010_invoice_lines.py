"""Persist invoice line reference rows from synthetic fixtures.

Revision ID: 0010
Revises: 0009
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def _parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _valid_fixtures_dir() -> Path:
    configured = os.environ.get("WASATCH_FIXTURES_DIR", "").strip()
    if configured:
        return Path(configured)
    repo_root = Path(__file__).resolve().parents[4]
    return repo_root / "data" / "fixtures" / "valid"


def _backfill_invoice_lines() -> None:
    lines_path = _valid_fixtures_dir() / "invoice_lines.json"
    payload = json.loads(lines_path.read_text(encoding="utf-8"))
    records = payload["records"]
    connection = op.get_bind()
    for record in records:
        unit = record["unit_price"]
        total = record["line_total"]
        work_order_id = record.get("work_order_id")
        connection.execute(
            sa.text(
                """
                INSERT INTO invoice_lines (
                    id,
                    business_id,
                    invoice_id,
                    work_order_id,
                    description,
                    quantity,
                    unit_price_amount,
                    unit_price_currency,
                    line_total_amount,
                    line_total_currency,
                    line_type,
                    created_at,
                    updated_at
                )
                SELECT
                    CAST(:row_id AS uuid),
                    :business_id,
                    invoices.id,
                    work_orders.id,
                    :description,
                    :quantity,
                    :unit_price_amount,
                    :unit_price_currency,
                    :line_total_amount,
                    :line_total_currency,
                    :line_type,
                    :created_at,
                    :updated_at
                FROM invoices
                LEFT JOIN work_orders
                    ON work_orders.business_id = :work_order_business_id
                WHERE invoices.business_id = :invoice_business_id
                ON CONFLICT (business_id) DO NOTHING
                """
            ),
            {
                "row_id": str(uuid.uuid4()),
                "business_id": record["id"],
                "invoice_business_id": record["invoice_id"],
                "work_order_business_id": work_order_id,
                "description": record["description"],
                "quantity": Decimal(str(record["quantity"])),
                "unit_price_amount": Decimal(unit["amount"]),
                "unit_price_currency": unit["currency"],
                "line_total_amount": Decimal(total["amount"]),
                "line_total_currency": total["currency"],
                "line_type": record["line_type"],
                "created_at": _parse_datetime(record["created_at"]),
                "updated_at": _parse_datetime(record["updated_at"]),
            },
        )


def upgrade() -> None:
    op.create_table(
        "invoice_lines",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", sa.String(16), nullable=False, unique=True),
        sa.Column(
            "invoice_id",
            UUID,
            sa.ForeignKey("invoices.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "work_order_id",
            UUID,
            sa.ForeignKey("work_orders.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 4), nullable=False),
        sa.Column("unit_price_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("unit_price_currency", sa.String(3), nullable=False),
        sa.Column("line_total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("line_total_currency", sa.String(3), nullable=False),
        sa.Column("line_type", sa.String(32), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    _backfill_invoice_lines()


def downgrade() -> None:
    op.drop_table("invoice_lines")
