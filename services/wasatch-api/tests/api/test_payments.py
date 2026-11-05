from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_payments_paginated(client: TestClient) -> None:
    response = client.get("/api/v1/payments", params={"page": 1, "page_size": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 20
    assert len(body["items"]) == 5
    assert body["items"][0]["amount"]["currency"] == "USD"


def test_filter_payments_by_invoice(client: TestClient) -> None:
    response = client.get("/api/v1/payments", params={"invoice_id": "inv_0011"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert all(item["invoice_id"] == "inv_0011" for item in body["items"])


def test_filter_payments_invalid_status(client: TestClient) -> None:
    response = client.get("/api/v1/payments", params={"status": "settled"})
    assert response.status_code == 422


def test_get_payment_detail(client: TestClient) -> None:
    response = client.get("/api/v1/payments/pay_0001")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "pay_0001"
    assert body["invoice_id"] == "inv_0011"
    assert body["method"] == "ach"


def test_get_payment_not_found(client: TestClient) -> None:
    assert client.get("/api/v1/payments/pay_9999").status_code == 404


def test_payments_require_laboratory_actor(
    client: TestClient, anonymous_client: TestClient
) -> None:
    assert client.get("/api/v1/payments").status_code == 200
    assert anonymous_client.get("/api/v1/payments").status_code == 401
