"""Low-confidence and financial extractions stay undecided without a person."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from wasatch_api.documents.application.decisions import (
    EXTRACTION_REVIEW_DECISIONS,
    DocumentExtractionDecisions,
)
from wasatch_api.documents.domain.entities import DocumentExtraction
from wasatch_api.documents.domain.review import (
    awaiting_review,
    has_financial_effect,
    is_low_confidence,
    requires_human_review,
    unattended_status,
)
from wasatch_api.shared.errors import AuthorizationDenied, InvalidParameterError
from wasatch_api.workforce.application.access import LaboratoryAccessService
from wasatch_api.workforce.domain.entities import LaboratoryActor
from wasatch_api.workforce.infrastructure.local_authenticator import (
    LocalEmployeeAuthenticator,
)

DISPATCHER = LaboratoryActor(
    employee_id="emp_0004",
    role_id="role_0004",
    is_approver=False,
    status="active",
)
MANAGER = LaboratoryActor(
    employee_id="emp_0001",
    role_id="role_0001",
    is_approver=True,
    status="active",
)
NOW = datetime(2026, 6, 2, 13, 0, tzinfo=UTC)


def _extraction(status: str, confidence: float | None = 0.7) -> DocumentExtraction:
    return DocumentExtraction(
        id="dx_0003",
        document_id="doc_0003",
        document_version_id="dv_0003",
        status=status,
        extractor="model",
        confidence=confidence,
        extracted_fields={"invoice_number": "V-0003"},
        review_notes="Low confidence; hold for AP.",
        extracted_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )


class _Directory:
    def __init__(self, actors: dict[str, LaboratoryActor]) -> None:
        self._actors = actors

    def find_actor(self, business_id: str) -> LaboratoryActor | None:
        return self._actors.get(business_id)


class _Repository:
    def __init__(self, extraction: DocumentExtraction) -> None:
        self.extraction = extraction
        self.recorded: dict | None = None

    def get_document_extraction(self, extraction_id: str) -> DocumentExtraction | None:
        if self.extraction.id == extraction_id:
            return self.extraction
        return None

    def record_review_decision(
        self, extraction_id: str, **kwargs
    ) -> DocumentExtraction:
        self.recorded = {"extraction_id": extraction_id, **kwargs}
        return self.extraction


def _service(
    repository: _Repository, actor: LaboratoryActor
) -> DocumentExtractionDecisions:
    access = LaboratoryAccessService(
        LocalEmployeeAuthenticator(
            _Directory({actor.employee_id: actor}), app_env="test"
        )
    )
    return DocumentExtractionDecisions(repository, access)


def test_confidence_boundary() -> None:
    assert is_low_confidence(None) is True
    assert is_low_confidence(Decimal("0.7")) is True
    assert is_low_confidence(0.799) is True
    assert is_low_confidence(Decimal("0.8")) is False
    assert is_low_confidence(0.9) is False


def test_financial_effect_covers_invoice_fields_and_linked_documents() -> None:
    assert has_financial_effect({"invoice_number": "V-0003"}, None) is True
    assert has_financial_effect({"amount": "10.00"}, None) is True
    assert has_financial_effect({"lines": [{"unit_price": "1.00"}]}, None) is True
    assert has_financial_effect({"vendor_name": "Synthetic Vendor"}, None) is False
    assert has_financial_effect(None, "inv_0015") is True
    assert has_financial_effect({}, "  ") is False
    assert has_financial_effect(None, None) is False


def test_low_confidence_and_financial_rows_require_a_person() -> None:
    assert (
        requires_human_review(
            status="needs_review",
            confidence=Decimal("0.7"),
            extracted_fields={"invoice_number": "V-0003"},
            document_invoice_id=None,
        )
        is True
    )
    assert (
        requires_human_review(
            status="succeeded",
            confidence=Decimal("0.6"),
            extracted_fields={"invoice_number": "V-0002"},
            document_invoice_id=None,
        )
        is True
    )
    assert (
        requires_human_review(
            status="pending",
            confidence=Decimal("0.95"),
            extracted_fields={"vendor_name": "Synthetic Vendor"},
            document_invoice_id="inv_0015",
        )
        is True
    )
    assert (
        requires_human_review(
            status="needs_review",
            confidence=Decimal("0.95"),
            extracted_fields={"vendor_name": "Synthetic Vendor"},
            document_invoice_id=None,
        )
        is True
    )
    assert (
        requires_human_review(
            status="succeeded",
            confidence=Decimal("0.95"),
            extracted_fields={"vendor_name": "Synthetic Vendor"},
            document_invoice_id=None,
        )
        is False
    )
    assert (
        requires_human_review(
            status="accepted",
            confidence=Decimal("0.8"),
            extracted_fields={"invoice_number": "V-0004"},
            document_invoice_id=None,
        )
        is False
    )


def test_unattended_paths_do_not_accept_or_reject() -> None:
    held = {
        "status": "needs_review",
        "confidence": Decimal("0.7"),
        "extracted_fields": {"invoice_number": "V-0003"},
        "document_invoice_id": None,
    }
    assert unattended_status(**held) == "needs_review"
    assert unattended_status(**held, proposed_status="accepted") == "needs_review"
    assert unattended_status(**held, proposed_status="rejected") == "needs_review"

    linked = {
        "status": "pending",
        "confidence": Decimal("0.95"),
        "extracted_fields": {"vendor_name": "Synthetic Vendor"},
        "document_invoice_id": "inv_0015",
    }
    assert unattended_status(**linked, proposed_status="accepted") == "pending"

    confident = {
        "status": "succeeded",
        "confidence": Decimal("0.95"),
        "extracted_fields": {"vendor_name": "Synthetic Vendor"},
        "document_invoice_id": None,
    }
    assert unattended_status(**confident, proposed_status="accepted") == "succeeded"
    copied = unattended_status(
        "accepted",
        confidence=confident["confidence"],
        extracted_fields=confident["extracted_fields"],
        document_invoice_id=confident["document_invoice_id"],
    )
    assert copied == "accepted"


def test_awaiting_review_is_the_undecided_status_set() -> None:
    assert EXTRACTION_REVIEW_DECISIONS == frozenset({"accepted", "rejected"})
    for status in ("pending", "succeeded", "failed", "needs_review"):
        assert awaiting_review(status) is True
    assert awaiting_review("accepted") is False
    assert awaiting_review("rejected") is False


def test_dispatcher_cannot_decide_an_extraction() -> None:
    repository = _Repository(_extraction("needs_review"))
    service = _service(repository, DISPATCHER)
    with pytest.raises(AuthorizationDenied, match="role role_0004"):
        service.decide(DISPATCHER, "dx_0003", decision="accepted", note="override")
    assert repository.recorded is None


def test_approver_command_records_only_the_decision() -> None:
    repository = _Repository(_extraction("needs_review"))
    service = _service(repository, MANAGER)
    service.decide(MANAGER, "dx_0003", decision="accepted", note="  Hold cleared.  ")
    assert repository.recorded is not None
    assert repository.recorded["extraction_id"] == "dx_0003"
    assert repository.recorded["actor_employee_id"] == "emp_0001"
    assert repository.recorded["to_status"] == "accepted"
    assert repository.recorded["note"] == "Hold cleared."
    assert "invoice" not in repository.recorded
    assert "payment" not in repository.recorded


def test_command_rejects_a_posting_decision_and_a_closed_row() -> None:
    repository = _Repository(_extraction("needs_review"))
    service = _service(repository, MANAGER)
    with pytest.raises(InvalidParameterError, match="unsupported"):
        service.decide(MANAGER, "dx_0003", decision="posted", note=None)
    assert repository.recorded is None

    repository.extraction = _extraction("accepted", confidence=0.8)
    with pytest.raises(InvalidParameterError, match="is accepted"):
        service.decide(MANAGER, "dx_0003", decision="rejected", note=None)
    assert repository.recorded is None
