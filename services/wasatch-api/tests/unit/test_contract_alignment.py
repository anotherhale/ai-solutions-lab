from __future__ import annotations

import json
from pathlib import Path

from wasatch_api.documents.application.decisions import EXTRACTION_REVIEW_DECISIONS
from wasatch_api.governance.application.decisions import CUSTOMER_MESSAGE_DECISIONS
from wasatch_api.shared.pagination import (
    APPROVAL_ACTION_TYPES,
    APPROVAL_STATUSES,
    AUDIT_OUTCOMES,
    CUSTOMER_STATUSES,
    DOCUMENT_SOURCES,
    DOCUMENT_STATUSES,
    DOCUMENT_TYPES,
    EXTRACTION_STATUSES,
    EXTRACTORS,
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
    approval = _schema("governance/approval-request.schema.json")
    audit = _schema("governance/audit-event.schema.json")
    document = _schema("documents/document.schema.json")
    extraction = _schema("documents/document-extraction.schema.json")
    assert CUSTOMER_STATUSES == frozenset(customer["properties"]["status"]["enum"])
    assert WORK_ORDER_STATUSES == frozenset(work_order["properties"]["status"]["enum"])
    assert SUPPORT_TICKET_STATUSES == frozenset(ticket["properties"]["status"]["enum"])
    assert MESSAGE_STATUSES == frozenset(message["properties"]["status"]["enum"])
    assert APPROVAL_STATUSES == frozenset(approval["properties"]["status"]["enum"])
    assert APPROVAL_ACTION_TYPES == frozenset(
        approval["properties"]["action_type"]["enum"]
    )
    assert AUDIT_OUTCOMES == frozenset(audit["properties"]["outcome"]["enum"])
    assert DOCUMENT_STATUSES == frozenset(document["properties"]["status"]["enum"])
    assert DOCUMENT_TYPES == frozenset(document["properties"]["document_type"]["enum"])
    assert DOCUMENT_SOURCES == frozenset(document["properties"]["source"]["enum"])
    assert EXTRACTION_STATUSES == frozenset(extraction["properties"]["status"]["enum"])
    assert EXTRACTORS == frozenset(extraction["properties"]["extractor"]["enum"])
    assert CUSTOMER_MESSAGE_DECISIONS == frozenset({"approved", "rejected"})
    assert CUSTOMER_MESSAGE_DECISIONS < APPROVAL_STATUSES
    assert "executed" not in CUSTOMER_MESSAGE_DECISIONS
    assert "sent" not in CUSTOMER_MESSAGE_DECISIONS
    assert EXTRACTION_REVIEW_DECISIONS == frozenset({"accepted", "rejected"})
    assert EXTRACTION_REVIEW_DECISIONS <= EXTRACTION_STATUSES
    assert "posted" not in EXTRACTION_REVIEW_DECISIONS
