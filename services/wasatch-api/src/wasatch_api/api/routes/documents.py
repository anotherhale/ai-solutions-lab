"""Read-only document, version, and extraction routes.

There is no write route and no human-review decision.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from wasatch_api.api.dependencies import (
    db_session,
    document_queries,
    require_laboratory_actor,
)
from wasatch_api.api.schemas import (
    DocumentDetailOut,
    DocumentExtractionOut,
    DocumentListItemOut,
    DocumentVersionOut,
    PageOut,
)
from wasatch_api.documents.application.queries import DocumentQueries

router = APIRouter(
    prefix="/api/v1",
    tags=["documents"],
    dependencies=[Depends(require_laboratory_actor)],
)

SessionDep = Annotated[Session, Depends(db_session)]


def queries(session: SessionDep) -> DocumentQueries:
    return document_queries(session)


QueriesDep = Annotated[DocumentQueries, Depends(queries)]


@router.get("/documents", response_model=PageOut[DocumentListItemOut])
def list_documents(
    service: QueriesDep,
    status: str | None = None,
    document_type: str | None = None,
    source: str | None = None,
    customer_id: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=100),
) -> PageOut[DocumentListItemOut]:
    items, total, request = service.list_documents(
        page=page,
        page_size=page_size,
        status=status,
        document_type=document_type,
        source=source,
        customer_id=customer_id,
    )
    return PageOut(
        items=[DocumentListItemOut.from_domain(item) for item in items],
        page=request.page,
        page_size=request.page_size,
        total=total,
    )


@router.get("/documents/{document_id}", response_model=DocumentDetailOut)
def get_document(document_id: str, service: QueriesDep) -> DocumentDetailOut:
    return DocumentDetailOut.from_domain(service.get_document(document_id))


@router.get("/document-versions", response_model=PageOut[DocumentVersionOut])
def list_document_versions(
    service: QueriesDep,
    document_id: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=100),
) -> PageOut[DocumentVersionOut]:
    items, total, request = service.list_document_versions(
        page=page,
        page_size=page_size,
        document_id=document_id,
    )
    return PageOut(
        items=[DocumentVersionOut.from_domain(item) for item in items],
        page=request.page,
        page_size=request.page_size,
        total=total,
    )


@router.get("/document-versions/{version_id}", response_model=DocumentVersionOut)
def get_document_version(version_id: str, service: QueriesDep) -> DocumentVersionOut:
    return DocumentVersionOut.from_domain(service.get_document_version(version_id))


@router.get("/document-extractions", response_model=PageOut[DocumentExtractionOut])
def list_document_extractions(
    service: QueriesDep,
    status: str | None = None,
    extractor: str | None = None,
    document_id: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=100),
) -> PageOut[DocumentExtractionOut]:
    items, total, request = service.list_document_extractions(
        page=page,
        page_size=page_size,
        status=status,
        extractor=extractor,
        document_id=document_id,
    )
    return PageOut(
        items=[DocumentExtractionOut.from_domain(item) for item in items],
        page=request.page,
        page_size=request.page_size,
        total=total,
    )


@router.get(
    "/document-extractions/{extraction_id}",
    response_model=DocumentExtractionOut,
)
def get_document_extraction(
    extraction_id: str, service: QueriesDep
) -> DocumentExtractionOut:
    return DocumentExtractionOut.from_domain(
        service.get_document_extraction(extraction_id)
    )
