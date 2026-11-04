from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_approval_requests_paginated(client: TestClient) -> None:
    response = client.get(
        "/api/v1/approval-requests", params={"page": 1, "page_size": 5}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 5
    assert body["total"] == 10
    assert [item["id"] for item in body["items"]] == [
        "apr_0001",
        "apr_0002",
        "apr_0003",
        "apr_0004",
        "apr_0005",
    ]


def test_filter_approval_requests(client: TestClient) -> None:
    pending = client.get("/api/v1/approval-requests", params={"status": "pending"})
    assert pending.status_code == 200
    assert pending.json()["total"] == 3
    assert [item["id"] for item in pending.json()["items"]] == [
        "apr_0001",
        "apr_0002",
        "apr_0010",
    ]

    message_send = client.get(
        "/api/v1/approval-requests",
        params={"status": "pending", "action_type": "send_customer_message"},
    )
    assert message_send.status_code == 200
    assert message_send.json()["total"] == 1
    assert message_send.json()["items"][0]["id"] == "apr_0001"

    invalid = client.get("/api/v1/approval-requests", params={"status": "sent"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_parameter"

    bad_action = client.get(
        "/api/v1/approval-requests", params={"action_type": "send_email"}
    )
    assert bad_action.status_code == 422
    assert bad_action.json()["error"]["code"] == "invalid_parameter"


def test_get_approval_request_includes_history(client: TestClient) -> None:
    pending = client.get("/api/v1/approval-requests/apr_0001")
    assert pending.status_code == 200
    body = pending.json()
    assert body["id"] == "apr_0001"
    assert body["status"] == "pending"
    assert body["action_type"] == "send_customer_message"
    assert body["subject_type"] == "message"
    assert body["subject_id"] == "msg_0016"
    assert body["requested_by_employee_id"] == "emp_0006"
    assert body["reviewer_employee_id"] is None
    assert body["decided_at"] is None
    assert body["decision_history"] == []

    decided = client.get("/api/v1/approval-requests/apr_0003")
    assert decided.status_code == 200
    history = decided.json()["decision_history"]
    assert decided.json()["status"] == "approved"
    assert decided.json()["reviewer_employee_id"] == "emp_0001"
    assert len(history) == 1
    assert history[0]["actor_employee_id"] == "emp_0001"
    assert history[0]["from_status"] == "pending"
    assert history[0]["to_status"] == "approved"
    assert history[0]["note"] == "Rate matches signed quote."


def test_approval_request_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/approval-requests/apr_9999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_message_is_readable_with_its_approval_request(client: TestClient) -> None:
    response = client.get("/api/v1/messages/msg_0016")
    assert response.status_code == 200
    message = response.json()
    assert message["status"] == "pending_approval"
    assert message["requires_approval"] is True
    assert message["approval_request_id"] == "apr_0001"
    approval = message["approval_request"]
    assert approval["id"] == "apr_0001"
    assert approval["status"] == "pending"
    assert approval["subject_id"] == "msg_0016"
    assert approval["decision_history"] == []

    direct = client.get("/api/v1/approval-requests/apr_0001")
    assert direct.status_code == 200
    assert direct.json()["subject_id"] == message["id"]


def test_approval_resource_stays_read_only(
    client: TestClient, decision_transaction: None
) -> None:
    for method in ("post", "put", "patch", "delete"):
        response = getattr(client, method)("/api/v1/approval-requests/apr_0001")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "forbidden"
        assert response.json()["error"]["message"] == "writes are denied"
    missing = client.post("/api/v1/approval-requests/apr_0001/decisions")
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "invalid_parameter"
    current = client.get("/api/v1/approval-requests/apr_0001")
    assert current.status_code == 200
    assert current.json()["status"] == "pending"
    assert current.json()["decision_history"] == []
    assert current.json()["decided_at"] is None
    spec = client.get("/openapi.json").json()
    decision_path = "/api/v1/approval-requests/{approval_id}/decisions"
    draft_path = "/api/v1/support-tickets/{ticket_id}/draft-replies"
    extraction_path = "/api/v1/document-extractions/{extraction_id}/decisions"
    assert set(spec["paths"][decision_path]) == {"post"}
    assert set(spec["paths"][draft_path]) == {"post"}
    assert set(spec["paths"][extraction_path]) == {"post"}
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
        allowed = {"post"} if path in writes else {"get", "head"}
        assert http_methods & set(operations) <= allowed


def test_list_audit_events_paginated(client: TestClient) -> None:
    response = client.get("/api/v1/audit-events", params={"page": 1, "page_size": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 5
    assert body["total"] == 50
    assert [item["id"] for item in body["items"]] == [
        "aud_0001",
        "aud_0002",
        "aud_0003",
        "aud_0004",
        "aud_0005",
    ]
    assert "updated_at" not in body["items"][0]


def test_filter_and_get_audit_events(client: TestClient) -> None:
    pending = client.get("/api/v1/audit-events", params={"outcome": "pending"})
    assert pending.status_code == 200
    assert pending.json()["total"] == 2
    assert [item["id"] for item in pending.json()["items"]] == ["aud_0045", "aud_0046"]

    linked = client.get(
        "/api/v1/audit-events",
        params={"approval_request_id": "apr_0001", "page_size": 100},
    )
    assert linked.status_code == 200
    assert linked.json()["total"] == 1
    assert linked.json()["items"][0]["id"] == "aud_0045"
    assert linked.json()["items"][0]["subject_id"] == "apr_0001"

    detail = client.get("/api/v1/audit-events/aud_0045")
    assert detail.status_code == 200
    event = detail.json()
    assert event["id"] == "aud_0045"
    assert event["outcome"] == "pending"
    assert event["actor_employee_id"] == "emp_0006"
    assert event["approval_request_id"] == "apr_0001"
    assert event["action"] == "approval.updated"
    assert "updated_at" not in event

    missing = client.get("/api/v1/audit-events/aud_9999")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"

    invalid = client.get("/api/v1/audit-events", params={"outcome": "approved"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_parameter"


def test_governance_routes_are_read_only(client: TestClient) -> None:
    for path in ("/api/v1/approval-requests", "/api/v1/audit-events"):
        posted = client.post(path)
        deleted = client.delete(path)
        assert posted.status_code == 403
        assert deleted.status_code == 403
        assert posted.json()["error"]["code"] == "forbidden"
    assert client.delete("/api/v1/audit-events/aud_0001").status_code == 403
    assert client.patch("/api/v1/audit-events/aud_0001").status_code == 403
