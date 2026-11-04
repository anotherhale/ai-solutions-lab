"""Ports for customer-service adapters."""

from __future__ import annotations

from typing import Protocol

from wasatch_api.customer_service.domain.retrieval import RetrievalResult


class RetrievalPort(Protocol):
    """Read persisted history for one customer and matching procedure pages.

    The first adapter uses relational queries and local text search. It does
    not call a model and does not read a vector column.
    """

    def retrieve_for_ticket(self, ticket_id: str) -> RetrievalResult | None:
        """Return retrieval for the ticket, or None when that ticket is absent."""
