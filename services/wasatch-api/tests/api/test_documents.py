from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_documents_paginated(client: TestClient) -> None:
    response = client.get("/api/v1/documents", params={"page": 1, "page_size": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 5
    assert body["total"] == 30
    assert [item["id"] for item in body["items"]] == [
        "doc_0001",
        "doc_0002",
        "doc_0003",
        "doc_0004",
        "doc_0005",
    ]
    assert "versions" not in body["items"][0]
    assert body["items"][0]["current_version_id"] == "dv_0001"


def test_filter_documents(client: TestClient) -> None:
    needs_review = client.get("/api/v1/documents", params={"status": "needs_review"})
    assert needs_review.status_code == 200
    assert needs_review.json()["total"] == 5
    assert needs_review.json()["items"][0]["id"] == "doc_0004"

    contracts = client.get("/api/v1/documents", params={"document_type": "contract"})
    assert contracts.status_code == 200
    assert contracts.json()["total"] == 5
    assert contracts.json()["items"][0]["id"] == "doc_0003"

    generated = client.get(
        "/api/v1/documents",
        params={"source": "generated", "customer_id": "cust_0003"},
    )
    assert generated.status_code == 200
    assert generated.json()["total"] >= 1
    assert all(item["customer_id"] == "cust_0003" for item in generated.json()["items"])
    assert all(item["source"] == "generated" for item in generated.json()["items"])

    invalid = client.get("/api/v1/documents", params={"status": "posted"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_parameter"

    bad_type = client.get("/api/v1/documents", params={"document_type": "photo"})
    assert bad_type.status_code == 422
    assert bad_type.json()["error"]["code"] == "invalid_parameter"


def test_get_document_includes_versions_and_extractions(client: TestClient) -> None:
    response = client.get("/api/v1/documents/doc_0004")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "doc_0004"
    assert body["document_type"] == "vendor_bill"
    assert body["status"] == "needs_review"
    assert body["source"] == "generated"
    assert body["untrusted"] is False
    assert body["customer_id"] == "cust_0003"
    assert body["service_location_id"] == "loc_0004"
    assert body["work_order_id"] is None
    assert body["current_version_id"] == "dv_0031"
    assert body["uploaded_by_employee_id"] == "emp_0007"
    assert [item["id"] for item in body["versions"]] == ["dv_0004", "dv_0031"]
    assert body["versions"][1]["version_number"] == 2
    assert body["versions"][1]["storage_path"] == "synthetic/documents/doc_0004/v2.bin"
    assert body["versions"][1]["created_by_employee_id"] == "emp_0009"
    assert len(body["versions"][1]["checksum_sha256"]) == 64
    extraction = body["extractions"][0]
    assert extraction["id"] == "dx_0004"
    assert extraction["document_version_id"] == "dv_0004"
    assert extraction["status"] == "accepted"
    assert extraction["extractor"] == "model"
    assert extraction["confidence"] == 0.8
    assert extraction["reviewed_by_employee_id"] == "emp_0008"
    assert extraction["extracted_fields"]["invoice_number"] == "V-0004"

    linked = client.get("/api/v1/documents/doc_0003")
    assert linked.status_code == 200
    assert linked.json()["work_order_id"] == "wo_0003"

    invoiced = client.get("/api/v1/documents/doc_0005")
    assert invoiced.status_code == 200
    assert invoiced.json()["invoice_id"] == "inv_0005"


def test_document_not_found(client: TestClient) -> None:
    missing = client.get("/api/v1/documents/doc_9999")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"
    version = client.get("/api/v1/document-versions/dv_9999")
    assert version.status_code == 404
    assert version.json()["error"]["code"] == "not_found"
    extraction = client.get("/api/v1/document-extractions/dx_9999")
    assert extraction.status_code == 404
    assert extraction.json()["error"]["code"] == "not_found"


def test_list_versions_and_extractions(client: TestClient) -> None:
    versions = client.get(
        "/api/v1/document-versions",
        params={"document_id": "doc_0004", "page_size": 10},
    )
    assert versions.status_code == 200
    assert versions.json()["total"] == 2
    assert [item["id"] for item in versions.json()["items"]] == ["dv_0004", "dv_0031"]

    one = client.get("/api/v1/document-versions/dv_0031")
    assert one.status_code == 200
    assert one.json()["document_id"] == "doc_0004"
    assert one.json()["version_number"] == 2

    all_versions = client.get("/api/v1/document-versions", params={"page_size": 5})
    assert all_versions.status_code == 200
    assert all_versions.json()["total"] == 31

    extractions = client.get(
        "/api/v1/document-extractions", params={"status": "needs_review"}
    )
    assert extractions.status_code == 200
    assert extractions.json()["total"] == 3
    assert extractions.json()["items"][0]["id"] == "dx_0003"

    rules = client.get("/api/v1/document-extractions", params={"extractor": "rules"})
    assert rules.status_code == 200
    assert rules.json()["total"] == 3

    held = client.get("/api/v1/document-extractions/dx_0003")
    assert held.status_code == 200
    assert held.json()["status"] == "needs_review"
    assert held.json()["review_notes"] == "Low confidence; hold for AP."
    assert held.json()["reviewed_by_employee_id"] is None

    invalid = client.get("/api/v1/document-extractions", params={"extractor": "llm"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_parameter"

    counted = client.get("/api/v1/document-extractions", params={"page_size": 5})
    assert counted.status_code == 200
    assert counted.json()["total"] == 18


def test_document_routes_stay_read_only(
    client: TestClient, anonymous_client: TestClient
) -> None:
    anonymous = anonymous_client.get("/api/v1/documents/doc_0001")
    assert anonymous.status_code == 401
    assert anonymous.json()["error"]["code"] == "unauthenticated"

    for method in ("post", "put", "patch", "delete"):
        response = getattr(client, method)("/api/v1/documents/doc_0001")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "forbidden"
        assert response.json()["error"]["message"] == "writes are denied"

    spec = client.get("/openapi.json").json()
    read_paths = {
        "/api/v1/documents",
        "/api/v1/documents/{document_id}",
        "/api/v1/document-versions",
        "/api/v1/document-versions/{version_id}",
        "/api/v1/document-extractions",
        "/api/v1/document-extractions/{extraction_id}",
    }
    assert read_paths <= set(spec["paths"])
    for path in read_paths:
        assert set(spec["paths"][path]) <= {"get", "head"}
    current = client.get("/api/v1/documents/doc_0004")
    assert current.status_code == 200
    assert current.json()["status"] == "needs_review"
