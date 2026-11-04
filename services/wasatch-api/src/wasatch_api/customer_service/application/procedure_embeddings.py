"""Fill the trusted index with synthetic procedure page text.

The service calls ``EmbeddingPort`` and asks infrastructure to persist the
vectors. It does not import a vendor SDK. Document version bytes are not
read. Extractions are not inserted. Accepting an extraction is a different
command and does not post a payment or change an invoice.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from wasatch_api.ai.application.ports import EmbeddingPort
from wasatch_api.customer_service.application.ports import ProcedureEmbeddingStore
from wasatch_api.customer_service.domain.embeddings import ProcedurePageEmbedding
from wasatch_api.customer_service.domain.retrieval import ProcedurePage
from wasatch_api.documents.domain.entities import DocumentExtraction
from wasatch_api.documents.domain.review import extraction_barred_from_trusted_index
from wasatch_api.shared.errors import InvalidParameterError


class FillProcedurePageEmbeddings:
    """Embed each synthetic procedure page and replace the trusted index."""

    def __init__(
        self,
        embeddings: EmbeddingPort,
        store: ProcedureEmbeddingStore,
    ) -> None:
        self._embeddings = embeddings
        self._store = store

    def fill(self, pages: Sequence[ProcedurePage]) -> int:
        """Write one vector per procedure page. Returns the number written."""

        embedded = self._embeddings.embed(tuple(page.text for page in pages))
        if len(embedded) != len(pages):
            raise InvalidParameterError(
                "embedding port returned a different number of vectors"
            )
        if any(len(item.vector) == 0 for item in embedded):
            raise InvalidParameterError("embedding port returned an empty vector")
        widths = {len(item.vector) for item in embedded}
        if len(widths) > 1:
            raise InvalidParameterError("embedding port returned mixed vector widths")
        embedded_at = datetime.now(UTC)
        rows: list[ProcedurePageEmbedding] = []
        for page, item in zip(pages, embedded, strict=True):
            if page.synthetic is not True:
                raise InvalidParameterError(
                    "only synthetic procedure pages are indexed"
                )
            rows.append(
                ProcedurePageEmbedding(
                    procedure_id=page.id,
                    model=item.model,
                    vector=item.vector,
                    token_count=item.token_count,
                    embedded_at=embedded_at,
                )
            )
        self._store.replace_procedure_pages(tuple(rows))
        return len(rows)

    def exclude_extraction(
        self,
        extraction: DocumentExtraction,
        *,
        document_invoice_id: str | None,
    ) -> None:
        """Do not insert this extraction into the trusted index.

        Unaccepted rows, ``needs_review``, low confidence, and financial
        extractions are barred. An accepted non-financial extraction is still
        not procedure text, so it is not written either. This method does not
        post a payment or change an invoice.
        """

        if extraction_barred_from_trusted_index(
            status=extraction.status,
            confidence=extraction.confidence,
            extracted_fields=extraction.extracted_fields,
            document_invoice_id=document_invoice_id,
        ):
            return
        # An accepted extraction that is not financial is still not
        # procedure text. This slice does not write it.
