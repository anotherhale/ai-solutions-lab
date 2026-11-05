from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_invoice_lines_for_invoice(client: TestClient) -> None:
    response = client.get("/api/v1/invoices/inv_0001/lines")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 2
    assert all(item["invoice_id"] == "inv_0001" for item in body["items"])
    first = body["items"][0]
    assert first["unit_price"]["currency"] == "USD"
    assert first["line_total"]["currency"] == "USD"


def test_filter_invoice_lines_by_type(client: TestClient) -> None:
    response = client.get(
        "/api/v1/invoices/inv_0001/lines",
        params={"line_type": "labor"},
    )
    assert response.status_code == 200
    assert all(item["line_type"] == "labor" for item in response.json()["items"])

    invalid = client.get(
        "/api/v1/invoices/inv_0001/lines",
        params={"line_type": "posted"},
    )
    assert invalid.status_code == 422


def test_get_invoice_line_detail(client: TestClient) -> None:
    response = client.get("/api/v1/invoice-lines/il_0001")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "il_0001"
    assert body["invoice_id"] == "inv_0001"
    assert body["work_order_id"] == "wo_0020"


def test_invoice_lines_not_found(client: TestClient) -> None:
    assert client.get("/api/v1/invoices/inv_9999/lines").status_code == 404
    assert client.get("/api/v1/invoice-lines/il_9999").status_code == 404


def test_invoice_lines_require_laboratory_actor(
    client: TestClient, anonymous_client: TestClient
) -> None:
    assert client.get("/api/v1/invoices/inv_0001/lines").status_code == 200
    assert anonymous_client.get("/api/v1/invoices/inv_0001/lines").status_code == 401
