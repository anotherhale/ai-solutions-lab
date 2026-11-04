from __future__ import annotations

import pytest

from wasatch_api.shared.errors import InvalidParameterError
from wasatch_api.shared.pagination import (
    escape_like,
    parse_page,
    validate_approval_action_type,
    validate_approval_status,
    validate_audit_outcome,
    validate_customer_status,
    validate_message_status,
    validate_support_ticket_status,
    validate_work_order_status,
)


def test_parse_page_defaults() -> None:
    request = parse_page(None, None)
    assert request.page == 1
    assert request.page_size == 20
    assert request.offset == 0


def test_parse_page_offset() -> None:
    request = parse_page(3, 10)
    assert request.offset == 20


def test_parse_page_rejects_invalid_values() -> None:
    with pytest.raises(InvalidParameterError):
        parse_page(0, 20)
    with pytest.raises(InvalidParameterError):
        parse_page(1, 0)
    with pytest.raises(InvalidParameterError):
        parse_page(1, 101)


def test_status_filters() -> None:
    assert validate_customer_status("active") == "active"
    assert validate_work_order_status("awaiting_parts") == "awaiting_parts"
    assert validate_support_ticket_status("awaiting_customer") == "awaiting_customer"
    assert validate_message_status("pending_approval") == "pending_approval"
    assert validate_approval_status("pending") == "pending"
    assert validate_approval_action_type("send_customer_message") == (
        "send_customer_message"
    )
    assert validate_audit_outcome("pending") == "pending"
    assert validate_support_ticket_status(None) is None
    assert validate_approval_status(None) is None
    with pytest.raises(InvalidParameterError):
        validate_customer_status("unknown")
    with pytest.raises(InvalidParameterError):
        validate_work_order_status("done")
    with pytest.raises(InvalidParameterError):
        validate_support_ticket_status("done")
    with pytest.raises(InvalidParameterError):
        validate_message_status("opened")
    with pytest.raises(InvalidParameterError):
        validate_approval_status("sent")
    with pytest.raises(InvalidParameterError):
        validate_approval_action_type("send_email")
    with pytest.raises(InvalidParameterError):
        validate_audit_outcome("approved")


def test_escape_like() -> None:
    assert escape_like("100%_ready") == "100\\%\\_ready"
