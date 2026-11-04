"""Relational retrieval over persisted customer history and procedure files."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from wasatch_api.ai.application.ports import EmbeddingPort
from wasatch_api.customer_service.domain.retrieval import (
    INTERACTION,
    MESSAGE,
    SUPPORT_TICKET,
    WORK_ORDER,
    HistoryPassage,
    ProcedurePage,
    RetrievalResult,
)
from wasatch_api.customer_service.infrastructure.procedure_corpus import (
    ProcedureCorpus,
)
from wasatch_api.customer_service.infrastructure.procedure_embeddings import (
    ProcedureEmbeddingRepository,
)
from wasatch_api.shared.database.models import (
    InteractionORM,
    MessageORM,
    SupportTicketORM,
    WorkOrderORM,
)


class RelationalTextRetrieval:
    """Retrieval adapter.

    History is a relational read of one customer's tickets, messages,
    interactions, and work orders. Procedure pages are matched from the
    synthetic file corpus. When those pages have stored vectors, the match
    is ordered by that column. The history query stays.
    """

    def __init__(
        self,
        session: Session,
        procedures: ProcedureCorpus,
        embeddings: EmbeddingPort | None = None,
    ) -> None:
        self.session = session
        self.procedures = procedures
        self.embeddings = embeddings
        self._vectors = ProcedureEmbeddingRepository(session)

    def retrieve_for_ticket(self, ticket_id: str) -> RetrievalResult | None:
        ticket = self.session.scalar(
            select(SupportTicketORM)
            .options(
                selectinload(SupportTicketORM.customer),
                selectinload(SupportTicketORM.messages),
            )
            .where(SupportTicketORM.business_id == ticket_id)
        )
        if ticket is None:
            return None
        customer_key = ticket.customer_id
        history = (
            *_ticket_passages(self._tickets(customer_key)),
            *_message_passages(self._messages(customer_key)),
            *_interaction_passages(self._interactions(customer_key)),
            *_work_order_passages(self._work_orders(customer_key)),
        )
        inquiry = _inquiry_text(ticket)
        return RetrievalResult(
            support_ticket_id=ticket.business_id,
            customer_id=ticket.customer.business_id,
            history=history,
            procedures=self._order_with_stored_vectors(
                self.procedures.matching_pages(inquiry),
                inquiry,
            ),
        )

    def _order_with_stored_vectors(
        self, pages: tuple[ProcedurePage, ...], inquiry: str
    ) -> tuple[ProcedurePage, ...]:
        if not pages or self.embeddings is None:
            return pages
        stored = self._vectors.stored_among(tuple(page.id for page in pages))
        if not stored:
            return pages
        embedded = self.embeddings.embed((inquiry,))
        if len(embedded) != 1:
            return pages
        ordered = self._vectors.order_by_similarity(stored, embedded[0].vector)
        by_id = {page.id: page for page in pages}
        ranked = [
            by_id[procedure_id] for procedure_id in ordered if procedure_id in by_id
        ]
        seen = {page.id for page in ranked}
        return tuple(ranked + [page for page in pages if page.id not in seen])

    def _tickets(self, customer_key) -> list[SupportTicketORM]:
        return list(
            self.session.scalars(
                select(SupportTicketORM)
                .where(SupportTicketORM.customer_id == customer_key)
                .order_by(SupportTicketORM.business_id)
            ).all()
        )

    def _messages(self, customer_key) -> list[MessageORM]:
        return list(
            self.session.scalars(
                select(MessageORM)
                .join(
                    SupportTicketORM,
                    MessageORM.support_ticket_id == SupportTicketORM.id,
                )
                .where(SupportTicketORM.customer_id == customer_key)
                .order_by(MessageORM.business_id)
            ).all()
        )

    def _interactions(self, customer_key) -> list[InteractionORM]:
        return list(
            self.session.scalars(
                select(InteractionORM)
                .where(InteractionORM.customer_id == customer_key)
                .order_by(InteractionORM.business_id)
            ).all()
        )

    def _work_orders(self, customer_key) -> list[WorkOrderORM]:
        return list(
            self.session.scalars(
                select(WorkOrderORM)
                .options(selectinload(WorkOrderORM.tasks))
                .where(WorkOrderORM.customer_id == customer_key)
                .order_by(WorkOrderORM.business_id)
            ).all()
        )


def _inquiry_text(ticket: SupportTicketORM) -> str:
    messages = sorted(ticket.messages, key=lambda row: (row.sent_at, row.business_id))
    return _lines(ticket.subject, *(message.body for message in messages))


def _ticket_passages(rows: list[SupportTicketORM]) -> tuple[HistoryPassage, ...]:
    return tuple(
        HistoryPassage(
            source=SUPPORT_TICKET, source_id=row.business_id, text=row.subject
        )
        for row in rows
    )


def _message_passages(rows: list[MessageORM]) -> tuple[HistoryPassage, ...]:
    return tuple(
        HistoryPassage(source=MESSAGE, source_id=row.business_id, text=row.body)
        for row in rows
    )


def _interaction_passages(rows: list[InteractionORM]) -> tuple[HistoryPassage, ...]:
    return tuple(
        HistoryPassage(source=INTERACTION, source_id=row.business_id, text=row.summary)
        for row in rows
    )


def _work_order_passages(rows: list[WorkOrderORM]) -> tuple[HistoryPassage, ...]:
    return tuple(
        HistoryPassage(
            source=WORK_ORDER,
            source_id=row.business_id,
            text=_work_order_text(row),
        )
        for row in rows
    )


def _work_order_text(row: WorkOrderORM) -> str:
    task_lines = [task.description for task in row.tasks]
    return _lines(
        row.summary,
        row.description,
        row.completion_notes,
        row.cancelled_reason,
        row.reopen_reason,
        *task_lines,
    )


def _lines(*parts: str | None) -> str:
    return "\n".join(part.strip() for part in parts if part and part.strip())
