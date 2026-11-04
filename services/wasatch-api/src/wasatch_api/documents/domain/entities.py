"""Document domain records used by application services.

Extraction fields stay untrusted until an approver accepts them. The review
rule lives in ``review.py``. Accepting or rejecting does not post finance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class DocumentVersion:
    id: str
    document_id: str
    version_number: int
    storage_path: str
    checksum_sha256: str
    created_at: datetime
    byte_size: int | None = None
    created_by_employee_id: str | None = None


@dataclass(frozen=True)
class DocumentExtraction:
    id: str
    document_id: str
    document_version_id: str
    status: str
    extractor: str
    extracted_at: datetime
    created_at: datetime
    updated_at: datetime
    confidence: float | None = None
    extracted_fields: dict | None = None
    reviewed_by_employee_id: str | None = None
    reviewed_at: datetime | None = None
    review_notes: str | None = None


@dataclass
class Document:
    id: str
    title: str
    document_type: str
    status: str
    source: str
    mime_type: str
    untrusted: bool
    created_at: datetime
    updated_at: datetime
    customer_id: str | None = None
    service_location_id: str | None = None
    work_order_id: str | None = None
    invoice_id: str | None = None
    current_version_id: str | None = None
    uploaded_by_employee_id: str | None = None
    notes: str | None = None
    versions: list[DocumentVersion] = field(default_factory=list)
    extractions: list[DocumentExtraction] = field(default_factory=list)
