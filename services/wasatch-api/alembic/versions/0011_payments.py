"""Persist payment reference rows from synthetic fixtures.

Revision ID: 0011
Revises: 0010
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _valid_fixtures_dir() -> Path:
    configured = os.environ.get("WASATCH_FIXTURES_DIR", "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[4] / "data" / "fixtures" / "valid"


def _backfill_payments() -> None:
    path = _valid_fixtures_dir() / "payments.json"
    records = json.loads(path.read_text(encoding="utf-8"))["records"]
    connection = op.get_bind()
    for record in records:
        amount = record["amount"]
        received_by = record.get("received_by_employee_id")
        connection.execute(
            sa.text(
                """
                INSERT INTO payments (
                    id,
                    business_id,
                    invoice_id,
                    amount,
                    amount_currency,
                    method,
                    status,
                    received_on,
                    reference,
                    received_by_employee_id,
                    notes,
                    created_at,
                    updated_at
                )
                SELECT
                    CAST(:row_id AS uuid),
                    :business_id,
                    invoices.id,
                    :amount,
                    :amount_currency,
                    :method,
                    :status,
                    :received_on,
                    :reference,
                    employees.id,
                    :notes,
                    :created_at,
                    :updated_at
                FROM invoices
                LEFT JOIN employees
                    ON employees.business_id = :employee_business_id
                WHERE invoices.business_id = :invoice_business_id
                ON CONFLICT (business_id) DO NOTHING
                """
            ),
            {
                "row_id": str(uuid.uuid4()),
                "business_id": record["id"],
                "invoice_business_id": record["invoice_id"],
                "amount": Decimal(amount["amount"]),
                "amount_currency": amount["currency"],
                "method": record["method"],
                "status": record["status"],
                "received_on": _parse_date(record["received_on"]),
                "reference": record.get("reference"),
                "employee_business_id": received_by,
                "notes": record.get("notes"),
                "created_at": _parse_datetime(record["created_at"]),
                "updated_at": _parse_datetime(record["updated_at"]),
            },
        )


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", sa.String(16), nullable=False, unique=True),
        sa.Column(
            "invoice_id",
            UUID,
            sa.ForeignKey("invoices.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount_currency", sa.String(3), nullable=False),
        sa.Column("method", sa.String(32), nullable=False, index=True),
        sa.Column("status", sa.String(32), nullable=False, index=True),
        sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column("reference", sa.String(128), nullable=True),
        sa.Column(
            "received_by_employee_id",
            UUID,
            sa.ForeignKey("employees.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    _backfill_payments()


def downgrade() -> None:
    op.drop_table("payments")
