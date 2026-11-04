"""Human-review rules for synthetic document extractions.

Low-confidence results and any financial effect stay untrusted until an
approver accepts or rejects them. A read, a seed, and a background job do
not accept those rows. This service has no background job. Accepting or
rejecting records that decision only. It does not post a payment or change
an invoice.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

LOW_CONFIDENCE_BELOW = Decimal("0.8")
AWAITING_REVIEW_STATUSES = frozenset({"pending", "succeeded", "failed", "needs_review"})
EXTRACTION_REVIEW_DECISIONS = frozenset({"accepted", "rejected"})
_FINANCIAL_TOKENS = frozenset(
    {
        "amount",
        "balance",
        "invoice",
        "money",
        "payment",
        "price",
        "subtotal",
        "tax",
        "total",
    }
)


def is_low_confidence(confidence: Decimal | float | None) -> bool:
    """Confidence below 0.8, including a missing score, is low."""

    if confidence is None:
        return True
    return Decimal(str(confidence)) < LOW_CONFIDENCE_BELOW


def has_financial_effect(
    extracted_fields: Mapping[str, object] | None,
    document_invoice_id: str | None,
) -> bool:
    """True when the extraction or its document can move money.

    Invoice and money keys in ``extracted_fields`` count. A document linked
    to an invoice counts even when the field map is empty. Field values are
    not inspected.
    """

    if document_invoice_id is not None and document_invoice_id.strip() != "":
        return True
    return _contains_financial_key(extracted_fields)


def requires_human_review(
    *,
    status: str,
    confidence: Decimal | float | None,
    extracted_fields: Mapping[str, object] | None,
    document_invoice_id: str | None,
) -> bool:
    """True while a person must decide before the row can be trusted.

    ``accepted`` and ``rejected`` are already decided. ``needs_review``,
    low confidence, and any financial effect still require that decision.
    """

    if status in EXTRACTION_REVIEW_DECISIONS:
        return False
    if status == "needs_review" or is_low_confidence(confidence):
        return True
    return has_financial_effect(extracted_fields, document_invoice_id)


def awaiting_review(status: str) -> bool:
    """An approver may accept or reject these statuses."""

    return status in AWAITING_REVIEW_STATUSES


def unattended_status(
    status: str,
    *,
    confidence: Decimal | float | None,
    extracted_fields: Mapping[str, object] | None,
    document_invoice_id: str | None,
    proposed_status: str | None = None,
) -> str:
    """Status a read, seed, or background job may store.

    Those paths do not accept or reject. A proposed decision is ignored.
    A low-confidence or financial row is also left unchanged when some
    other status was proposed for it.
    """

    proposed = status if proposed_status is None else proposed_status
    if proposed != status and (
        proposed in EXTRACTION_REVIEW_DECISIONS
        or requires_human_review(
            status=status,
            confidence=confidence,
            extracted_fields=extracted_fields,
            document_invoice_id=document_invoice_id,
        )
    ):
        return status
    return proposed


def _contains_financial_key(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if _key_is_financial(str(key)) or _contains_financial_key(nested):
                return True
        return False
    if isinstance(value, list):
        return any(_contains_financial_key(item) for item in value)
    return False


def _key_is_financial(key: str) -> bool:
    parts = {
        part
        for part in "".join(
            character if character.isalnum() else "_" for character in key.lower()
        ).split("_")
        if part
    }
    return bool(parts & _FINANCIAL_TOKENS)
