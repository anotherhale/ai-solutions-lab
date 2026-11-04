from __future__ import annotations

import pytest

from wasatch_api.customer_service.application.retrieval import RetrievalQueries
from wasatch_api.shared.errors import NotFoundError


class _MissingTicket:
    def retrieve_for_ticket(self, ticket_id: str):
        assert ticket_id == "tkt_9999"
        return None


def test_missing_ticket_is_not_found() -> None:
    service = RetrievalQueries(_MissingTicket())
    with pytest.raises(NotFoundError, match="tkt_9999"):
        service.for_ticket("tkt_9999")
