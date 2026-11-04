from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_invoices_paginated(client: TestClient) -> None:
    response = client.get("/api/v1/invoices", params={"page": 1, "page_size": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 5
    assert body["total"] == 30
    assert [item["id"] for item in body["items"]] == [
        "inv_0001",
        "inv_0002",
        "inv_0003",
        "inv_0004",
        "inv_0005",
    ]


def test_filter_invoices_by_status(client: TestClient) -> None:
    drafts = client.get("/api/v1/invoices", params={"status": "draft"})
    assert drafts.status_code == 200
    assert drafts.json()["total"] >= 1
    assert all(item["status"] == "draft" for item in drafts.json()["items"])

    invalid = client.get("/api/v1/invoices", params={"status": "posted"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_parameter"


def test_get_invoice_detail(client: TestClient) -> None:
    response = client.get("/api/v1/invoices/inv_0001")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "inv_0001"
    assert body["customer_id"] == "cust_0015"
    assert body["status"] == "draft"
    assert "created_at" in body
    assert "updated_at" in body


def test_get_invoice_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/invoices/inv_9999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_invoices_require_laboratory_actor(
    client: TestClient, anonymous_client: TestClient
) -> None:
    assert client.get("/api/v1/invoices").status_code == 200
    assert anonymous_client.get("/api/v1/invoices").status_code == 401
