"""Pagination and list-filter validation."""

from __future__ import annotations

from dataclasses import dataclass

from wasatch_api.shared.errors import InvalidParameterError

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

CUSTOMER_STATUSES = frozenset({"active", "inactive", "prospect", "suspended"})
WORK_ORDER_STATUSES = frozenset(
    {
        "created",
        "scheduled",
        "assigned",
        "in_progress",
        "awaiting_parts",
        "completed",
        "invoiced",
        "cancelled",
        "reopened",
    }
)
SUPPORT_TICKET_STATUSES = frozenset(
    {
        "opened",
        "triaged",
        "assigned",
        "awaiting_customer",
        "resolved",
        "closed",
        "reopened",
    }
)
MESSAGE_STATUSES = frozenset(
    {"draft", "pending_approval", "sent", "failed", "discarded"}
)
APPROVAL_STATUSES = frozenset(
    {"pending", "approved", "rejected", "executed", "cancelled"}
)
APPROVAL_ACTION_TYPES = frozenset(
    {
        "send_customer_message",
        "void_invoice",
        "issue_invoice",
        "cancel_work_order",
        "change_schedule",
        "export_records",
        "price_override",
    }
)
AUDIT_OUTCOMES = frozenset({"succeeded", "failed", "pending"})
DOCUMENT_STATUSES = frozenset(
    {
        "uploaded",
        "awaiting_extraction",
        "extracted",
        "needs_review",
        "reviewed",
        "archived",
    }
)
DOCUMENT_TYPES = frozenset(
    {
        "invoice_scan",
        "work_order_photo",
        "contract",
        "vendor_bill",
        "equipment_manual",
        "correspondence",
        "other",
    }
)
DOCUMENT_SOURCES = frozenset({"email", "upload", "scan", "generated"})
EXTRACTION_STATUSES = frozenset(
    {"pending", "succeeded", "failed", "needs_review", "accepted", "rejected"}
)
EXTRACTORS = frozenset({"human", "model", "rules"})
INVOICE_STATUSES = frozenset(
    {"draft", "issued", "partially_paid", "paid", "overdue", "voided"}
)
INVOICE_LINE_TYPES = frozenset(
    {"labor", "parts", "travel", "equipment", "adjustment", "agreement"}
)
PAYMENT_STATUSES = frozenset({"pending", "posted", "failed", "reversed"})
PAYMENT_METHODS = frozenset({"ach", "check", "card", "wire", "credit_memo"})


@dataclass(frozen=True)
class PageRequest:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def parse_page(page: int | None, page_size: int | None) -> PageRequest:
    resolved_page = DEFAULT_PAGE if page is None else page
    resolved_size = DEFAULT_PAGE_SIZE if page_size is None else page_size
    if resolved_page < 1:
        raise InvalidParameterError("page must be greater than or equal to 1")
    if resolved_size < 1 or resolved_size > MAX_PAGE_SIZE:
        raise InvalidParameterError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
    return PageRequest(page=resolved_page, page_size=resolved_size)


def validate_customer_status(status: str | None) -> str | None:
    if status is None:
        return None
    if status not in CUSTOMER_STATUSES:
        raise InvalidParameterError(f"unsupported customer status: {status}")
    return status


def validate_work_order_status(status: str | None) -> str | None:
    if status is None:
        return None
    if status not in WORK_ORDER_STATUSES:
        raise InvalidParameterError(f"unsupported work order status: {status}")
    return status


def validate_support_ticket_status(status: str | None) -> str | None:
    if status is None:
        return None
    if status not in SUPPORT_TICKET_STATUSES:
        raise InvalidParameterError(f"unsupported support ticket status: {status}")
    return status


def validate_message_status(status: str | None) -> str | None:
    if status is None:
        return None
    if status not in MESSAGE_STATUSES:
        raise InvalidParameterError(f"unsupported message status: {status}")
    return status


def validate_approval_status(status: str | None) -> str | None:
    if status is None:
        return None
    if status not in APPROVAL_STATUSES:
        raise InvalidParameterError(f"unsupported approval status: {status}")
    return status


def validate_approval_action_type(action_type: str | None) -> str | None:
    if action_type is None:
        return None
    if action_type not in APPROVAL_ACTION_TYPES:
        raise InvalidParameterError(f"unsupported approval action: {action_type}")
    return action_type


def validate_audit_outcome(outcome: str | None) -> str | None:
    if outcome is None:
        return None
    if outcome not in AUDIT_OUTCOMES:
        raise InvalidParameterError(f"unsupported audit outcome: {outcome}")
    return outcome


def validate_document_status(status: str | None) -> str | None:
    if status is None:
        return None
    if status not in DOCUMENT_STATUSES:
        raise InvalidParameterError(f"unsupported document status: {status}")
    return status


def validate_document_type(document_type: str | None) -> str | None:
    if document_type is None:
        return None
    if document_type not in DOCUMENT_TYPES:
        raise InvalidParameterError(f"unsupported document type: {document_type}")
    return document_type


def validate_document_source(source: str | None) -> str | None:
    if source is None:
        return None
    if source not in DOCUMENT_SOURCES:
        raise InvalidParameterError(f"unsupported document source: {source}")
    return source


def validate_extraction_status(status: str | None) -> str | None:
    if status is None:
        return None
    if status not in EXTRACTION_STATUSES:
        raise InvalidParameterError(f"unsupported extraction status: {status}")
    return status


def validate_extractor(extractor: str | None) -> str | None:
    if extractor is None:
        return None
    if extractor not in EXTRACTORS:
        raise InvalidParameterError(f"unsupported extractor: {extractor}")
    return extractor


def validate_invoice_status(status: str | None) -> str | None:
    if status is None:
        return None
    if status not in INVOICE_STATUSES:
        raise InvalidParameterError(f"unsupported invoice status: {status}")
    return status


def validate_invoice_line_type(line_type: str | None) -> str | None:
    if line_type is None:
        return None
    if line_type not in INVOICE_LINE_TYPES:
        raise InvalidParameterError(f"unsupported invoice line type: {line_type}")
    return line_type


def validate_payment_status(status: str | None) -> str | None:
    if status is None:
        return None
    if status not in PAYMENT_STATUSES:
        raise InvalidParameterError(f"unsupported payment status: {status}")
    return status


def validate_payment_method(method: str | None) -> str | None:
    if method is None:
        return None
    if method not in PAYMENT_METHODS:
        raise InvalidParameterError(f"unsupported payment method: {method}")
    return method


def escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
