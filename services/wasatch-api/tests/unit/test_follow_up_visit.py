"""Follow-up visit rules without a database."""

from __future__ import annotations

import pytest

from wasatch_api.shared.errors import InvalidParameterError
from wasatch_api.workflows.domain.follow_up import (
    CANCELLED,
    CONFIRMED,
    UNSCHEDULED,
    next_status,
    opened_status,
)


def test_open_requires_an_approved_customer_message() -> None:
    assert opened_status("send_customer_message", "message", "approved") == UNSCHEDULED
    with pytest.raises(InvalidParameterError, match="approved the request"):
        opened_status("send_customer_message", "message", "pending")
    with pytest.raises(InvalidParameterError, match="approved the request"):
        opened_status("send_customer_message", "message", "rejected")
    with pytest.raises(InvalidParameterError, match="customer message"):
        opened_status("price_override", "invoice", "approved")
    with pytest.raises(InvalidParameterError, match="customer message"):
        opened_status("send_customer_message", "invoice", "approved")


def test_confirm_and_cancel_leave_an_unscheduled_visit() -> None:
    assert next_status(UNSCHEDULED, "confirm") == CONFIRMED
    assert next_status(UNSCHEDULED, "cancel") == CANCELLED
    with pytest.raises(InvalidParameterError, match="already open|is confirmed"):
        next_status(CONFIRMED, "confirm")
    with pytest.raises(InvalidParameterError, match="is cancelled"):
        next_status(CANCELLED, "cancel")
    with pytest.raises(InvalidParameterError, match="unsupported"):
        next_status(UNSCHEDULED, "open")
