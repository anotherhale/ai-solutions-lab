"""Documents, versions, and extractions.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-04

Persists synthetic document metadata from data/fixtures/valid/. Version rows
store a storage_path string. The bytes are not in this repository. Extraction
payloads are JSONB and stay untrusted. invoice_id stays a string because
invoices are not mapped. There is no vector column.

Downgrade drops document_extractions, document_versions, and documents. That
is safe on the synthetic database. Reload data/fixtures/valid/ after downgrade.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    create_document_tables()


def create_document_tables() -> None:
    op.create_table(
        "documents",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", sa.String(16), nullable=False, unique=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("document_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("untrusted", sa.Boolean(), nullable=False),
        sa.Column(
            "customer_id",
            UUID,
            sa.ForeignKey(
                "customers.id",
                name="fk_documents_customer",
                ondelete="SET NULL",
            ),
        ),
        sa.Column(
            "service_location_id",
            UUID,
            sa.ForeignKey(
                "service_locations.id",
                name="fk_documents_service_location",
                ondelete="SET NULL",
            ),
        ),
        sa.Column(
            "work_order_id",
            UUID,
            sa.ForeignKey(
                "work_orders.id",
                name="fk_documents_work_order",
                ondelete="SET NULL",
            ),
        ),
        sa.Column("invoice_id", sa.String(16)),
        sa.Column("current_version_id", UUID),
        sa.Column(
            "uploaded_by_employee_id",
            UUID,
            sa.ForeignKey(
                "employees.id",
                name="fk_documents_uploaded_by",
                ondelete="SET NULL",
            ),
        ),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_documents_document_type", "documents", ["document_type"])
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_index("ix_documents_source", "documents", ["source"])
    op.create_index("ix_documents_customer_id", "documents", ["customer_id"])
    op.create_index(
        "ix_documents_service_location_id", "documents", ["service_location_id"]
    )
    op.create_index("ix_documents_work_order_id", "documents", ["work_order_id"])
    op.create_index(
        "ix_documents_uploaded_by_employee_id",
        "documents",
        ["uploaded_by_employee_id"],
    )

    op.create_table(
        "document_versions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", sa.String(16), nullable=False, unique=True),
        sa.Column(
            "document_id",
            UUID,
            sa.ForeignKey(
                "documents.id",
                name="fk_document_versions_document",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(255), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("byte_size", sa.Integer()),
        sa.Column(
            "created_by_employee_id",
            UUID,
            sa.ForeignKey(
                "employees.id",
                name="fk_document_versions_created_by",
                ondelete="SET NULL",
            ),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "document_id",
            "version_number",
            name="uq_document_versions_number",
        ),
    )
    op.create_index(
        "ix_document_versions_document_id", "document_versions", ["document_id"]
    )

    op.create_table(
        "document_extractions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", sa.String(16), nullable=False, unique=True),
        sa.Column(
            "document_id",
            UUID,
            sa.ForeignKey(
                "documents.id",
                name="fk_document_extractions_document",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "document_version_id",
            UUID,
            sa.ForeignKey(
                "document_versions.id",
                name="fk_document_extractions_version",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("extractor", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3)),
        sa.Column("extracted_fields", postgresql.JSONB()),
        sa.Column(
            "reviewed_by_employee_id",
            UUID,
            sa.ForeignKey(
                "employees.id",
                name="fk_document_extractions_reviewed_by",
                ondelete="SET NULL",
            ),
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_notes", sa.Text()),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_document_extractions_document_id",
        "document_extractions",
        ["document_id"],
    )
    op.create_index(
        "ix_document_extractions_document_version_id",
        "document_extractions",
        ["document_version_id"],
    )
    op.create_index(
        "ix_document_extractions_status", "document_extractions", ["status"]
    )
    op.create_index(
        "ix_document_extractions_extractor", "document_extractions", ["extractor"]
    )

    op.create_foreign_key(
        "fk_documents_current_version",
        "documents",
        "document_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_documents_current_version_id", "documents", ["current_version_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_documents_current_version_id", table_name="documents")
    op.drop_constraint("fk_documents_current_version", "documents", type_="foreignkey")
    op.drop_index(
        "ix_document_extractions_extractor", table_name="document_extractions"
    )
    op.drop_index("ix_document_extractions_status", table_name="document_extractions")
    op.drop_index(
        "ix_document_extractions_document_version_id",
        table_name="document_extractions",
    )
    op.drop_index(
        "ix_document_extractions_document_id", table_name="document_extractions"
    )
    op.drop_table("document_extractions")
    op.drop_index("ix_document_versions_document_id", table_name="document_versions")
    op.drop_table("document_versions")
    op.drop_index("ix_documents_uploaded_by_employee_id", table_name="documents")
    op.drop_index("ix_documents_work_order_id", table_name="documents")
    op.drop_index("ix_documents_service_location_id", table_name="documents")
    op.drop_index("ix_documents_customer_id", table_name="documents")
    op.drop_index("ix_documents_source", table_name="documents")
    op.drop_index("ix_documents_status", table_name="documents")
    op.drop_index("ix_documents_document_type", table_name="documents")
    op.drop_table("documents")
