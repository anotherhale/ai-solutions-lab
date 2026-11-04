"""Procedure-page vectors in PostgreSQL. Synthetic data only."""

from __future__ import annotations

import socket
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from wasatch_api.ai.infrastructure.fake import FakeModelPort
from wasatch_api.ai.infrastructure.provider import build_model_provider
from wasatch_api.config import get_settings
from wasatch_api.customer_service.application.procedure_embeddings import (
    FillProcedurePageEmbeddings,
)
from wasatch_api.customer_service.domain.embeddings import ProcedurePageEmbedding
from wasatch_api.customer_service.infrastructure.procedure_corpus import (
    ProcedureCorpus,
)
from wasatch_api.customer_service.infrastructure.procedure_embeddings import (
    ProcedureEmbeddingRepository,
)
from wasatch_api.documents.domain.review import extraction_barred_from_trusted_index
from wasatch_api.documents.infrastructure.repository import DocumentRepository
from wasatch_api.shared.database.vector import PROCEDURE_EMBEDDING_WIDTH
from wasatch_api.shared.errors import InvalidParameterError

_LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})


def test_fill_writes_procedure_vectors_without_a_provider_socket(
    monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    _use_fake_provider(monkeypatch)
    opened: list[object] = []
    constructed: list[object] = []
    _guard_sockets(monkeypatch, opened)
    _guard_openai_client(monkeypatch, constructed)
    corpus = ProcedureCorpus.load_default()
    provider = build_model_provider(get_settings())
    assert isinstance(provider, FakeModelPort)
    service = FillProcedurePageEmbeddings(
        provider, ProcedureEmbeddingRepository(db_session)
    )
    try:
        assert service.fill(corpus.pages) == 3
        stored = ProcedureEmbeddingRepository(db_session).list_stored()
        assert [row[0] for row in stored] == ["proc_0001", "proc_0002", "proc_0003"]
        assert {row[1] for row in stored} == {"fake-embedding"}
        fake = FakeModelPort()
        for page, row in zip(corpus.pages, stored, strict=True):
            expected = fake.embed((page.text,))[0]
            assert row[2] == pytest.approx(expected.vector)
            assert row[3] == expected.token_count
            assert len(row[2]) == PROCEDURE_EMBEDDING_WIDTH
        dims = (
            db_session.execute(
                text(
                    """
                    SELECT DISTINCT vector_dims(embedding)
                    FROM procedure_page_embeddings
                    """
                )
            )
            .scalars()
            .all()
        )
        assert dims == [PROCEDURE_EMBEDDING_WIDTH]
        versions = db_session.scalar(text("SELECT count(*) FROM document_versions"))
        extractions = db_session.scalar(
            text("SELECT count(*) FROM document_extractions")
        )
        assert versions == 31
        assert extractions == 18
        assert service.fill(corpus.pages) == 3
        assert _count(db_session) == 3
    finally:
        _clear(db_session)
        get_settings.cache_clear()
    assert constructed == []
    for address in opened:
        assert _is_local(address), address


def test_retrieval_for_tkt_0015_still_cites_proc_0001(
    monkeypatch: pytest.MonkeyPatch, db_session: Session, client: TestClient
) -> None:
    _use_fake_provider(monkeypatch)
    corpus = ProcedureCorpus.load_default()
    service = FillProcedurePageEmbeddings(
        build_model_provider(get_settings()),
        ProcedureEmbeddingRepository(db_session),
    )
    try:
        service.fill(corpus.pages)
        response = client.get("/api/v1/support-tickets/tkt_0015/retrieval")
        assert response.status_code == 200
        body = response.json()
        assert [page["id"] for page in body["procedures"]] == ["proc_0001"]
        assert "embedding" not in body["procedures"][0]
        history = {item["source_id"] for item in body["history"]}
        assert {"tkt_0015", "msg_0015", "ixn_0015", "wo_0015", "wo_0035"} <= history
        assert "tkt_0001" not in history
    finally:
        _clear(db_session)
        get_settings.cache_clear()


def test_unaccepted_financial_extraction_is_not_inserted(
    db_session: Session,
) -> None:
    documents = DocumentRepository(db_session)
    extraction = documents.get_document_extraction("dx_0001")
    assert extraction is not None
    document = documents.get_document(extraction.document_id)
    assert document is not None
    assert extraction.status != "accepted"
    assert (
        extraction_barred_from_trusted_index(
            status=extraction.status,
            confidence=extraction.confidence,
            extracted_fields=extraction.extracted_fields,
            document_invoice_id=document.invoice_id,
        )
        is True
    )
    invoice_before = document.invoice_id
    status_before = extraction.status
    before = _count(db_session)
    service = FillProcedurePageEmbeddings(
        FakeModelPort(), ProcedureEmbeddingRepository(db_session)
    )
    service.exclude_extraction(extraction, document_invoice_id=document.invoice_id)
    assert _count(db_session) == before
    indexed = db_session.scalar(
        text(
            """
            SELECT count(*)
            FROM procedure_page_embeddings
            WHERE procedure_id = 'dx_0001'
            """
        )
    )
    assert indexed == 0
    again = documents.get_document_extraction("dx_0001")
    assert again is not None
    assert again.status == status_before
    reread = documents.get_document(extraction.document_id)
    assert reread is not None
    assert reread.invoice_id == invoice_before


def test_document_version_and_other_widths_are_not_stored(
    db_session: Session,
) -> None:
    store = ProcedureEmbeddingRepository(db_session)
    now = ProcedurePageEmbedding(
        procedure_id="proc_0001",
        model="fake-embedding",
        vector=(0.0,) * PROCEDURE_EMBEDDING_WIDTH,
        token_count=1,
        embedded_at=datetime.now(UTC),
    )
    version = ProcedurePageEmbedding(
        procedure_id="dv_0001",
        model=now.model,
        vector=now.vector,
        token_count=now.token_count,
        embedded_at=now.embedded_at,
    )
    wide = ProcedurePageEmbedding(
        procedure_id="proc_0001",
        model=now.model,
        vector=(0.0,) * 1536,
        token_count=now.token_count,
        embedded_at=now.embedded_at,
    )
    try:
        with pytest.raises(InvalidParameterError, match="procedure pages only"):
            store.replace_procedure_pages((version,))
        with pytest.raises(InvalidParameterError, match="width"):
            store.replace_procedure_pages((wide,))
        assert _count(db_session) == 0
    finally:
        _clear(db_session)


def _use_fake_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()


def _guard_sockets(monkeypatch: pytest.MonkeyPatch, opened: list[object]) -> None:
    real_connect = socket.socket.connect
    real_create = socket.create_connection

    def connect(self: socket.socket, address: object) -> object:
        opened.append(address)
        if not _is_local(address):
            raise AssertionError(f"provider socket: {address!r}")
        return real_connect(self, address)  # type: ignore[arg-type]

    def create_connection(address: object, *args: object, **kwargs: object) -> object:
        opened.append(address)
        if not _is_local(address):
            raise AssertionError(f"provider socket: {address!r}")
        return real_create(address, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "create_connection", create_connection)


def _guard_openai_client(
    monkeypatch: pytest.MonkeyPatch, constructed: list[object]
) -> None:
    import openai

    def _reject(*_args: object, **_kwargs: object) -> None:
        constructed.append("openai")
        raise AssertionError("OpenAI client constructed")

    monkeypatch.setattr(openai, "OpenAI", _reject)


def _is_local(address: object) -> bool:
    if isinstance(address, str):
        return True
    if isinstance(address, tuple) and address:
        host = address[0]
        return isinstance(host, str) and host in _LOOPBACK
    return False


def _count(session: Session) -> int:
    value = session.scalar(text("SELECT count(*) FROM procedure_page_embeddings"))
    return int(value or 0)


def _clear(session: Session) -> None:
    session.execute(text("DELETE FROM procedure_page_embeddings"))
    session.commit()
