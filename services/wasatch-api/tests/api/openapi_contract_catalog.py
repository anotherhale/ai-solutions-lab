"""Expected HTTP surface for the Wasatch laboratory API slice.

Keep this catalog aligned with docs/architecture/API_CONVENTIONS.md.
"""

from __future__ import annotations

SLICE_PATH_METHODS: dict[str, frozenset[str]] = {
    "/health": frozenset({"get"}),
    "/health/ready": frozenset({"get"}),
    "/api/v1/customers": frozenset({"get"}),
    "/api/v1/customers/{customer_id}": frozenset({"get"}),
    "/api/v1/service-locations/{location_id}": frozenset({"get"}),
    "/api/v1/work-orders": frozenset({"get"}),
    "/api/v1/work-orders/{work_order_id}": frozenset({"get"}),
    "/api/v1/support-tickets": frozenset({"get"}),
    "/api/v1/support-tickets/{ticket_id}": frozenset({"get"}),
    "/api/v1/support-tickets/{ticket_id}/retrieval": frozenset({"get"}),
    "/api/v1/support-tickets/{ticket_id}/draft-replies": frozenset({"post"}),
    "/api/v1/messages": frozenset({"get"}),
    "/api/v1/messages/{message_id}": frozenset({"get"}),
    "/api/v1/interactions": frozenset({"get"}),
    "/api/v1/interactions/{interaction_id}": frozenset({"get"}),
    "/api/v1/approval-requests": frozenset({"get"}),
    "/api/v1/approval-requests/{approval_id}": frozenset({"get"}),
    "/api/v1/approval-requests/{approval_id}/decisions": frozenset({"post"}),
    "/api/v1/approval-requests/{approval_id}/follow-up-visits": frozenset(
        {"get", "post"}
    ),
    "/api/v1/follow-up-visits/{follow_up_id}": frozenset({"get"}),
    "/api/v1/audit-events": frozenset({"get"}),
    "/api/v1/audit-events/{audit_event_id}": frozenset({"get"}),
    "/api/v1/invoices": frozenset({"get"}),
    "/api/v1/invoices/{invoice_id}": frozenset({"get"}),
    "/api/v1/invoices/{invoice_id}/lines": frozenset({"get"}),
    "/api/v1/invoice-lines/{invoice_line_id}": frozenset({"get"}),
    "/api/v1/payments": frozenset({"get"}),
    "/api/v1/payments/{payment_id}": frozenset({"get"}),
    "/api/v1/documents": frozenset({"get"}),
    "/api/v1/documents/{document_id}": frozenset({"get"}),
    "/api/v1/document-versions": frozenset({"get"}),
    "/api/v1/document-versions/{version_id}": frozenset({"get"}),
    "/api/v1/document-extractions": frozenset({"get"}),
    "/api/v1/document-extractions/{extraction_id}": frozenset({"get"}),
    "/api/v1/document-extractions/{extraction_id}/decisions": frozenset({"post"}),
}

WRITE_PATHS = frozenset(
    path
    for path, methods in SLICE_PATH_METHODS.items()
    if "post" in methods and path.startswith("/api/v1/")
)

READ_PATHS = frozenset(
    path
    for path, methods in SLICE_PATH_METHODS.items()
    if methods <= frozenset({"get", "head"}) and path.startswith("/api/v1/")
)

LIST_GET_QUERY_PARAM_NAMES: dict[str, frozenset[str]] = {
    "/api/v1/work-orders": frozenset(
        {
            "customer_id",
            "status",
            "assigned_employee_id",
            "service_location_id",
            "invoice_id",
            "page",
            "page_size",
        }
    ),
    "/api/v1/invoices": frozenset({"customer_id", "status", "page", "page_size"}),
    "/api/v1/invoices/{invoice_id}/lines": frozenset(
        {"line_type", "page", "page_size"}
    ),
    "/api/v1/payments": frozenset(
        {"invoice_id", "status", "method", "page", "page_size"}
    ),
}

POST_BODY_DECISION_ENUMS: dict[str, frozenset[str]] = {
    "/api/v1/approval-requests/{approval_id}/decisions": frozenset(
        {"approved", "rejected"}
    ),
    "/api/v1/document-extractions/{extraction_id}/decisions": frozenset(
        {"accepted", "rejected"}
    ),
    "/api/v1/approval-requests/{approval_id}/follow-up-visits": frozenset(
        {"open", "confirm", "cancel"}
    ),
}
