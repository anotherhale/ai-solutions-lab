"""Persist procedure-page vectors in PostgreSQL.

The table is the trusted index. Rows are procedure ids only. Document
version bytes and extractions are refused before insert.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from wasatch_api.customer_service.domain.embeddings import ProcedurePageEmbedding
from wasatch_api.shared.database.vector import (
    PROCEDURE_EMBEDDING_WIDTH,
    parse_vector_literal,
    vector_literal,
)
from wasatch_api.shared.errors import InvalidParameterError

_PROCEDURE_ID = re.compile(r"^proc_[0-9]{4}$")


class ProcedureEmbeddingRepository:
    """Replace and read ``procedure_page_embeddings``."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def replace_procedure_pages(self, rows: Sequence[ProcedurePageEmbedding]) -> None:
        for row in rows:
            if _PROCEDURE_ID.fullmatch(row.procedure_id) is None:
                raise InvalidParameterError(
                    "the trusted index stores procedure pages only"
                )
            if len(row.vector) != PROCEDURE_EMBEDDING_WIDTH:
                raise InvalidParameterError(
                    "embedding width does not match the procedure column"
                )
        self.session.execute(text("DELETE FROM procedure_page_embeddings"))
        for row in rows:
            self.session.execute(
                text(
                    """
                    INSERT INTO procedure_page_embeddings (
                        id,
                        procedure_id,
                        embedding_model,
                        embedding,
                        token_count,
                        embedded_at
                    )
                    VALUES (
                        CAST(:id AS uuid),
                        :procedure_id,
                        :embedding_model,
                        CAST(:embedding AS vector),
                        :token_count,
                        :embedded_at
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "procedure_id": row.procedure_id,
                    "embedding_model": row.model,
                    "embedding": vector_literal(row.vector),
                    "token_count": row.token_count,
                    "embedded_at": row.embedded_at,
                },
            )
        self.session.commit()

    def stored_among(self, procedure_ids: Sequence[str]) -> tuple[str, ...]:
        if not procedure_ids:
            return ()
        statement = text(
            """
            SELECT procedure_id
            FROM procedure_page_embeddings
            WHERE procedure_id IN :ids
            ORDER BY procedure_id
            """
        ).bindparams(bindparam("ids", expanding=True))
        rows = self.session.execute(statement, {"ids": list(procedure_ids)}).all()
        return tuple(str(row[0]) for row in rows)

    def order_by_similarity(
        self, procedure_ids: Sequence[str], query: Sequence[float]
    ) -> tuple[str, ...]:
        """Order stored ids by pgvector cosine distance to ``query``.

        A query whose width does not match the column keeps the given order.
        The read does not insert a row.
        """

        if not procedure_ids:
            return ()
        if len(query) != PROCEDURE_EMBEDDING_WIDTH:
            return tuple(procedure_ids)
        statement = text(
            """
            SELECT procedure_id
            FROM procedure_page_embeddings
            WHERE procedure_id IN :ids
            ORDER BY embedding <=> CAST(:query AS vector), procedure_id
            """
        ).bindparams(bindparam("ids", expanding=True))
        rows = self.session.execute(
            statement,
            {"ids": list(procedure_ids), "query": vector_literal(query)},
        ).all()
        return tuple(str(row[0]) for row in rows)

    def list_stored(self) -> tuple[tuple[str, str, tuple[float, ...], int], ...]:
        rows = self.session.execute(
            text(
                """
                SELECT procedure_id, embedding_model, embedding::text, token_count
                FROM procedure_page_embeddings
                ORDER BY procedure_id
                """
            )
        ).all()
        return tuple(
            (str(row[0]), str(row[1]), parse_vector_literal(str(row[2])), int(row[3]))
            for row in rows
        )
