"""PostgreSQL adapter for document reads.

There is no write method. Extraction review is not recorded here.
"""

from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from wasatch_api.documents.domain.entities import (
    Document,
    DocumentExtraction,
    DocumentVersion,
)
from wasatch_api.documents.infrastructure.mapping import (
    document_extraction_from_orm,
    document_from_orm,
    document_version_from_orm,
)
from wasatch_api.shared.database.models import (
    DocumentExtractionORM,
    DocumentORM,
    DocumentVersionORM,
)
from wasatch_api.shared.pagination import PageRequest


def _restrict(stmt, count_stmt, criteria: list):
    if not criteria:
        return stmt, count_stmt
    return stmt.where(*criteria), count_stmt.where(*criteria)


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_document(self, business_id: str) -> Document | None:
        stmt = (
            select(DocumentORM)
            .options(*_document_detail_options())
            .where(DocumentORM.business_id == business_id)
        )
        row = self.session.scalar(stmt)
        if row is None:
            return None
        return document_from_orm(row, detail=True)

    def list_documents(
        self,
        page: PageRequest,
        *,
        status: str | None = None,
        document_type: str | None = None,
        source: str | None = None,
        customer_id: str | None = None,
    ) -> tuple[list[Document], int]:
        stmt: Select[tuple[DocumentORM]] = select(DocumentORM).options(
            *_document_summary_options()
        )
        count_stmt = select(func.count()).select_from(DocumentORM)
        criteria = []
        if status:
            criteria.append(DocumentORM.status == status)
        if document_type:
            criteria.append(DocumentORM.document_type == document_type)
        if source:
            criteria.append(DocumentORM.source == source)
        if customer_id:
            criteria.append(DocumentORM.customer.has(business_id=customer_id))
        stmt, count_stmt = _restrict(stmt, count_stmt, criteria)
        return _page(
            self.session,
            stmt.order_by(DocumentORM.business_id),
            count_stmt,
            page,
            lambda row: document_from_orm(row, detail=False),
        )

    def get_document_version(self, business_id: str) -> DocumentVersion | None:
        stmt = (
            select(DocumentVersionORM)
            .options(*_version_options())
            .where(DocumentVersionORM.business_id == business_id)
        )
        row = self.session.scalar(stmt)
        if row is None:
            return None
        return document_version_from_orm(row)

    def list_document_versions(
        self,
        page: PageRequest,
        *,
        document_id: str | None = None,
    ) -> tuple[list[DocumentVersion], int]:
        stmt: Select[tuple[DocumentVersionORM]] = select(DocumentVersionORM).options(
            *_version_options()
        )
        count_stmt = select(func.count()).select_from(DocumentVersionORM)
        criteria = []
        if document_id:
            criteria.append(DocumentVersionORM.document.has(business_id=document_id))
        stmt, count_stmt = _restrict(stmt, count_stmt, criteria)
        return _page(
            self.session,
            stmt.order_by(DocumentVersionORM.business_id),
            count_stmt,
            page,
            document_version_from_orm,
        )

    def get_document_extraction(self, business_id: str) -> DocumentExtraction | None:
        stmt = (
            select(DocumentExtractionORM)
            .options(*_extraction_options())
            .where(DocumentExtractionORM.business_id == business_id)
        )
        row = self.session.scalar(stmt)
        if row is None:
            return None
        return document_extraction_from_orm(row)

    def list_document_extractions(
        self,
        page: PageRequest,
        *,
        status: str | None = None,
        extractor: str | None = None,
        document_id: str | None = None,
    ) -> tuple[list[DocumentExtraction], int]:
        stmt: Select[tuple[DocumentExtractionORM]] = select(
            DocumentExtractionORM
        ).options(*_extraction_options())
        count_stmt = select(func.count()).select_from(DocumentExtractionORM)
        criteria = []
        if status:
            criteria.append(DocumentExtractionORM.status == status)
        if extractor:
            criteria.append(DocumentExtractionORM.extractor == extractor)
        if document_id:
            criteria.append(DocumentExtractionORM.document.has(business_id=document_id))
        stmt, count_stmt = _restrict(stmt, count_stmt, criteria)
        return _page(
            self.session,
            stmt.order_by(DocumentExtractionORM.business_id),
            count_stmt,
            page,
            document_extraction_from_orm,
        )


def _document_summary_options():
    return (
        selectinload(DocumentORM.customer),
        selectinload(DocumentORM.service_location),
        selectinload(DocumentORM.work_order),
        selectinload(DocumentORM.uploaded_by),
        selectinload(DocumentORM.current_version),
    )


def _document_detail_options():
    return (
        selectinload(DocumentORM.customer),
        selectinload(DocumentORM.service_location),
        selectinload(DocumentORM.work_order),
        selectinload(DocumentORM.uploaded_by),
        selectinload(DocumentORM.current_version),
        selectinload(DocumentORM.versions).selectinload(DocumentVersionORM.document),
        selectinload(DocumentORM.versions).selectinload(DocumentVersionORM.created_by),
        selectinload(DocumentORM.extractions).selectinload(
            DocumentExtractionORM.document
        ),
        selectinload(DocumentORM.extractions).selectinload(
            DocumentExtractionORM.document_version
        ),
        selectinload(DocumentORM.extractions).selectinload(
            DocumentExtractionORM.reviewed_by
        ),
    )


def _version_options():
    return (
        selectinload(DocumentVersionORM.document),
        selectinload(DocumentVersionORM.created_by),
    )


def _extraction_options():
    return (
        selectinload(DocumentExtractionORM.document),
        selectinload(DocumentExtractionORM.document_version),
        selectinload(DocumentExtractionORM.reviewed_by),
    )


def _page(session: Session, stmt, count_stmt, page: PageRequest, mapper):
    total = int(session.scalar(count_stmt) or 0)
    rows = session.scalars(stmt.offset(page.offset).limit(page.page_size)).all()
    return [mapper(row) for row in rows], total
