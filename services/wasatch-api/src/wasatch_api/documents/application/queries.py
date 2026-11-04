"""Read use cases for documents, versions, and extractions."""

from __future__ import annotations

from wasatch_api.documents.domain.entities import (
    Document,
    DocumentExtraction,
    DocumentVersion,
)
from wasatch_api.documents.infrastructure.repository import DocumentRepository
from wasatch_api.shared.errors import NotFoundError
from wasatch_api.shared.pagination import (
    PageRequest,
    parse_page,
    validate_document_source,
    validate_document_status,
    validate_document_type,
    validate_extraction_status,
    validate_extractor,
)


class DocumentQueries:
    def __init__(self, repository: DocumentRepository) -> None:
        self.repository = repository

    def list_documents(
        self,
        *,
        page: int | None,
        page_size: int | None,
        status: str | None,
        document_type: str | None,
        source: str | None,
        customer_id: str | None,
    ) -> tuple[list[Document], int, PageRequest]:
        request = parse_page(page, page_size)
        items, total = self.repository.list_documents(
            request,
            status=validate_document_status(status),
            document_type=validate_document_type(document_type),
            source=validate_document_source(source),
            customer_id=customer_id,
        )
        return items, total, request

    def get_document(self, document_id: str) -> Document:
        document = self.repository.get_document(document_id)
        if document is None:
            raise NotFoundError(f"document {document_id} was not found")
        return document

    def list_document_versions(
        self,
        *,
        page: int | None,
        page_size: int | None,
        document_id: str | None,
    ) -> tuple[list[DocumentVersion], int, PageRequest]:
        request = parse_page(page, page_size)
        items, total = self.repository.list_document_versions(
            request, document_id=document_id
        )
        return items, total, request

    def get_document_version(self, version_id: str) -> DocumentVersion:
        version = self.repository.get_document_version(version_id)
        if version is None:
            raise NotFoundError(f"document version {version_id} was not found")
        return version

    def list_document_extractions(
        self,
        *,
        page: int | None,
        page_size: int | None,
        status: str | None,
        extractor: str | None,
        document_id: str | None,
    ) -> tuple[list[DocumentExtraction], int, PageRequest]:
        request = parse_page(page, page_size)
        items, total = self.repository.list_document_extractions(
            request,
            status=validate_extraction_status(status),
            extractor=validate_extractor(extractor),
            document_id=document_id,
        )
        return items, total, request

    def get_document_extraction(self, extraction_id: str) -> DocumentExtraction:
        extraction = self.repository.get_document_extraction(extraction_id)
        if extraction is None:
            raise NotFoundError(f"document extraction {extraction_id} was not found")
        return extraction
