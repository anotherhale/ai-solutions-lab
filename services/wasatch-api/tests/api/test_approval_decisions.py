"""Approve or reject apr_0001 without sending msg_0016."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from wasatch_api.workforce.infrastructure.local_authenticator import (
    LABORATORY_ACTOR_HEADER,
)

MESSAGE_BODY = "We can be on site Thursday at 08:00 if you approve overtime."
DECISION_PATH = "/api/v1/approval-requests/apr_0001/decisions"
OPENAPI_DECISION = "/api/v1/approval-requests/{approval_id}/decisions"
OPENAPI_DRAFT = "/api/v1/support-tickets/{ticket_id}/draft-replies"
OPENAPI_WRITES = {OPENAPI_DECISION, OPENAPI_DRAFT}


def _message_without_approval(payload: dict) -> dict:
    recorded = dict(payload)
    recorded.pop("approval_request", None)
    return recorded


@pytest.mark.parametrize(
    ("decision", "note"),
    [
        ("approved", "Overtime approved for Thursday."),
        ("rejected", "Customer did not approve overtime."),
    ],
)
def test_approver_can_approve_or_reject_without_sending(
    client: TestClient,
    decision_transaction: None,
    decision: str,
    note: str,
) -> None:
    before = client.get("/api/v1/messages/msg_0016")
    assert before.status_code == 200
    original = before.json()
    assert original["body"] == MESSAGE_BODY
    assert original["status"] == "pending_approval"
    assert original["approval_request"]["status"] == "pending"

    response = client.post(
        DECISION_PATH,
        json={"decision": decision, "note": note},
    )
    assert response.status_code == 200
    recorded = response.json()
    assert recorded["id"] == "apr_0001"
    assert recorded["status"] == decision
    assert recorded["action_type"] == "send_customer_message"
    assert recorded["subject_id"] == "msg_0016"
    assert recorded["reviewer_employee_id"] == "emp_0001"
    assert recorded["decided_at"]
    assert recorded["executed_at"] is None
    assert recorded["decision_notes"] == note
    assert recorded["rationale"] == "Overtime commitment needs manager approval."
    history = recorded["decision_history"]
    assert len(history) == 1
    assert history[0]["actor_employee_id"] == "emp_0001"
    assert history[0]["from_status"] == "pending"
    assert history[0]["to_status"] == decision
    assert history[0]["note"] == note
    assert history[0]["at"] == recorded["decided_at"]

    again = client.post(
        DECISION_PATH,
        json={"decision": decision, "note": "second decision"},
    )
    assert again.status_code == 422
    assert again.json()["error"]["code"] == "invalid_parameter"
    still = client.get("/api/v1/approval-requests/apr_0001")
    assert still.json()["status"] == decision
    assert len(still.json()["decision_history"]) == 1

    message = client.get("/api/v1/messages/msg_0016")
    assert message.status_code == 200
    body = message.json()
    assert _message_without_approval(body) == _message_without_approval(original)
    assert body["status"] == "pending_approval"
    assert body["status"] != "sent"
    assert body["body"] == MESSAGE_BODY
    assert body["approval_request"]["status"] == decision
    assert body["approval_request"]["reviewer_employee_id"] == "emp_0001"

    linked = client.get(
        "/api/v1/audit-events",
        params={"approval_request_id": "apr_0001", "page_size": 100},
    )
    assert linked.status_code == 200
    assert linked.json()["total"] == 2
    events = {item["id"]: item for item in linked.json()["items"]}
    assert "aud_0045" in events
    recorded_audit = events["aud_0051"]
    assert recorded_audit["action"] == "approval.decided"
    assert recorded_audit["outcome"] == "succeeded"
    assert recorded_audit["actor_type"] == "employee"
    assert recorded_audit["actor_employee_id"] == "emp_0001"
    assert recorded_audit["subject_type"] == "approval_request"
    assert recorded_audit["subject_id"] == "apr_0001"
    assert recorded_audit["approval_request_id"] == "apr_0001"
    assert recorded_audit["occurred_at"] == recorded["decided_at"]
    assert recorded_audit["details"] == {
        "from_status": "pending",
        "to_status": decision,
    }
    assert MESSAGE_BODY not in str(recorded_audit)
    assert "updated_at" not in recorded_audit
    pending = client.get("/api/v1/audit-events", params={"outcome": "pending"})
    assert pending.json()["total"] == 2


def test_non_approver_cannot_decide_and_message_stays_pending(
    anonymous_client: TestClient, decision_transaction: None
) -> None:
    headers = {LABORATORY_ACTOR_HEADER: "emp_0004"}
    before = anonymous_client.get("/api/v1/messages/msg_0016", headers=headers)
    assert before.status_code == 200
    original = before.json()
    denied = anonymous_client.post(
        DECISION_PATH,
        headers=headers,
        json={"decision": "approved", "note": "dispatcher override"},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "forbidden"
    current = anonymous_client.get(
        "/api/v1/approval-requests/apr_0001", headers=headers
    )
    assert current.status_code == 200
    assert current.json()["status"] == "pending"
    assert current.json()["reviewer_employee_id"] is None
    assert current.json()["decided_at"] is None
    assert current.json()["decision_history"] == []
    message = anonymous_client.get("/api/v1/messages/msg_0016", headers=headers)
    assert message.json() == original
    assert message.json()["status"] == "pending_approval"
    linked = anonymous_client.get(
        "/api/v1/audit-events",
        headers=headers,
        params={"approval_request_id": "apr_0001", "page_size": 100},
    )
    assert linked.json()["total"] == 1
    assert linked.json()["items"][0]["id"] == "aud_0045"


def test_decision_command_rejects_other_actions_and_unknown_requests(
    client: TestClient, decision_transaction: None
) -> None:
    invoice = client.post(
        "/api/v1/approval-requests/apr_0002/decisions",
        json={"decision": "approved", "note": "not this command"},
    )
    assert invoice.status_code == 422
    assert invoice.json()["error"]["code"] == "invalid_parameter"
    still_pending = client.get("/api/v1/approval-requests/apr_0002")
    assert still_pending.json()["status"] == "pending"
    assert still_pending.json()["decision_history"] == []

    missing = client.post(
        "/api/v1/approval-requests/apr_9999/decisions",
        json={"decision": "rejected"},
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"

    invalid = client.post(DECISION_PATH, json={"decision": "executed"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_parameter"
    untouched = client.get("/api/v1/approval-requests/apr_0001")
    assert untouched.json()["status"] == "pending"
    assert untouched.json()["executed_at"] is None
    audits = client.get("/api/v1/audit-events", params={"page_size": 100})
    assert audits.json()["total"] == 50


def test_openapi_exposes_the_decision_and_draft_writes(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    assert set(spec["paths"][OPENAPI_DECISION]) == {"post"}
    assert set(spec["paths"][OPENAPI_DRAFT]) == {"post"}
    http_methods = {
        "get",
        "post",
        "put",
        "patch",
        "delete",
        "head",
        "options",
        "trace",
    }
    for path, operations in spec["paths"].items():
        allowed = {"post"} if path in OPENAPI_WRITES else {"get", "head"}
        assert http_methods & set(operations) <= allowed


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/v1/customers"),
        ("post", "/api/v1/audit-events"),
        ("delete", "/api/v1/audit-events/aud_0001"),
        ("put", "/api/v1/approval-requests/apr_0001"),
        ("patch", "/api/v1/messages/msg_0016"),
        ("put", "/api/v1/support-tickets/tkt_0015/draft-replies"),
        ("delete", "/api/v1/support-tickets/tkt_0015/draft-replies"),
    ],
)
def test_other_writes_stay_denied_for_an_approver(
    client: TestClient, method: str, path: str
) -> None:
    response = getattr(client, method)(path)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert response.json()["error"]["message"] == "writes are denied"
