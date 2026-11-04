"""Read-only synthetic invoices, lines, and payments."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session


def _snapshot(db_session: Session) -> tuple[list[tuple], list[tuple]]:
    invoices = db_session.execute(
        text(
            """
            SELECT business_id, status, total_amount, amount_paid_amount, balance_amount
            FROM invoices
            ORDER BY business_id
            """
        )
    ).all()
    payments = db_session.execute(
        text(
            """
            SELECT payments.business_id, invoices.business_id,
                   payments.status, payments.amount_amount
            FROM payments
            JOIN invoices ON invoices.id = payments.invoice_id
            ORDER BY payments.business_id
            """
        )
    ).all()
    invoice_rows = [
        (row[0], row[1], str(row[2]), str(row[3]), str(row[4])) for row in invoices
    ]
    payment_rows = [(row[0], row[1], row[2], str(row[3])) for row in payments]
    return invoice_rows, payment_rows


def test_list_and_read_invoice_without_posting(
    client: TestClient, anonymous_client: TestClient, db_session: Session
) -> None:
    before = _snapshot(db_session)
    assert len(before[0]) == 30
    assert len(before[1]) == 20

    denied = anonymous_client.get("/api/v1/invoices/inv_0005")
    assert denied.status_code == 401

    listed = client.get("/api/v1/invoices", params={"page": 1, "page_size": 5})
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 30
    assert [item["id"] for item in body["items"]] == [
        "inv_0001",
        "inv_0002",
        "inv_0003",
        "inv_0004",
        "inv_0005",
    ]
    assert "lines" not in body["items"][0]
    assert "payments" not in body["items"][0]

    issued = client.get(
        "/api/v1/invoices",
        params={"status": "issued", "customer_id": "cust_0005", "page_size": 100},
    )
    assert issued.status_code == 200
    assert [item["id"] for item in issued.json()["items"]] == ["inv_0005"]

    unknown = client.get("/api/v1/invoices", params={"status": "sent"})
    assert unknown.status_code == 422

    missing = client.get("/api/v1/invoices/inv_9999")
    assert missing.status_code == 404

    detail = client.get("/api/v1/invoices/inv_0005")
    assert detail.status_code == 200
    invoice = detail.json()
    assert invoice["customer_id"] == "cust_0005"
    assert invoice["work_order_id"] == "wo_0028"
    assert invoice["status"] == "issued"
    assert invoice["total"] == {"amount": "360.90", "currency": "USD"}
    assert invoice["amount_paid"] == {"amount": "0.00", "currency": "USD"}
    assert invoice["balance"] == {"amount": "360.90", "currency": "USD"}
    assert invoice["issued_on"] == "2026-10-20"
    assert invoice["due_on"] == "2026-11-20"
    assert [line["id"] for line in invoice["lines"]] == ["il_0007", "il_0008"]
    assert invoice["lines"][0]["quantity"] == 2
    assert invoice["lines"][0]["line_type"] == "labor"
    assert invoice["lines"][0]["work_order_id"] == "wo_0028"
    assert invoice["payments"] == []

    work_order = client.get("/api/v1/work-orders/wo_0028")
    assert work_order.status_code == 200
    assert work_order.json()["invoice_id"] == "inv_0005"

    lines = client.get(
        "/api/v1/invoice-lines",
        params={"invoice_id": "inv_0005", "line_type": "labor"},
    )
    assert lines.status_code == 200
    assert lines.json()["total"] == 1
    assert lines.json()["items"][0]["id"] == "il_0007"

    line = client.get("/api/v1/invoice-lines/il_0008")
    assert line.status_code == 200
    assert line.json()["unit_price"] == {"amount": "86.50", "currency": "USD"}
    assert line.json()["line_total"] == {"amount": "86.50", "currency": "USD"}

    voided = client.get("/api/v1/invoices/inv_0029")
    assert voided.status_code == 200
    assert voided.json()["status"] == "voided"
    assert voided.json()["void_reason"] == "Duplicate draft issued in error"
    assert voided.json()["voided_on"] == "2026-06-20"

    payments = client.get(
        "/api/v1/payments",
        params={"status": "posted", "invoice_id": "inv_0011", "page_size": 100},
    )
    assert payments.status_code == 200
    assert payments.json()["total"] == 1
    payment = payments.json()["items"][0]
    assert payment["id"] == "pay_0001"
    assert payment["amount"] == {"amount": "360.90", "currency": "USD"}
    assert payment["method"] == "ach"
    assert payment["received_by_employee_id"] == "emp_0009"
    assert payment["received_on"] == "2026-08-20"

    one = client.get("/api/v1/payments/pay_0001")
    assert one.status_code == 200
    assert one.json()["invoice_id"] == "inv_0011"
    assert one.json()["status"] == "posted"

    blocked = client.post("/api/v1/invoices", json={"status": "paid"})
    assert blocked.status_code == 403
    assert blocked.json()["error"]["message"] == "writes are denied"
    pay_blocked = client.post(
        "/api/v1/payments",
        json={"invoice_id": "inv_0005", "status": "posted"},
    )
    assert pay_blocked.status_code == 403
    assert _snapshot(db_session) == before
