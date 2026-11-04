"""Laboratory actor authentication and default-deny writes."""

from __future__ import annotations

import json
import logging
from io import StringIO

from fastapi.testclient import TestClient

from wasatch_api.shared.logging import StructuredFormatter
from wasatch_api.workforce.infrastructure.local_authenticator import (
    LABORATORY_ACTOR_HEADER,
)


def test_anonymous_write_is_rejected(anonymous_client: TestClient) -> None:
    response = anonymous_client.post("/api/v1/customers")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"
    decision = anonymous_client.post("/api/v1/approval-requests/apr_0001/decisions")
    assert decision.status_code == 401
    assert decision.json()["error"]["code"] == "unauthenticated"
    draft = anonymous_client.post("/api/v1/support-tickets/tkt_0015/draft-replies")
    assert draft.status_code == 401
    assert draft.json()["error"]["code"] == "unauthenticated"
    extraction = anonymous_client.post("/api/v1/document-extractions/dx_0003/decisions")
    assert extraction.status_code == 401
    assert extraction.json()["error"]["code"] == "unauthenticated"


def test_anonymous_customer_and_ticket_reads_are_rejected(
    anonymous_client: TestClient,
) -> None:
    customer = anonymous_client.get("/api/v1/customers/cust_0001")
    ticket = anonymous_client.get("/api/v1/support-tickets/tkt_0007")
    assert customer.status_code == 401
    assert ticket.status_code == 401
    assert customer.json()["error"]["code"] == "unauthenticated"
    unknown = anonymous_client.get(
        "/api/v1/support-tickets/tkt_0007",
        headers={LABORATORY_ACTOR_HEADER: "emp_9999"},
    )
    assert unknown.status_code == 401
    blank = anonymous_client.get(
        "/api/v1/customers/cust_0001",
        headers={LABORATORY_ACTOR_HEADER: "  "},
    )
    assert blank.status_code == 401


def test_authenticated_laboratory_actor_can_read_a_ticket(
    anonymous_client: TestClient,
) -> None:
    response = anonymous_client.get(
        "/api/v1/support-tickets/tkt_0007",
        headers={LABORATORY_ACTOR_HEADER: "emp_0006"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "tkt_0007"
    assert body["customer_id"] == "cust_0004"
    pending = body["messages"][1]
    assert pending["id"] == "msg_0016"
    assert pending["status"] == "pending_approval"


def test_non_approver_can_read_but_cannot_record_a_decision(
    anonymous_client: TestClient, decision_transaction: None
) -> None:
    headers = {LABORATORY_ACTOR_HEADER: "emp_0004"}
    ticket = anonymous_client.get("/api/v1/support-tickets/tkt_0007", headers=headers)
    assert ticket.status_code == 200
    denied = anonymous_client.post(
        "/api/v1/approval-requests/apr_0001/decisions",
        headers=headers,
        json={"decision": "approved"},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "forbidden"
    assert denied.json()["error"]["message"] == "writes are denied"
    current = anonymous_client.get(
        "/api/v1/approval-requests/apr_0001", headers=headers
    )
    assert current.status_code == 200
    assert current.json()["status"] == "pending"
    assert current.json()["decision_history"] == []
    message = anonymous_client.get("/api/v1/messages/msg_0016", headers=headers)
    assert message.status_code == 200
    assert message.json()["status"] == "pending_approval"
    assert message.json()["body"]
    spec = anonymous_client.get("/openapi.json").json()
    decision_path = "/api/v1/approval-requests/{approval_id}/decisions"
    draft_path = "/api/v1/support-tickets/{ticket_id}/draft-replies"
    extraction_path = "/api/v1/document-extractions/{extraction_id}/decisions"
    follow_up_path = "/api/v1/approval-requests/{approval_id}/follow-up-visits"
    assert set(spec["paths"][decision_path]) == {"post"}
    assert set(spec["paths"][draft_path]) == {"post"}
    assert set(spec["paths"][extraction_path]) == {"post"}
    assert set(spec["paths"][follow_up_path]) == {"get", "post"}
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
    writes = {decision_path, draft_path, extraction_path}
    for path, operations in spec["paths"].items():
        if path == follow_up_path:
            allowed = {"get", "head", "post"}
        elif path in writes:
            allowed = {"post"}
        else:
            allowed = {"get", "head"}
        assert http_methods & set(operations) <= allowed


def test_authenticated_write_is_denied_for_an_approver(client: TestClient) -> None:
    response = client.post("/api/v1/customers", json={"name": "not a customer write"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert response.json()["error"]["message"] == "writes are denied"
    audit = client.delete("/api/v1/audit-events/aud_0045")
    assert audit.status_code == 403
    current = client.get("/api/v1/approval-requests/apr_0001")
    assert current.status_code == 200
    assert current.json()["status"] == "pending"
    assert current.json()["decided_at"] is None


def test_health_stays_open_and_ticket_log_omits_the_message_body(
    anonymous_client: TestClient,
) -> None:
    health = anonymous_client.get("/health")
    assert health.status_code == 200
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(StructuredFormatter())
    child = logging.getLogger("wasatch_api.access")
    previous_level = child.level
    child.setLevel(logging.INFO)
    child.addHandler(handler)
    try:
        response = anonymous_client.get(
            "/api/v1/support-tickets/tkt_0007",
            headers={LABORATORY_ACTOR_HEADER: "emp_0001"},
        )
    finally:
        child.removeHandler(handler)
        child.setLevel(previous_level)
    assert response.status_code == 200
    message_body = response.json()["messages"][1]["body"]
    assert message_body
    logged = stream.getvalue()
    payload = json.loads(logged.strip().splitlines()[-1])
    assert payload["actor"] == "emp_0001"
    assert payload["subject"] == "tkt_0007"
    assert payload["outcome"] == "allowed"
    assert message_body not in logged
    assert "replace-me" not in logged
    assert "password" not in logged
