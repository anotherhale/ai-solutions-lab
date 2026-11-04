"""Procedure-page embeddings in the existing PostgreSQL database.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-04

Stores synthetic procedure page text in ``procedure_page_embeddings.embedding``.
The column width is the vector returned by the laboratory embedding port.
That default is the deterministic fake port and is 8-dimensional. Domain code
does not choose another width. Document version bytes are not files in this
repository and are not embedded. Extractions are not inserted.

Downgrade drops ``procedure_page_embeddings``. That is safe on the synthetic
database. Procedure pages stay files under ``data/documents/procedures/``.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# This revision is the first embedding column. A later width needs a new
# revision. The upgrade reads the laboratory port and refuses a mismatch.
_LABORATORY_WIDTH = 8


def upgrade() -> None:
    width = _laboratory_embedding_width()
    op.execute(
        f"""
        CREATE TABLE procedure_page_embeddings (
            id UUID PRIMARY KEY,
            procedure_id VARCHAR(16) NOT NULL,
            embedding_model VARCHAR(64) NOT NULL,
            embedding vector({width}) NOT NULL,
            token_count INTEGER NOT NULL,
            embedded_at TIMESTAMPTZ NOT NULL,
            CONSTRAINT uq_procedure_page_embeddings_procedure_id
                UNIQUE (procedure_id),
            CONSTRAINT ck_procedure_page_embeddings_procedure_id
                CHECK (procedure_id ~ '^proc_[0-9]{{4}}$')
        )
        """
    )
    op.execute(
        """
        COMMENT ON TABLE procedure_page_embeddings IS
        'Synthetic procedure page text only. Document version bytes and '
        'extractions are excluded. The vector is not a trusted model.'
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS procedure_page_embeddings")


def _laboratory_embedding_width() -> int:
    from wasatch_api.ai.infrastructure.fake import FakeModelPort

    width = len(FakeModelPort().embed(("synthetic procedure page",))[0].vector)
    if width != _LABORATORY_WIDTH:
        raise RuntimeError(
            "revision 0006 stores the 8-dimensional laboratory embedding"
        )
    return width
