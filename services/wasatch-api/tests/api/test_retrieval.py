from __future__ import annotations

from fastapi.testclient import TestClient

ROOFTOP = "Please send a technician. Rooftop unit is down."


def test_ticket_retrieval_returns_that_customers_history_and_procedure(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/support-tickets/tkt_0015/retrieval")
    assert response.status_code == 200
    body = response.json()
    assert body["support_ticket_id"] == "tkt_0015"
    assert body["customer_id"] == "cust_0011"

    by_source: dict[str, list[str]] = {}
    texts: dict[tuple[str, str], str] = {}
    for passage in body["history"]:
        by_source.setdefault(passage["source"], []).append(passage["source_id"])
        texts[(passage["source"], passage["source_id"])] = passage["text"]

    assert by_source["support_ticket"] == ["tkt_0015"]
    assert by_source["message"] == ["msg_0015"]
    assert by_source["interaction"] == ["ixn_0015"]
    assert by_source["work_order"] == ["wo_0015", "wo_0035"]
    assert texts[("support_ticket", "tkt_0015")] == "Service request related to wo_0015"
    assert texts[("message", "msg_0015")] == ROOFTOP
    assert "Logged inbound request" in texts[("interaction", "ixn_0015")]
    assert "Inspection request 15" in texts[("work_order", "wo_0015")]
    assert "Filters replaced" in texts[("work_order", "wo_0035")]
    assert "tkt_0001" not in by_source["support_ticket"]
    assert ("work_order", "wo_0001") not in texts

    assert [page["id"] for page in body["procedures"]] == ["proc_0001"]
    procedure = body["procedures"][0]
    assert procedure["synthetic"] is True
    assert procedure["path"] == "rooftop-unit-down.txt"
    assert "rooftop" in procedure["text"].lower()
    assert procedure["text"].startswith(
        "Synthetic laboratory procedure for Wasatch Business Systems."
    )
    assert "boiler" not in procedure["text"].lower()


def test_retrieval_does_not_include_another_customers_history(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/support-tickets/tkt_0001/retrieval")
    assert response.status_code == 200
    body = response.json()
    assert body["customer_id"] == "cust_0001"
    source_ids = {item["source_id"] for item in body["history"]}
    assert {"tkt_0001", "tkt_0002", "msg_0001", "msg_0002"} <= source_ids
    assert "tkt_0015" not in source_ids
    assert "wo_0015" not in source_ids
    assert "wo_0035" not in source_ids
    assert [page["id"] for page in body["procedures"]] == ["proc_0001"]


def test_retrieval_unknown_ticket_is_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/support-tickets/tkt_9999/retrieval")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_retrieval_requires_laboratory_actor(anonymous_client: TestClient) -> None:
    response = anonymous_client.get("/api/v1/support-tickets/tkt_0015/retrieval")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_retrieval_route_is_read_only(client: TestClient) -> None:
    response = client.post("/api/v1/support-tickets/tkt_0015/retrieval")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
