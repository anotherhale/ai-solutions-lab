from __future__ import annotations

import uuid
from datetime import UTC, datetime

from wasatch_api.customer_service.infrastructure.mapping import (
    interaction_from_orm,
    support_ticket_from_orm,
)
from wasatch_api.customers.infrastructure.mapping import customer_from_orm
from wasatch_api.shared.database.models import (
    ContactORM,
    CustomerORM,
    EmployeeORM,
    InteractionORM,
    MessageORM,
    ServiceLocationORM,
    SupportTicketORM,
    WorkOrderORM,
)
from wasatch_api.work_orders.infrastructure.mapping import work_order_from_orm


def test_customer_mapping_uses_business_id() -> None:
    now = datetime(2026, 1, 8, 17, 0, tzinfo=UTC)
    row = CustomerORM(
        id=uuid.uuid4(),
        business_id="cust_0001",
        legal_name="Pioneer Plaza Property Group LLC",
        trade_name="Pioneer Plaza",
        account_number="WBS-00001",
        status="active",
        customer_type="property_manager",
        billing_line1="48 W 300 S",
        billing_line2="Suite 400",
        billing_city="Salt Lake City",
        billing_state="UT",
        billing_postal_code="84101",
        billing_country="US",
        payment_terms="net_30",
        service_agreement="full_coverage",
        created_at=now,
        updated_at=now,
        contacts=[],
        service_locations=[],
    )
    customer = customer_from_orm(row, include_children=True)
    assert customer.id == "cust_0001"
    assert customer.billing_address.city == "Salt Lake City"
    assert customer.contacts == []


def test_support_ticket_mapping_uses_business_ids() -> None:
    now = datetime(2026, 4, 8, 9, 30, tzinfo=UTC)
    customer = CustomerORM(id=uuid.uuid4(), business_id="cust_0004")
    contact = ContactORM(id=uuid.uuid4(), business_id="con_0008")
    location = ServiceLocationORM(id=uuid.uuid4(), business_id="loc_0007")
    employee = EmployeeORM(id=uuid.uuid4(), business_id="emp_0006")
    work_order = WorkOrderORM(id=uuid.uuid4(), business_id="wo_0007")
    ticket = SupportTicketORM(
        id=uuid.uuid4(),
        business_id="tkt_0007",
        customer_id=customer.id,
        contact_id=contact.id,
        service_location_id=location.id,
        work_order_id=work_order.id,
        status="awaiting_customer",
        priority="normal",
        channel="portal",
        subject="Waiting on approval",
        assigned_employee_id=employee.id,
        opened_at=now,
        created_at=now,
        updated_at=now,
        related_document_ids=["doc_0008"],
    )
    message = MessageORM(
        id=uuid.uuid4(),
        business_id="msg_0016",
        support_ticket_id=ticket.id,
        direction="outbound",
        channel="email",
        body="We can be on site Thursday.",
        status="pending_approval",
        author_employee_id=employee.id,
        requires_approval=True,
        approval_request_id="apr_0001",
        sent_at=now,
        created_at=now,
        updated_at=now,
    )
    ticket.customer = customer
    ticket.contact = contact
    ticket.service_location = location
    ticket.work_order = work_order
    ticket.assigned_employee = employee
    ticket.messages = [message]
    message.support_ticket = ticket
    message.author_employee = employee
    mapped = support_ticket_from_orm(ticket, detail=True)
    assert mapped.id == "tkt_0007"
    assert mapped.customer_id == "cust_0004"
    assert mapped.work_order_id == "wo_0007"
    assert mapped.assigned_employee_id == "emp_0006"
    assert mapped.related_document_ids == ["doc_0008"]
    assert mapped.messages[0].id == "msg_0016"
    assert mapped.messages[0].author_employee_id == "emp_0006"
    assert mapped.messages[0].approval_request_id == "apr_0001"
    assert mapped.messages[0].support_ticket_id == "tkt_0007"
    assert mapped.messages[0].id != str(message.id)


def test_work_order_mapping_uses_ticket_business_id() -> None:
    now = datetime(2026, 4, 5, 9, 30, tzinfo=UTC)
    customer = CustomerORM(id=uuid.uuid4(), business_id="cust_0003")
    location = ServiceLocationORM(id=uuid.uuid4(), business_id="loc_0004")
    ticket = SupportTicketORM(
        id=uuid.uuid4(),
        business_id="tkt_0004",
        customer_id=customer.id,
        status="assigned",
        priority="high",
        channel="sms",
        subject="Service request",
        opened_at=now,
        created_at=now,
        updated_at=now,
        related_document_ids=[],
    )
    row = WorkOrderORM(
        id=uuid.uuid4(),
        business_id="wo_0004",
        customer_id=customer.id,
        service_location_id=location.id,
        support_ticket_id=ticket.id,
        status="scheduled",
        priority="high",
        work_type="repair",
        summary="No heat",
        opened_at=now,
        created_at=now,
        updated_at=now,
    )
    row.customer = customer
    row.service_location = location
    row.support_ticket = ticket
    row.assigned_employees = []
    mapped = work_order_from_orm(row, detail=False)
    assert mapped.id == "wo_0004"
    assert mapped.customer_id == "cust_0003"
    assert mapped.support_ticket_id == "tkt_0004"
    assert mapped.support_ticket_id != str(ticket.id)


def test_interaction_mapping_uses_business_ids() -> None:
    now = datetime(2026, 4, 2, 9, 30, tzinfo=UTC)
    customer = CustomerORM(id=uuid.uuid4(), business_id="cust_0001")
    contact = ContactORM(id=uuid.uuid4(), business_id="con_0001")
    employee = EmployeeORM(id=uuid.uuid4(), business_id="emp_0007")
    ticket = SupportTicketORM(
        id=uuid.uuid4(),
        business_id="tkt_0001",
        customer_id=customer.id,
        status="opened",
        priority="normal",
        channel="phone",
        subject="Rooftop unit",
        opened_at=now,
        created_at=now,
        updated_at=now,
        related_document_ids=[],
    )
    work_order = WorkOrderORM(id=uuid.uuid4(), business_id="wo_0001")
    row = InteractionORM(
        id=uuid.uuid4(),
        business_id="ixn_0001",
        customer_id=customer.id,
        contact_id=contact.id,
        support_ticket_id=ticket.id,
        work_order_id=work_order.id,
        channel="phone",
        occurred_at=now,
        summary="Logged inbound request and created work order.",
        employee_id=employee.id,
        outcome="answered",
        created_at=now,
        updated_at=now,
    )
    row.customer = customer
    row.contact = contact
    row.support_ticket = ticket
    row.work_order = work_order
    row.employee = employee
    mapped = interaction_from_orm(row)
    assert mapped.id == "ixn_0001"
    assert mapped.customer_id == "cust_0001"
    assert mapped.support_ticket_id == "tkt_0001"
    assert mapped.work_order_id == "wo_0001"
    assert mapped.employee_id == "emp_0007"
    assert mapped.outcome == "answered"
