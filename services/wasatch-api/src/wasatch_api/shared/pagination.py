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


def escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
