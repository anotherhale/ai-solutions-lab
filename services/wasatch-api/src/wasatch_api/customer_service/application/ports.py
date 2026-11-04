"""Ports for customer-service adapters."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from wasatch_api.customer_service.domain.embeddings import ProcedurePageEmbedding
from wasatch_api.customer_service.domain.entities import Message
from wasatch_api.customer_service.domain.retrieval import RetrievalResult


class RetrievalPort(Protocol):
    """Read persisted history for one customer and matching procedure pages.

    History is a relational read. Procedure pages may be ordered with stored
    vectors when the procedure index has been filled. The read does not send
    a customer message.
    """

    def retrieve_for_ticket(self, ticket_id: str) -> RetrievalResult | None:
        """Return retrieval for the ticket, or None when that ticket is absent."""


class ProcedureEmbeddingStore(Protocol):
    """Persist synthetic procedure-page vectors. Extractions are not stored."""

    def replace_procedure_pages(self, rows: Sequence[ProcedurePageEmbedding]) -> None:
        """Replace the trusted procedure index."""

    def stored_among(self, procedure_ids: Sequence[str]) -> tuple[str, ...]:
        """Return which of these procedure ids already have a vector."""

    def order_by_similarity(
        self, procedure_ids: Sequence[str], query: Sequence[float]
    ) -> tuple[str, ...]:
        """Order stored procedure ids by distance to the query vector."""


class SuggestedReplyStore(Protocol):
    """Persist one unsent suggested reply and, when required, its approval."""

    def save_suggested_reply(
        self,
        *,
        ticket_id: str,
        author_employee_id: str,
        body: str,
        requires_approval: bool,
        drafted_at: datetime,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> Message:
        """Insert the reply. The status is never ``sent``."""
