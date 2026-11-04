"""Suggested-reply rules without a database or a provider client."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from wasatch_api.ai.application.ports import ChatCompletion, ChatMessage
from wasatch_api.customer_service.application.draft_reply import DraftSuggestedReply
from wasatch_api.customer_service.domain.commitments import (
    outbound_text_commits_company,
    reply_cites_retrieval,
)
from wasatch_api.customer_service.domain.entities import Message
from wasatch_api.customer_service.domain.retrieval import (
    HistoryPassage,
    ProcedurePage,
    RetrievalResult,
)
from wasatch_api.shared.errors import InvalidParameterError, NotFoundError
from wasatch_api.workforce.domain.entities import LaboratoryActor

ACTOR = LaboratoryActor(
    employee_id="emp_0001",
    role_id="role_0001",
    is_approver=True,
    status="active",
)
ROOFTOP = "Please send a technician. Rooftop unit is down."
NOW = datetime(2026, 11, 4, tzinfo=UTC)


def test_commitment_language_requires_approval() -> None:
    assert outbound_text_commits_company(
        "We can be on site Thursday at 08:00 if you approve overtime."
    )
    assert outbound_text_commits_company("We will send a technician on Thursday.")
    assert outbound_text_commits_company("The visit is $180.")
    assert not outbound_text_commits_company(
        "Sources: msg_0015. The rooftop unit is down."
    )
    assert not outbound_text_commits_company(
        "Do not promise an arrival time in the first reply."
    )


def test_grounding_requires_a_retrieved_source_id() -> None:
    result = _result()
    assert reply_cites_retrieval("See msg_0015 and proc_0001.", result)
    assert not reply_cites_retrieval("See msg_9999.", result)
    assert not reply_cites_retrieval("The rooftop unit is down.", result)


def test_missing_ticket_does_not_call_the_model() -> None:
    chat = _ScriptChat("unused")
    store = _MemoryStore()
    service = DraftSuggestedReply(_MissingRetrieval(), chat, store)
    with pytest.raises(NotFoundError):
        service.draft(ACTOR, "tkt_9999")
    assert chat.calls == []
    assert store.calls == []


def test_ungrounded_reply_is_not_stored() -> None:
    chat = _ScriptChat("We will send a technician on Thursday at 08:00.")
    store = _MemoryStore()
    service = DraftSuggestedReply(_ReadyRetrieval(), chat, store)
    with pytest.raises(InvalidParameterError, match="retrieved source"):
        service.draft(ACTOR, "tkt_0015")
    assert store.calls == []
    assert "Rooftop unit is down" in chat.calls[0]


def test_committing_reply_opens_approval_and_is_not_sent() -> None:
    chat = _ScriptChat(
        "Sources: msg_0015, proc_0001. The rooftop unit is down. "
        "We will send a technician on Thursday at 08:00."
    )
    store = _MemoryStore()
    service = DraftSuggestedReply(_ReadyRetrieval(), chat, store)
    message = service.draft(ACTOR, "tkt_0015")
    assert message.status == "pending_approval"
    assert message.status != "sent"
    assert message.requires_approval is True
    assert message.approval_request_id == "apr_0011"
    assert store.calls[0]["requires_approval"] is True
    assert store.calls[0]["author_employee_id"] == "emp_0001"


def test_acknowledgement_stays_a_draft_without_an_approval() -> None:
    chat = _ScriptChat("Sources: msg_0015, proc_0001. The rooftop unit is down.")
    store = _MemoryStore()
    service = DraftSuggestedReply(_ReadyRetrieval(), chat, store)
    message = service.draft(ACTOR, "tkt_0015")
    assert message.status == "draft"
    assert message.status != "sent"
    assert message.requires_approval is False
    assert message.approval_request_id is None
    assert store.calls[0]["requires_approval"] is False


class _ScriptChat:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[str] = []

    def complete(self, messages: tuple[ChatMessage, ...]) -> ChatCompletion:
        user = next(message.content for message in messages if message.role == "user")
        self.calls.append(user)
        return ChatCompletion(
            content=self.content,
            model="script-chat",
            prompt_tokens=1,
            completion_tokens=1,
        )


class _MemoryStore:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def save_suggested_reply(self, **kwargs) -> Message:
        self.calls.append(kwargs)
        requires_approval = bool(kwargs["requires_approval"])
        status = "pending_approval" if requires_approval else "draft"
        return Message(
            id="msg_0018",
            support_ticket_id="tkt_0015",
            direction="outbound",
            channel="portal",
            body=kwargs["body"],
            status=status,
            sent_at=NOW,
            created_at=NOW,
            updated_at=NOW,
            author_employee_id=kwargs["author_employee_id"],
            requires_approval=requires_approval,
            approval_request_id="apr_0011" if requires_approval else None,
        )


class _MissingRetrieval:
    def retrieve_for_ticket(self, ticket_id: str) -> None:
        return None


class _ReadyRetrieval:
    def retrieve_for_ticket(self, ticket_id: str) -> RetrievalResult:
        return _result()


def _result() -> RetrievalResult:
    return RetrievalResult(
        support_ticket_id="tkt_0015",
        customer_id="cust_0011",
        history=(HistoryPassage("message", "msg_0015", ROOFTOP),),
        procedures=(
            ProcedurePage(
                id="proc_0001",
                title="Rooftop unit is down",
                path="rooftop-unit-down.txt",
                text="Synthetic laboratory procedure.\nRooftop unit is down.",
                synthetic=True,
            ),
        ),
    )
