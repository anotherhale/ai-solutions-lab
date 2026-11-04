from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_support_tickets_paginated(client: TestClient) -> None:
    response = client.get("/api/v1/support-tickets", params={"page": 1, "page_size": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 5
    assert body["total"] == 15
    assert [item["id"] for item in body["items"]] == [
        "tkt_0001",
        "tkt_0002",
        "tkt_0003",
        "tkt_0004",
        "tkt_0005",
    ]


def test_filter_support_tickets(client: TestClient) -> None:
    opened = client.get("/api/v1/support-tickets", params={"status": "opened"})
    assert opened.status_code == 200
    assert opened.json()["total"] == 1
    assert opened.json()["items"][0]["id"] == "tkt_0001"

    by_customer = client.get(
        "/api/v1/support-tickets", params={"customer_id": "cust_0001"}
    )
    assert by_customer.status_code == 200
    assert by_customer.json()["total"] == 2

    assigned = client.get(
        "/api/v1/support-tickets",
        params={"assigned_employee_id": "emp_0007", "page_size": 100},
    )
    assert assigned.status_code == 200
    assert assigned.json()["total"] >= 1
    assert all(
        item["assigned_employee_id"] == "emp_0007" for item in assigned.json()["items"]
    )

    by_location = client.get(
        "/api/v1/support-tickets", params={"service_location_id": "loc_0004"}
    )
    assert by_location.status_code == 200
    assert by_location.json()["total"] == 1
    assert by_location.json()["items"][0]["id"] == "tkt_0004"

    invalid = client.get("/api/v1/support-tickets", params={"status": "nope"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_parameter"


def test_get_support_ticket_includes_messages(client: TestClient) -> None:
    response = client.get("/api/v1/support-tickets/tkt_0007")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "tkt_0007"
    assert body["status"] == "awaiting_customer"
    assert body["customer_id"] == "cust_0004"
    assert body["work_order_id"] == "wo_0007"
    assert body["service_location_id"] == "loc_0007"
    message_ids = [item["id"] for item in body["messages"]]
    assert message_ids == ["msg_0007", "msg_0016"]
    pending = body["messages"][1]
    assert pending["status"] == "pending_approval"
    assert pending["requires_approval"] is True
    assert pending["approval_request_id"] == "apr_0001"
    assert pending["author_employee_id"] == "emp_0006"


def test_support_ticket_detail_keeps_document_ids(client: TestClient) -> None:
    response = client.get("/api/v1/support-tickets/tkt_0003")
    assert response.status_code == 200
    assert response.json()["related_document_ids"] == ["doc_0003"]


def test_support_ticket_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/support-tickets/tkt_9999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_list_and_get_messages(client: TestClient) -> None:
    listed = client.get(
        "/api/v1/messages", params={"support_ticket_id": "tkt_0007", "page_size": 100}
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 2
    assert [item["id"] for item in listed.json()["items"]] == ["msg_0007", "msg_0016"]

    pending = client.get("/api/v1/messages", params={"status": "pending_approval"})
    assert pending.status_code == 200
    assert pending.json()["total"] == 1
    assert pending.json()["items"][0]["id"] == "msg_0016"

    detail = client.get("/api/v1/messages/msg_0016")
    assert detail.status_code == 200
    assert detail.json()["support_ticket_id"] == "tkt_0007"
    assert detail.json()["body"].startswith("We can be on site")

    missing = client.get("/api/v1/messages/msg_9999")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"

    invalid = client.get("/api/v1/messages", params={"status": "nope"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_parameter"


def test_list_and_get_interactions(client: TestClient) -> None:
    listed = client.get("/api/v1/interactions", params={"page_size": 100})
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 15
    assert [item["id"] for item in body["items"]] == sorted(
        item["id"] for item in body["items"]
    )

    by_customer = client.get(
        "/api/v1/interactions", params={"customer_id": "cust_0001"}
    )
    assert by_customer.status_code == 200
    assert by_customer.json()["total"] == 2

    detail = client.get("/api/v1/interactions/ixn_0001")
    assert detail.status_code == 200
    interaction = detail.json()
    assert interaction["id"] == "ixn_0001"
    assert interaction["customer_id"] == "cust_0001"
    assert interaction["support_ticket_id"] == "tkt_0001"
    assert interaction["work_order_id"] == "wo_0001"
    assert interaction["outcome"] == "answered"
    assert interaction["employee_id"] == "emp_0007"

    missing = client.get("/api/v1/interactions/ixn_9999")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"


def test_work_order_ticket_link_is_business_id(client: TestClient) -> None:
    linked = client.get("/api/v1/work-orders/wo_0001")
    assert linked.status_code == 200
    assert linked.json()["support_ticket_id"] == "tkt_0001"

    unlinked = client.get("/api/v1/work-orders/wo_0016")
    assert unlinked.status_code == 200
    assert unlinked.json()["support_ticket_id"] is None


def test_customer_service_routes_are_read_only(client: TestClient) -> None:
    for path in (
        "/api/v1/support-tickets",
        "/api/v1/messages",
        "/api/v1/interactions",
    ):
        assert client.post(path).status_code == 405
