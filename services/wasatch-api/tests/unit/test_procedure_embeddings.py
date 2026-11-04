"""Procedure embeddings stay on the fake port and out of the domain width."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from wasatch_api.customer_service.application.procedure_embeddings import (
    FillProcedurePageEmbeddings,
)
from wasatch_api.customer_service.domain.embeddings import ProcedurePageEmbedding
from wasatch_api.customer_service.domain.retrieval import ProcedurePage
from wasatch_api.documents.domain.entities import DocumentExtraction
from wasatch_api.documents.domain.review import extraction_barred_from_trusted_index

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "wasatch_api"
DOMAIN_ROOTS = (
    PACKAGE / "customer_service" / "domain",
    PACKAGE / "documents" / "domain",
)
NOW = datetime(2026, 6, 2, 13, 0, tzinfo=UTC)


class _Store:
    def __init__(self) -> None:
        self.rows: tuple[ProcedurePageEmbedding, ...] | None = None

    def replace_procedure_pages(self, rows: tuple[ProcedurePageEmbedding, ...]) -> None:
        self.rows = rows

    def stored_among(self, procedure_ids: tuple[str, ...]) -> tuple[str, ...]:
        return procedure_ids

    def order_by_similarity(
        self, procedure_ids: tuple[str, ...], query: tuple[float, ...]
    ) -> tuple[str, ...]:
        return procedure_ids


def test_domain_does_not_choose_an_embedding_width() -> None:
    offenders: list[str] = []
    for root in DOMAIN_ROOTS:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "1536" in text or "vector(" in text:
                offenders.append(path.name)
    assert offenders == []


def test_unaccepted_financial_extraction_is_barred_and_not_written() -> None:
    extraction = _extraction(
        status="pending",
        confidence=0.5,
        fields={"invoice_number": "V-0001"},
    )
    assert (
        extraction_barred_from_trusted_index(
            status=extraction.status,
            confidence=extraction.confidence,
            extracted_fields=extraction.extracted_fields,
            document_invoice_id=None,
        )
        is True
    )
    store = _Store()
    FillProcedurePageEmbeddings(_UnusedPort(), store).exclude_extraction(
        extraction, document_invoice_id=None
    )
    assert store.rows is None


def test_needs_review_low_confidence_and_accepted_finance_stay_out() -> None:
    assert (
        extraction_barred_from_trusted_index(
            status="needs_review",
            confidence=0.95,
            extracted_fields={"vendor_name": "Synthetic Vendor"},
            document_invoice_id=None,
        )
        is True
    )
    assert (
        extraction_barred_from_trusted_index(
            status="accepted",
            confidence=0.4,
            extracted_fields={"vendor_name": "Synthetic Vendor"},
            document_invoice_id=None,
        )
        is True
    )
    assert (
        extraction_barred_from_trusted_index(
            status="accepted",
            confidence=0.9,
            extracted_fields={"invoice_number": "V-0004"},
            document_invoice_id=None,
        )
        is True
    )
    accepted = _extraction(
        status="accepted",
        confidence=0.95,
        fields={"vendor_name": "Synthetic Vendor"},
    )
    assert (
        extraction_barred_from_trusted_index(
            status=accepted.status,
            confidence=accepted.confidence,
            extracted_fields=accepted.extracted_fields,
            document_invoice_id=None,
        )
        is False
    )
    store = _Store()
    FillProcedurePageEmbeddings(_UnusedPort(), store).exclude_extraction(
        accepted, document_invoice_id=None
    )
    assert store.rows is None


def test_fill_embeds_procedure_text_only() -> None:
    page = ProcedurePage(
        id="proc_0001",
        title="Rooftop unit is down",
        path="rooftop-unit-down.txt",
        text="Synthetic laboratory procedure for Wasatch Business Systems.\n",
        synthetic=True,
    )
    port = _RecordingPort()
    store = _Store()
    written = FillProcedurePageEmbeddings(port, store).fill((page,))
    assert written == 1
    assert port.texts == (page.text,)
    assert "synthetic/documents" not in port.texts[0]
    assert store.rows is not None
    assert store.rows[0].procedure_id == "proc_0001"
    assert store.rows[0].vector == port.vectors[0]


class _UnusedPort:
    def embed(self, texts: tuple[str, ...]) -> tuple[object, ...]:
        raise AssertionError(texts)


class _RecordingPort:
    def __init__(self) -> None:
        self.texts: tuple[str, ...] = ()
        self.vectors: tuple[tuple[float, ...], ...] = ()

    def embed(self, texts: tuple[str, ...]):
        from wasatch_api.ai.infrastructure.fake import FakeModelPort

        self.texts = tuple(texts)
        embedded = FakeModelPort().embed(texts)
        self.vectors = tuple(item.vector for item in embedded)
        return embedded


def _extraction(
    *,
    status: str,
    confidence: float | None,
    fields: dict[str, str],
) -> DocumentExtraction:
    return DocumentExtraction(
        id="dx_0001",
        document_id="doc_0001",
        document_version_id="dv_0001",
        status=status,
        extractor="rules",
        confidence=confidence,
        extracted_fields=fields,
        extracted_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )
