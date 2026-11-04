"""Read use cases for support tickets, messages, and interactions."""

from __future__ import annotations

from wasatch_api.customer_service.domain.entities import (
    Interaction,
    Message,
    SupportTicket,
)
from wasatch_api.customer_service.infrastructure.repository import (
    CustomerServiceRepository,
)
from wasatch_api.shared.errors import NotFoundError
from wasatch_api.shared.pagination import (
    PageRequest,
    parse_page,
    validate_message_status,
    validate_support_ticket_status,
)


class CustomerServiceQueries:
    def __init__(self, repository: CustomerServiceRepository) -> None:
        self.repository = repository

    def list_support_tickets(
        self,
        *,
        page: int | None,
        page_size: int | None,
        customer_id: str | None,
        status: str | None,
        service_location_id: str | None,
        assigned_employee_id: str | None,
    ) -> tuple[list[SupportTicket], int, PageRequest]:
        request = parse_page(page, page_size)
        items, total = self.repository.list_support_tickets(
            request,
            customer_id=customer_id,
            status=validate_support_ticket_status(status),
            service_location_id=service_location_id,
            assigned_employee_id=assigned_employee_id,
        )
        return items, total, request

    def get_support_ticket(self, ticket_id: str) -> SupportTicket:
        ticket = self.repository.get_support_ticket(ticket_id)
        if ticket is None:
            raise NotFoundError(f"support ticket {ticket_id} was not found")
        return ticket

    def list_messages(
        self,
        *,
        page: int | None,
        page_size: int | None,
        support_ticket_id: str | None,
        status: str | None,
    ) -> tuple[list[Message], int, PageRequest]:
        request = parse_page(page, page_size)
        items, total = self.repository.list_messages(
            request,
            support_ticket_id=support_ticket_id,
            status=validate_message_status(status),
        )
        return items, total, request

    def get_message(self, message_id: str) -> Message:
        message = self.repository.get_message(message_id)
        if message is None:
            raise NotFoundError(f"message {message_id} was not found")
        return message

    def list_interactions(
        self,
        *,
        page: int | None,
        page_size: int | None,
        customer_id: str | None,
        support_ticket_id: str | None,
    ) -> tuple[list[Interaction], int, PageRequest]:
        request = parse_page(page, page_size)
        items, total = self.repository.list_interactions(
            request,
            customer_id=customer_id,
            support_ticket_id=support_ticket_id,
        )
        return items, total, request

    def get_interaction(self, interaction_id: str) -> Interaction:
        interaction = self.repository.get_interaction(interaction_id)
        if interaction is None:
            raise NotFoundError(f"interaction {interaction_id} was not found")
        return interaction
