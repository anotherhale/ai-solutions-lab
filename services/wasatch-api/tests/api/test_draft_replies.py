"""Draft a grounded reply for tkt_0015 and leave it unsent."""

from __future__ import annotations

import logging
from io import StringIO

import pytest
from fastapi.testclient import TestClient

from wasatch_api.ai.application.ports import ChatCompletion, ChatMessage
from wasatch_api.shared.logging import StructuredFormatter
from wasatch_api.workforce.infrastructure.local_authenticator import (
    LABORATORY_ACTOR_HEADER,
)

DRAFT = "/api/v1/support-tickets/tkt_0015/draft-replies"
INBOUND = "Please send a technician. Rooftop unit is down."


def test_tkt_0015_reply_is_grounded_and_rejection_leaves_it_unsent(
    client: TestClient, decision_transaction: None
) -> None:
    before = client.get("/api/v1/messages", params={"support_ticket_id": "tkt_0015"})
    assert before.status_code == 200
    assert [item["id"] for item in before.json()["items"]] == ["msg_0015"]

    response = client.post(DRAFT)
    assert response.status_code == 200
    message = response.json()
    assert message["support_ticket_id"] == "tkt_0015"
    assert message["direction"] == "outbound"
    assert message["channel"] == "portal"
    assert message["author_employee_id"] == "emp_0001"
    assert message["status"] == "pending_approval"
    assert message["status"] != "sent"
    assert message["requires_approval"] is True
    assert "msg_0015" in message["body"]
    assert "proc_0001" in message["body"]
    assert "rooftop" in message["body"].lower()
    assert "we will" in message["body"].lower()
    assert "08:00" in message["body"]
    approval = message["approval_request"]
    assert approval["action_type"] == "send_customer_message"
    assert approval["status"] == "pending"
    assert approval["subject_type"] == "message"
    assert approval["subject_id"] == message["id"]
    assert approval["requested_by_employee_id"] == "emp_0001"
    assert approval["executed_at"] is None
    assert approval["decision_history"] == []
    assert message["body"] not in approval["rationale"]

    inbound = client.get("/api/v1/messages/msg_0015")
    assert inbound.json()["body"] == INBOUND
    assert inbound.json()["status"] == "sent"

    rejected = client.post(
        f"/api/v1/approval-requests/{approval['id']}/decisions",
        json={"decision": "rejected", "note": "Do not promise an arrival time."},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["executed_at"] is None
    assert rejected.json()["reviewer_employee_id"] == "emp_0001"

    after = client.get(f"/api/v1/messages/{message['id']}")
    assert after.status_code == 200
    body = after.json()
    assert body["status"] == "pending_approval"
    assert body["status"] != "sent"
    assert body["body"] == message["body"]
    assert body["approval_request"]["status"] == "rejected"
    assert body["approval_request"]["executed_at"] is None

    ticket = client.get("/api/v1/support-tickets/tkt_0015")
    saved = next(
        item for item in ticket.json()["messages"] if item["id"] == message["id"]
    )
    assert saved["status"] != "sent"

    audit = client.get(
        "/api/v1/audit-events",
        params={"approval_request_id": approval["id"], "page_size": 100},
    )
    assert audit.status_code == 200
    actions = {item["action"]: item for item in audit.json()["items"]}
    drafted = actions["message.drafted"]
    assert drafted["outcome"] == "pending"
    assert drafted["subject_id"] == message["id"]
    assert drafted["actor_employee_id"] == "emp_0001"
    assert drafted["details"]["model"] == "fake-chat"
    assert drafted["details"]["requires_approval"] is True
    assert drafted["details"]["status"] == "pending_approval"
    assert message["body"] not in str(drafted["details"])
    decided = actions["approval.decided"]
    assert decided["details"]["to_status"] == "rejected"
    assert message["body"] not in str(decided)


def test_non_approver_can_draft_and_cannot_reject(
    anonymous_client: TestClient, decision_transaction: None
) -> None:
    headers = {LABORATORY_ACTOR_HEADER: "emp_0004"}
    response = anonymous_client.post(DRAFT, headers=headers)
    assert response.status_code == 200
    message = response.json()
    assert message["author_employee_id"] == "emp_0004"
    assert message["status"] == "pending_approval"
    assert message["status"] != "sent"
    assert message["approval_request"]["requested_by_employee_id"] == "emp_0004"
    denied = anonymous_client.post(
        f"/api/v1/approval-requests/{message['approval_request']['id']}/decisions",
        headers=headers,
        json={"decision": "rejected"},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "forbidden"
    still = anonymous_client.get(f"/api/v1/messages/{message['id']}", headers=headers)
    assert still.json()["status"] != "sent"
    assert still.json()["approval_request"]["status"] == "pending"
    assert still.json()["body"] == message["body"]


def test_acknowledgement_is_a_draft_without_an_approval(
    client: TestClient,
    decision_transaction: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "wasatch_api.api.dependencies.build_model_provider",
        lambda settings: _QuietChat(),
    )
    response = client.post(DRAFT)
    assert response.status_code == 200
    message = response.json()
    assert message["status"] == "draft"
    assert message["status"] != "sent"
    assert message["requires_approval"] is False
    assert message["approval_request_id"] is None
    assert message["approval_request"] is None
    assert "msg_0015" in message["body"]
    assert "rooftop" in message["body"].lower()
    assert "08:00" not in message["body"]
    listed = client.get(
        "/api/v1/messages",
        params={"support_ticket_id": "tkt_0015", "status": "draft"},
    )
    assert [item["id"] for item in listed.json()["items"]] == [message["id"]]


def test_draft_unknown_ticket_is_not_found(client: TestClient) -> None:
    response = client.post("/api/v1/support-tickets/tkt_9999/draft-replies")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_draft_log_omits_the_reply_body(
    client: TestClient, decision_transaction: None
) -> None:
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(StructuredFormatter())
    child = logging.getLogger("wasatch_api.access")
    previous = child.level
    child.setLevel(logging.INFO)
    child.addHandler(handler)
    try:
        response = client.post(DRAFT)
    finally:
        child.removeHandler(handler)
        child.setLevel(previous)
    assert response.status_code == 200
    logged = stream.getvalue()
    assert "We will send a technician" not in logged
    assert "Rooftop unit is down" not in logged
    assert "replace-me" not in logged
    assert "tkt_0015" in logged


class _QuietChat:
    def complete(self, messages: tuple[ChatMessage, ...]) -> ChatCompletion:
        return ChatCompletion(
            content="Sources: msg_0015, proc_0001. The rooftop unit is down.",
            model="script-chat",
            prompt_tokens=3,
            completion_tokens=8,
        )
