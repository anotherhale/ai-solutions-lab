"""Accept or reject a synthetic extraction without posting finance."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from wasatch_api.config import REPO_ROOT
from wasatch_api.shared.seed import seed_valid_fixtures
from wasatch_api.workforce.infrastructure.local_authenticator import (
    LABORATORY_ACTOR_HEADER,
)

DECISION = "/api/v1/document-extractions/{extraction_id}/decisions"
OPENAPI_DECISION = "/api/v1/document-extractions/{extraction_id}/decisions"
FIXTURES = REPO_ROOT / "data" / "fixtures" / "valid"
FINANCE_FILES = ("invoices.json", "invoice_lines.json", "payments.json")
INVOICE_DOCUMENTS = (
    "doc_0003",
    "doc_0005",
    "doc_0009",
    "doc_0010",
    "doc_0015",
    "doc_0020",
    "doc_0025",
    "doc_0030",
)


def _finance_bytes() -> dict[str, bytes]:
    return {name: (FIXTURES / name).read_bytes() for name in FINANCE_FILES}


def _finance_rows() -> tuple[list, list]:
    invoices = json.loads((FIXTURES / "invoices.json").read_text(encoding="utf-8"))
    payments = json.loads((FIXTURES / "payments.json").read_text(encoding="utf-8"))
    invoice_rows = [
        (row["id"], row["status"], row["total"], row["amount_paid"], row["balance"])
        for row in invoices["records"]
    ]
    payment_rows = [
        (row["id"], row["invoice_id"], row["status"], row["amount"])
        for row in payments["records"]
    ]
    return invoice_rows, payment_rows


def _document_finance(client: TestClient) -> dict[str, dict]:
    recorded = {}
    for document_id in INVOICE_DOCUMENTS:
        response = client.get(f"/api/v1/documents/{document_id}")
        assert response.status_code == 200
        body = response.json()
        recorded[document_id] = {
            "status": body["status"],
            "invoice_id": body["invoice_id"],
            "updated_at": body["updated_at"],
        }
    work_order = client.get("/api/v1/work-orders/wo_0003")
    assert work_order.status_code == 200
    recorded["wo_0003"] = {
        "status": work_order.json()["status"],
        "invoice_id": work_order.json()["invoice_id"],
    }
    return recorded


def _payment_count(db_session: Session) -> int:
    return int(db_session.execute(text("SELECT count(*) FROM payments")).scalar() or 0)


def test_approver_accepts_needs_review_without_posting(
    client: TestClient, decision_transaction: None, db_session: Session
) -> None:
    before = client.get("/api/v1/document-extractions/dx_0003")
    assert before.status_code == 200
    original = before.json()
    assert original["status"] == "needs_review"
    assert original["confidence"] == 0.7
    assert original["extracted_fields"]["invoice_number"] == "V-0003"
    assert original["reviewed_by_employee_id"] is None
    reread = client.get("/api/v1/document-extractions/dx_0003")
    assert reread.json() == original

    finance_bytes = _finance_bytes()
    finance_rows = _finance_rows()
    documents = _document_finance(client)
    payment_count = _payment_count(db_session)
    assert documents["doc_0003"]["invoice_id"] is None
    assert documents["doc_0003"]["status"] == "extracted"

    response = client.post(
        DECISION.format(extraction_id="dx_0003"),
        json={"decision": "accepted", "note": "Fields match the vendor bill."},
    )
    assert response.status_code == 200
    recorded = response.json()
    assert recorded["id"] == "dx_0003"
    assert recorded["status"] == "accepted"
    assert recorded["reviewed_by_employee_id"] == "emp_0001"
    assert recorded["reviewed_at"]
    assert recorded["review_notes"] == "Fields match the vendor bill."
    assert recorded["extracted_fields"] == original["extracted_fields"]
    assert recorded["confidence"] == original["confidence"]
    assert recorded["document_id"] == "doc_0003"
    assert recorded["updated_at"] == recorded["reviewed_at"]

    again = client.post(
        DECISION.format(extraction_id="dx_0003"),
        json={"decision": "rejected", "note": "second decision"},
    )
    assert again.status_code == 422
    assert again.json()["error"]["code"] == "invalid_parameter"
    still = client.get("/api/v1/document-extractions/dx_0003")
    assert still.json()["status"] == "accepted"
    assert still.json()["review_notes"] == "Fields match the vendor bill."

    document = client.get("/api/v1/documents/doc_0003")
    assert document.json()["status"] == "extracted"
    assert document.json()["invoice_id"] is None
    assert document.json()["updated_at"] == documents["doc_0003"]["updated_at"]
    assert _document_finance(client) == documents
    assert _finance_bytes() == finance_bytes
    assert _finance_rows() == finance_rows
    assert _payment_count(db_session) == payment_count

    audits = client.get("/api/v1/audit-events", params={"page_size": 100})
    assert audits.status_code == 200
    assert audits.json()["total"] == 51
    events = {item["id"]: item for item in audits.json()["items"]}
    review = events["aud_0051"]
    assert review["action"] == "document_extraction.reviewed"
    assert review["outcome"] == "succeeded"
    assert review["actor_type"] == "employee"
    assert review["actor_employee_id"] == "emp_0001"
    assert review["subject_type"] == "document_extraction"
    assert review["subject_id"] == "dx_0003"
    assert review["approval_request_id"] is None
    assert review["occurred_at"] == recorded["reviewed_at"]
    assert review["details"] == {"from_status": "needs_review", "to_status": "accepted"}
    assert "V-0003" not in str(review)
    assert "updated_at" not in review
    held = client.get("/api/v1/document-extractions", params={"status": "needs_review"})
    assert held.json()["total"] == 2
    assert [item["id"] for item in held.json()["items"]] == ["dx_0009", "dx_0015"]


def test_approver_rejects_needs_review_and_does_not_post(
    client: TestClient, decision_transaction: None
) -> None:
    finance_bytes = _finance_bytes()
    finance_rows = _finance_rows()
    documents = _document_finance(client)
    response = client.post(
        DECISION.format(extraction_id="dx_0009"),
        json={"decision": "rejected", "note": "Amounts did not match."},
    )
    assert response.status_code == 200
    recorded = response.json()
    assert recorded["status"] == "rejected"
    assert recorded["status"] != "posted"
    assert recorded["reviewed_by_employee_id"] == "emp_0001"
    assert recorded["review_notes"] == "Amounts did not match."
    assert recorded["extracted_fields"]["invoice_number"] == "V-0009"
    document = client.get("/api/v1/documents/doc_0009")
    assert document.json()["status"] == documents["doc_0009"]["status"]
    assert document.json()["invoice_id"] is None
    assert _document_finance(client) == documents
    assert _finance_bytes() == finance_bytes
    invoice_rows, payment_rows = _finance_rows()
    assert (invoice_rows, payment_rows) == finance_rows
    posted_before = [row for row in finance_rows[1] if row[2] == "posted"]
    posted_after = [row for row in payment_rows if row[2] == "posted"]
    assert posted_after == posted_before


def test_non_approver_cannot_review_an_extraction(
    anonymous_client: TestClient, decision_transaction: None
) -> None:
    headers = {LABORATORY_ACTOR_HEADER: "emp_0004"}
    before = anonymous_client.get(
        "/api/v1/document-extractions/dx_0015", headers=headers
    )
    assert before.status_code == 200
    original = before.json()
    assert original["status"] == "needs_review"
    denied = anonymous_client.post(
        DECISION.format(extraction_id="dx_0015"),
        headers=headers,
        json={"decision": "accepted", "note": "dispatcher override"},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "forbidden"
    assert denied.json()["error"]["message"] == "writes are denied"
    current = anonymous_client.get(
        "/api/v1/document-extractions/dx_0015", headers=headers
    )
    assert current.json() == original
    audits = anonymous_client.get(
        "/api/v1/audit-events", headers=headers, params={"page_size": 100}
    )
    assert audits.json()["total"] == 50


def test_anonymous_extraction_decision_is_unauthorized(
    anonymous_client: TestClient,
) -> None:
    response = anonymous_client.post(
        DECISION.format(extraction_id="dx_0003"),
        json={"decision": "accepted", "note": "anonymous"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"
    blank = anonymous_client.post(
        DECISION.format(extraction_id="dx_0003"),
        headers={LABORATORY_ACTOR_HEADER: "  "},
        json={"decision": "rejected"},
    )
    assert blank.status_code == 401


def test_read_and_seed_leave_financial_extractions_unaccepted(
    client: TestClient, db_session: Session
) -> None:
    low_confidence = client.get("/api/v1/document-extractions/dx_0002")
    assert low_confidence.status_code == 200
    assert low_confidence.json()["status"] == "succeeded"
    assert low_confidence.json()["confidence"] == 0.6
    assert "invoice_number" in low_confidence.json()["extracted_fields"]
    again = client.get("/api/v1/document-extractions/dx_0002")
    assert again.json() == low_confidence.json()

    linked = client.get("/api/v1/documents/doc_0015")
    assert linked.json()["invoice_id"] == "inv_0015"
    extraction = client.get("/api/v1/document-extractions/dx_0015")
    assert extraction.json()["status"] == "needs_review"
    assert extraction.json()["confidence"] == 0.7
    assert extraction.json()["reviewed_by_employee_id"] is None

    before = dict(
        db_session.execute(
            text(
                """
                SELECT business_id, status
                FROM document_extractions
                ORDER BY business_id
                """
            )
        ).all()
    )
    seed_valid_fixtures(db_session, FIXTURES)
    db_session.expire_all()
    after = dict(
        db_session.execute(
            text(
                """
                SELECT business_id, status
                FROM document_extractions
                ORDER BY business_id
                """
            )
        ).all()
    )
    assert after == before
    assert before["dx_0003"] == "needs_review"
    assert before["dx_0009"] == "needs_review"
    assert before["dx_0015"] == "needs_review"
    assert before["dx_0002"] == "succeeded"
    accepted = sorted(key for key, status in before.items() if status == "accepted")
    assert accepted == ["dx_0004", "dx_0010", "dx_0016"]


def test_other_extraction_writes_stay_denied_and_openapi_lists_the_decision(
    client: TestClient,
) -> None:
    for method in ("post", "put", "patch", "delete"):
        response = getattr(client, method)("/api/v1/document-extractions/dx_0003")
        assert response.status_code == 403
        assert response.json()["error"]["message"] == "writes are denied"
    for method in ("put", "patch", "delete"):
        response = getattr(client, method)(DECISION.format(extraction_id="dx_0003"))
        assert response.status_code == 403
    missing = client.post(
        DECISION.format(extraction_id="dx_9999"),
        json={"decision": "rejected"},
    )
    assert missing.status_code == 404
    spec = client.get("/openapi.json").json()
    assert set(spec["paths"][OPENAPI_DECISION]) == {"post"}
