"""Read use case for ticket retrieval."""

from __future__ import annotations

from wasatch_api.customer_service.application.ports import RetrievalPort
from wasatch_api.customer_service.domain.retrieval import RetrievalResult
from wasatch_api.shared.errors import NotFoundError


class RetrievalQueries:
    def __init__(self, retrieval: RetrievalPort) -> None:
        self.retrieval = retrieval

    def for_ticket(self, ticket_id: str) -> RetrievalResult:
        result = self.retrieval.retrieve_for_ticket(ticket_id)
        if result is None:
            raise NotFoundError(f"support ticket {ticket_id} was not found")
        return result
