"""Follow-up visit after an approved customer message. Synthetic data only."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from wasatch_api.config import REPO_ROOT
from wasatch_api.workforce.infrastructure.local_authenticator import (
    LABORATORY_ACTOR_HEADER,
)

MESSAGE_BODY = "We can be on site Thursday at 08:00 if you approve overtime."
APPROVAL = "/api/v1/approval-requests/apr_0001/decisions"
FOLLOW_UP = "/api/v1/approval-requests/apr_0001/follow-up-visits"
OPENAPI_FOLLOW_UP = "/api/v1/approval-requests/{approval_id}/follow-up-visits"
FIXTURES = REPO_ROOT / "data" / "fixtures" / "valid"
FINANCE_FILES = ("invoices.json", "invoice_lines.json", "payments.json")
DISPATCHER = {LABORATORY_ACTOR_HEADER: "emp_0004"}


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


def _payment_count(db_session: Session) -> int:
    return int(db_session.execute(text("SELECT count(*) FROM payments")).scalar() or 0)


def _message_without_approval(payload: dict) -> dict:
    recorded = dict(payload)
    recorded.pop("approval_request", None)
    return recorded


def _work_orders(client: TestClient) -> list[dict]:
    response = client.get("/api/v1/work-orders", params={"page_size": 100})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 40
    return [
        {
            "id": item["id"],
            "status": item["status"],
            "assigned_employee_ids": item["assigned_employee_ids"],
        }
        for item in body["items"]
    ]


def _field_detail(client: TestClient) -> dict:
    work_order = client.get("/api/v1/work-orders/wo_0007")
    ticket = client.get("/api/v1/support-tickets/tkt_0007")
    assert work_order.status_code == 200
    assert ticket.status_code == 200
    order = work_order.json()
    return {
        "work_order": {
            "status": order["status"],
            "invoice_id": order["invoice_id"],
            "scheduled_for": order["scheduled_for"],
            "updated_at": order["updated_at"],
            "assigned_employees": order["assigned_employees"],
            "appointments": order["appointments"],
        },
        "ticket": {
            "status": ticket.json()["status"],
            "work_order_id": ticket.json()["work_order_id"],
            "assigned_employee_id": ticket.json()["assigned_employee_id"],
            "updated_at": ticket.json()["updated_at"],
        },
    }


def _post(client: TestClient, path: str, payload: dict, headers: dict | None = None):
    if headers is None:
        return client.post(path, json=payload)
    return client.post(path, json=payload, headers=headers)


def test_dispatcher_confirms_only_after_approval_and_leaves_the_message_unsent(
    client: TestClient,
    anonymous_client: TestClient,
    decision_transaction: None,
    db_session: Session,
) -> None:
    before = client.get("/api/v1/messages/msg_0016")
    assert before.status_code == 200
    original = before.json()
    assert original["body"] == MESSAGE_BODY
    assert original["status"] == "pending_approval"
    finance_bytes = _finance_bytes()
    finance_rows = _finance_rows()
    payment_count_before = _payment_count(db_session)
    work_orders = _work_orders(client)
    field = _field_detail(client)
    assert anonymous_client.get(FOLLOW_UP, headers=DISPATCHER).status_code == 404

    opened_early = _post(anonymous_client, FOLLOW_UP, {"decision": "open"}, DISPATCHER)
    assert opened_early.status_code == 422
    assert opened_early.json()["error"]["code"] == "invalid_parameter"
    confirmed_early = _post(
        anonymous_client, FOLLOW_UP, {"decision": "confirm"}, DISPATCHER
    )
    assert confirmed_early.status_code == 422
    assert anonymous_client.get(FOLLOW_UP, headers=DISPATCHER).status_code == 404
    audits = client.get("/api/v1/audit-events", params={"page_size": 100})
    assert audits.json()["total"] == 50

    approved = client.post(
        APPROVAL,
        json={"decision": "approved", "note": "Overtime approved for Thursday."},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["executed_at"] is None
    assert approved.json()["reviewer_employee_id"] == "emp_0001"
    message = client.get("/api/v1/messages/msg_0016")
    assert message.json()["status"] == "pending_approval"
    assert message.json()["status"] != "sent"
    assert message.json()["body"] == MESSAGE_BODY
    assert _message_without_approval(message.json()) == _message_without_approval(
        original
    )
    assert anonymous_client.get(FOLLOW_UP, headers=DISPATCHER).status_code == 404
    assert _work_orders(client) == work_orders
    assert _field_detail(client) == field
    still_early = _post(
        anonymous_client, FOLLOW_UP, {"decision": "confirm"}, DISPATCHER
    )
    assert still_early.status_code == 422
    assert anonymous_client.get(FOLLOW_UP, headers=DISPATCHER).status_code == 404

    opened = _post(
        anonymous_client,
        FOLLOW_UP,
        {"decision": "open", "note": "not stored on open"},
        DISPATCHER,
    )
    assert opened.status_code == 200
    visit = opened.json()
    assert visit["id"] == "fuv_0001"
    assert visit["approval_request_id"] == "apr_0001"
    assert visit["message_id"] == "msg_0016"
    assert visit["support_ticket_id"] == "tkt_0007"
    assert visit["status"] == "unscheduled"
    assert visit["opened_by_employee_id"] == "emp_0004"
    assert visit["decided_by_employee_id"] is None
    assert visit["decided_at"] is None
    assert visit["note"] is None
    assert "assigned_employee_id" not in visit
    assert "scheduled_for" not in visit
    assert client.get(FOLLOW_UP).json() == visit
    assert client.get("/api/v1/follow-up-visits/fuv_0001").json() == visit
    assert _work_orders(client) == work_orders
    assert _field_detail(client) == field
    again = _post(anonymous_client, FOLLOW_UP, {"decision": "open"}, DISPATCHER)
    assert again.status_code == 422
    assert client.get(FOLLOW_UP).json()["status"] == "unscheduled"

    confirmed = _post(
        anonymous_client,
        FOLLOW_UP,
        {"decision": "confirm", "note": "Dispatcher confirmed the follow-up."},
        DISPATCHER,
    )
    assert confirmed.status_code == 200
    decided = confirmed.json()
    assert decided["status"] == "confirmed"
    assert decided["opened_by_employee_id"] == "emp_0004"
    assert decided["decided_by_employee_id"] == "emp_0004"
    assert decided["decided_at"]
    assert decided["note"] == "Dispatcher confirmed the follow-up."
    assert decided["opened_at"] == visit["opened_at"]
    assert "assigned_employee_id" not in decided
    assert "scheduled_for" not in decided
    repeat = _post(anonymous_client, FOLLOW_UP, {"decision": "confirm"}, DISPATCHER)
    assert repeat.status_code == 422
    assert client.get(FOLLOW_UP).json()["status"] == "confirmed"

    message = client.get("/api/v1/messages/msg_0016")
    assert message.json()["status"] == "pending_approval"
    assert message.json()["body"] == MESSAGE_BODY
    assert _message_without_approval(message.json()) == _message_without_approval(
        original
    )
    approval = client.get("/api/v1/approval-requests/apr_0001")
    assert approval.json()["status"] == "approved"
    assert approval.json()["executed_at"] is None
    assert len(approval.json()["decision_history"]) == 1
    assert _work_orders(client) == work_orders
    assert _field_detail(client) == field
    assert _finance_bytes() == finance_bytes
    assert _finance_rows() == finance_rows
    assert _payment_count(db_session) == payment_count_before

    linked = client.get(
        "/api/v1/audit-events",
        params={"approval_request_id": "apr_0001", "page_size": 100},
    )
    assert linked.json()["total"] == 4
    events = {item["id"]: item for item in linked.json()["items"]}
    assert events["aud_0052"]["action"] == "follow_up_visit.opened"
    assert events["aud_0052"]["actor_employee_id"] == "emp_0004"
    assert events["aud_0052"]["subject_type"] == "follow_up_visit"
    assert events["aud_0052"]["subject_id"] == "fuv_0001"
    assert events["aud_0052"]["outcome"] == "succeeded"
    assert events["aud_0052"]["approval_request_id"] == "apr_0001"
    assert events["aud_0052"]["details"] == {"to_status": "unscheduled"}
    assert events["aud_0053"]["action"] == "follow_up_visit.confirmed"
    assert events["aud_0053"]["details"] == {
        "from_status": "unscheduled",
        "to_status": "confirmed",
    }
    assert events["aud_0051"]["action"] == "approval.decided"
    assert MESSAGE_BODY not in str(linked.json())
    assert (
        client.get("/api/v1/audit-events", params={"page_size": 100}).json()["total"]
        == 53
    )


def test_dispatcher_can_cancel_the_unscheduled_follow_up(
    client: TestClient,
    anonymous_client: TestClient,
    decision_transaction: None,
    db_session: Session,
) -> None:
    finance_bytes = _finance_bytes()
    finance_rows = _finance_rows()
    work_orders = _work_orders(client)
    field = _field_detail(client)
    approved = client.post(APPROVAL, json={"decision": "approved"})
    assert approved.status_code == 200
    assert approved.json()["executed_at"] is None
    opened = _post(anonymous_client, FOLLOW_UP, {"decision": "open"}, DISPATCHER)
    assert opened.status_code == 200
    assert opened.json()["status"] == "unscheduled"
    cancelled = _post(
        anonymous_client,
        FOLLOW_UP,
        {"decision": "cancel", "note": "Customer will call back."},
        DISPATCHER,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["decided_by_employee_id"] == "emp_0004"
    assert cancelled.json()["note"] == "Customer will call back."
    assert "scheduled_for" not in cancelled.json()
    message = client.get("/api/v1/messages/msg_0016")
    assert message.json()["status"] == "pending_approval"
    assert message.json()["body"] == MESSAGE_BODY
    approval = client.get("/api/v1/approval-requests/apr_0001")
    assert approval.json()["status"] == "approved"
    assert approval.json()["executed_at"] is None
    assert _work_orders(client) == work_orders
    assert _field_detail(client) == field
    assert _finance_bytes() == finance_bytes
    assert _finance_rows() == finance_rows
    payment_count_before = _payment_count(db_session)
    assert _payment_count(db_session) == payment_count_before
    linked = client.get(
        "/api/v1/audit-events",
        params={"approval_request_id": "apr_0001", "page_size": 100},
    )
    actions = [item["action"] for item in linked.json()["items"]]
    assert "follow_up_visit.cancelled" in actions
    assert MESSAGE_BODY not in str(linked.json())


@pytest.mark.parametrize("employee_id", ["emp_0001", "emp_0006"])
def test_non_dispatcher_cannot_open_or_confirm(
    client: TestClient,
    anonymous_client: TestClient,
    decision_transaction: None,
    employee_id: str,
) -> None:
    headers = {LABORATORY_ACTOR_HEADER: employee_id}
    denied = anonymous_client.post(
        FOLLOW_UP, headers=headers, json={"decision": "open"}
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "forbidden"
    assert denied.json()["error"]["message"] == "writes are denied"
    approved = client.post(APPROVAL, json={"decision": "approved"})
    assert approved.status_code == 200
    opened = anonymous_client.post(
        FOLLOW_UP, headers=DISPATCHER, json={"decision": "open"}
    )
    assert opened.status_code == 200
    assert opened.json()["status"] == "unscheduled"
    confirm = anonymous_client.post(
        FOLLOW_UP, headers=headers, json={"decision": "confirm"}
    )
    assert confirm.status_code == 403
    assert confirm.json()["error"]["message"] == "writes are denied"
    cancel = anonymous_client.post(
        FOLLOW_UP, headers=headers, json={"decision": "cancel"}
    )
    assert cancel.status_code == 403
    current = client.get(FOLLOW_UP)
    assert current.json()["status"] == "unscheduled"
    assert current.json()["decided_at"] is None
    message = client.get("/api/v1/messages/msg_0016")
    assert message.json()["status"] == "pending_approval"


def test_anonymous_follow_up_command_is_unauthorized(
    anonymous_client: TestClient,
) -> None:
    response = anonymous_client.post(FOLLOW_UP, json={"decision": "confirm"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"
    blank = anonymous_client.post(
        FOLLOW_UP,
        headers={LABORATORY_ACTOR_HEADER: "  "},
        json={"decision": "open"},
    )
    assert blank.status_code == 401
    read = anonymous_client.get(FOLLOW_UP)
    assert read.status_code == 401


def test_other_approvals_do_not_open_a_follow_up(
    client: TestClient,
    anonymous_client: TestClient,
    decision_transaction: None,
) -> None:
    price = anonymous_client.post(
        "/api/v1/approval-requests/apr_0003/follow-up-visits",
        headers=DISPATCHER,
        json={"decision": "open"},
    )
    assert price.status_code == 422
    missing = anonymous_client.get(
        "/api/v1/approval-requests/apr_0003/follow-up-visits",
        headers=DISPATCHER,
    )
    assert missing.status_code == 404
    rejected = client.post(APPROVAL, json={"decision": "rejected"})
    assert rejected.status_code == 200
    opened = anonymous_client.post(
        FOLLOW_UP, headers=DISPATCHER, json={"decision": "open"}
    )
    assert opened.status_code == 422
    assert (
        client.get("/api/v1/messages/msg_0016").json()["status"] == "pending_approval"
    )
    assert (
        client.get("/api/v1/audit-events", params={"page_size": 100}).json()["total"]
        == 51
    )


def test_other_follow_up_writes_stay_denied(
    client: TestClient, anonymous_client: TestClient
) -> None:
    for method in ("put", "patch", "delete"):
        response = getattr(client, method)(FOLLOW_UP)
        assert response.status_code == 403
        assert response.json()["error"]["message"] == "writes are denied"
        dispatched = getattr(anonymous_client, method)(FOLLOW_UP, headers=DISPATCHER)
        assert dispatched.status_code == 403
    created = client.post("/api/v1/follow-up-visits", json={"decision": "confirm"})
    assert created.status_code == 403
    spec = client.get("/openapi.json").json()
    assert set(spec["paths"][OPENAPI_FOLLOW_UP]) == {"get", "post"}
    assert set(spec["paths"]["/api/v1/follow-up-visits/{follow_up_id}"]) == {"get"}
