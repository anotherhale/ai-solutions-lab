"""Ports for customer-service adapters."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from wasatch_api.customer_service.domain.entities import Message
from wasatch_api.customer_service.domain.retrieval import RetrievalResult


class RetrievalPort(Protocol):
    """Read persisted history for one customer and matching procedure pages.

    The first adapter uses relational queries and local text search. It does
    not call a model and does not read a vector column.
    """

    def retrieve_for_ticket(self, ticket_id: str) -> RetrievalResult | None:
        """Return retrieval for the ticket, or None when that ticket is absent."""


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
