"""Human accept or reject for one document extraction.

The command records the decision and an audit event. It does not post a
payment, change an invoice total, or mark an invoice posted.
"""

from __future__ import annotations

from datetime import UTC, datetime

from wasatch_api.documents.domain.entities import DocumentExtraction
from wasatch_api.documents.domain.review import (
    EXTRACTION_REVIEW_DECISIONS,
    awaiting_review,
)
from wasatch_api.documents.infrastructure.repository import DocumentRepository
from wasatch_api.shared.errors import InvalidParameterError, NotFoundError
from wasatch_api.workforce.application.access import LaboratoryAccessService
from wasatch_api.workforce.domain.entities import LaboratoryActor


class DocumentExtractionDecisions:
    """Record an approver's decision on an extraction that is awaiting review."""

    def __init__(
        self, repository: DocumentRepository, access: LaboratoryAccessService
    ) -> None:
        self._repository = repository
        self._access = access

    def decide(
        self,
        actor: LaboratoryActor,
        extraction_id: str,
        *,
        decision: str,
        note: str | None,
    ) -> DocumentExtraction:
        self._access.authorize_approval(actor)
        if decision not in EXTRACTION_REVIEW_DECISIONS:
            raise InvalidParameterError(
                f"unsupported document extraction decision: {decision}"
            )
        extraction = self._repository.get_document_extraction(extraction_id)
        if extraction is None:
            raise NotFoundError(f"document extraction {extraction_id} was not found")
        if not awaiting_review(extraction.status):
            raise InvalidParameterError(
                f"document extraction {extraction_id} is {extraction.status}"
            )
        return self._repository.record_review_decision(
            extraction_id,
            actor_employee_id=actor.employee_id,
            to_status=decision,
            reviewed_at=datetime.now(UTC),
            note=_clean_note(note),
        )


def _clean_note(note: str | None) -> str | None:
    if note is None:
        return None
    cleaned = note.strip()
    return cleaned or None
