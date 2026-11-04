from __future__ import annotations

import json
from pathlib import Path

from wasatch_api.shared.pagination import (
    CUSTOMER_STATUSES,
    MESSAGE_STATUSES,
    SUPPORT_TICKET_STATUSES,
    WORK_ORDER_STATUSES,
)

ROOT = Path(__file__).resolve().parents[4]


def _schema(relative: str) -> dict:
    return json.loads((ROOT / "data" / "schemas" / "v1" / relative).read_text())


def test_api_status_filters_match_json_schema() -> None:
    customer = _schema("customers/customer.schema.json")
    work_order = _schema("field-operations/work-order.schema.json")
    ticket = _schema("customer-service/support-ticket.schema.json")
    message = _schema("customer-service/message.schema.json")
    assert CUSTOMER_STATUSES == frozenset(customer["properties"]["status"]["enum"])
    assert WORK_ORDER_STATUSES == frozenset(work_order["properties"]["status"]["enum"])
    assert SUPPORT_TICKET_STATUSES == frozenset(ticket["properties"]["status"]["enum"])
    assert MESSAGE_STATUSES == frozenset(message["properties"]["status"]["enum"])
