"""ORM to domain mapping for documents, versions, and extractions."""

from __future__ import annotations

from decimal import Decimal

from wasatch_api.documents.domain.entities import (
    Document,
    DocumentExtraction,
    DocumentVersion,
)
from wasatch_api.shared.database.models import (
    DocumentExtractionORM,
    DocumentORM,
    DocumentVersionORM,
)


def _confidence(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def document_version_from_orm(row: DocumentVersionORM) -> DocumentVersion:
    return DocumentVersion(
        id=row.business_id,
        document_id=row.document.business_id,
        version_number=row.version_number,
        storage_path=row.storage_path,
        checksum_sha256=row.checksum_sha256,
        byte_size=row.byte_size,
        created_by_employee_id=(row.created_by.business_id if row.created_by else None),
        created_at=row.created_at,
    )


def document_extraction_from_orm(row: DocumentExtractionORM) -> DocumentExtraction:
    fields = dict(row.extracted_fields) if row.extracted_fields else None
    return DocumentExtraction(
        id=row.business_id,
        document_id=row.document.business_id,
        document_version_id=row.document_version.business_id,
        status=row.status,
        extractor=row.extractor,
        confidence=_confidence(row.confidence),
        extracted_fields=fields,
        reviewed_by_employee_id=(
            row.reviewed_by.business_id if row.reviewed_by else None
        ),
        reviewed_at=row.reviewed_at,
        review_notes=row.review_notes,
        extracted_at=row.extracted_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def document_from_orm(row: DocumentORM, *, detail: bool) -> Document:
    document = Document(
        id=row.business_id,
        title=row.title,
        document_type=row.document_type,
        status=row.status,
        source=row.source,
        mime_type=row.mime_type,
        untrusted=row.untrusted,
        customer_id=row.customer.business_id if row.customer else None,
        service_location_id=(
            row.service_location.business_id if row.service_location else None
        ),
        work_order_id=row.work_order.business_id if row.work_order else None,
        invoice_id=row.invoice_id,
        current_version_id=(
            row.current_version.business_id if row.current_version else None
        ),
        uploaded_by_employee_id=(
            row.uploaded_by.business_id if row.uploaded_by else None
        ),
        notes=row.notes,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
    if detail:
        document.versions = [document_version_from_orm(item) for item in row.versions]
        document.extractions = [
            document_extraction_from_orm(item) for item in row.extractions
        ]
    return document
