from __future__ import annotations

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "password" not in response.text.lower()
    assert "replace-me" not in response.text


def test_ready(client: TestClient) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["database"] == "up"


def test_list_customers_paginated(client: TestClient) -> None:
    response = client.get("/api/v1/customers", params={"page": 1, "page_size": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 5
    assert body["total"] == 15
    assert len(body["items"]) == 5
    ids = [item["id"] for item in body["items"]]
    assert ids == sorted(ids)
    assert "cust_0001" in ids


def test_search_and_status_filter(client: TestClient) -> None:
    search = client.get("/api/v1/customers", params={"q": "Pioneer"})
    assert search.status_code == 200
    assert search.json()["total"] == 1
    assert search.json()["items"][0]["id"] == "cust_0001"

    filtered = client.get("/api/v1/customers", params={"status": "prospect"})
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["id"] == "cust_0015"


def test_get_customer_includes_children(client: TestClient) -> None:
    response = client.get("/api/v1/customers/cust_0001")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "cust_0001"
    assert body["legal_name"].startswith("Pioneer Plaza")
    assert len(body["contacts"]) >= 2
    assert len(body["service_locations"]) >= 2
    assert "id" in body["contacts"][0]
    assert body["contacts"][0]["id"].startswith("con_")


def test_customer_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/customers/cust_9999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_invalid_customer_status(client: TestClient) -> None:
    response = client.get("/api/v1/customers", params={"status": "nope"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_parameter"


def test_invalid_page_size(client: TestClient) -> None:
    response = client.get("/api/v1/customers", params={"page_size": 0})
    assert response.status_code == 422


def test_service_location_includes_customer(client: TestClient) -> None:
    response = client.get("/api/v1/service-locations/loc_0001")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "loc_0001"
    assert body["customer"]["id"] == "cust_0001"


def test_service_location_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/service-locations/loc_9999")
    assert response.status_code == 404


def test_list_work_orders_filters(client: TestClient) -> None:
    by_customer = client.get(
        "/api/v1/work-orders", params={"customer_id": "cust_0001", "page_size": 100}
    )
    assert by_customer.status_code == 200
    payload = by_customer.json()
    assert payload["total"] >= 1
    assert all(item["customer_id"] == "cust_0001" for item in payload["items"])

    created = client.get("/api/v1/work-orders", params={"status": "created"})
    assert created.status_code == 200
    assert created.json()["total"] == 3

    assigned = client.get(
        "/api/v1/work-orders",
        params={"assigned_employee_id": "emp_0010", "page_size": 100},
    )
    assert assigned.status_code == 200
    assert assigned.json()["total"] >= 1

    by_location = client.get(
        "/api/v1/work-orders",
        params={"service_location_id": "loc_0004", "page_size": 100},
    )
    assert by_location.status_code == 200
    assert by_location.json()["total"] >= 1
    assert all(
        item["service_location_id"] == "loc_0004"
        for item in by_location.json()["items"]
    )


def test_get_work_order_detail(client: TestClient) -> None:
    response = client.get("/api/v1/work-orders/wo_0004")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "wo_0004"
    assert body["status"] == "scheduled"
    assert body["support_ticket_id"] == "tkt_0004"
    assert body["tasks"]
    assert body["appointments"]
    assert body["equipment"]
    assert all(task["id"].startswith("wot_") for task in body["tasks"])


def test_work_order_not_found_and_invalid_status(client: TestClient) -> None:
    missing = client.get("/api/v1/work-orders/wo_9999")
    assert missing.status_code == 404
    invalid = client.get("/api/v1/work-orders", params={"status": "nope"})
    assert invalid.status_code == 422
