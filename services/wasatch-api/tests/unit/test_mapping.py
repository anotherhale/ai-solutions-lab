from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from wasatch_api.customer_service.infrastructure.mapping import (
    interaction_from_orm,
    support_ticket_from_orm,
)
from wasatch_api.customers.infrastructure.mapping import customer_from_orm
from wasatch_api.documents.infrastructure.mapping import document_from_orm
from wasatch_api.governance.infrastructure.mapping import (
    approval_from_orm,
    audit_event_from_orm,
)
from wasatch_api.shared.database.models import (
    ApprovalRequestORM,
    AuditEventORM,
    ContactORM,
    CustomerORM,
    DocumentExtractionORM,
    DocumentORM,
    DocumentVersionORM,
    EmployeeORM,
    InteractionORM,
    InvoiceORM,
    MessageORM,
    RoleORM,
    ServiceLocationORM,
    SupportTicketORM,
    TeamORM,
    WorkOrderORM,
)
from wasatch_api.work_orders.infrastructure.mapping import work_order_from_orm
from wasatch_api.workforce.infrastructure.mapping import (
    laboratory_actor_from_employee,
    role_from_orm,
    team_from_orm,
)


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
    approval = ApprovalRequestORM(
        id=uuid.uuid4(),
        business_id="apr_0001",
        action_type="send_customer_message",
        status="pending",
        requested_by_employee_id=employee.id,
        subject_type="message",
        subject_id="msg_0016",
        rationale="Overtime commitment needs manager approval.",
        requested_at=now,
        created_at=now,
        updated_at=now,
    )
    approval.requested_by = employee
    approval.reviewer = None
    approval.decision_history = []
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
        approval_request_id=approval.id,
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
    message.approval_request = approval
    mapped = support_ticket_from_orm(ticket, detail=True)
    assert mapped.id == "tkt_0007"
    assert mapped.customer_id == "cust_0004"
    assert mapped.work_order_id == "wo_0007"
    assert mapped.assigned_employee_id == "emp_0006"
    assert mapped.related_document_ids == ["doc_0008"]
    assert mapped.messages[0].id == "msg_0016"
    assert mapped.messages[0].author_employee_id == "emp_0006"
    assert mapped.messages[0].approval_request_id == "apr_0001"
    assert mapped.messages[0].approval_request is not None
    assert mapped.messages[0].approval_request.status == "pending"
    assert mapped.messages[0].approval_request.subject_id == "msg_0016"
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
    invoice = InvoiceORM(id=uuid.uuid4(), business_id="inv_0005")
    row.customer = customer
    row.service_location = location
    row.support_ticket = ticket
    row.invoice = invoice
    row.invoice_id = invoice.id
    row.assigned_employees = []
    mapped = work_order_from_orm(row, detail=False)
    assert mapped.id == "wo_0004"
    assert mapped.customer_id == "cust_0003"
    assert mapped.support_ticket_id == "tkt_0004"
    assert mapped.support_ticket_id != str(ticket.id)
    assert mapped.invoice_id == "inv_0005"
    assert mapped.invoice_id != str(invoice.id)


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


def test_approval_mapping_uses_business_ids() -> None:
    now = datetime(2026, 8, 2, 15, 10, tzinfo=UTC)
    requester = EmployeeORM(id=uuid.uuid4(), business_id="emp_0014")
    reviewer = EmployeeORM(id=uuid.uuid4(), business_id="emp_0001")
    row = ApprovalRequestORM(
        id=uuid.uuid4(),
        business_id="apr_0003",
        action_type="price_override",
        status="approved",
        requested_by_employee_id=requester.id,
        reviewer_employee_id=reviewer.id,
        subject_type="invoice",
        subject_id="inv_0011",
        rationale="Match quoted maintenance rate.",
        decision_notes="Approved at quoted rate.",
        requested_at=now,
        decided_at=now,
        created_at=now,
        updated_at=now,
    )
    row.requested_by = requester
    row.reviewer = reviewer
    row.decision_history = []
    mapped = approval_from_orm(row)
    assert mapped.id == "apr_0003"
    assert mapped.id != str(row.id)
    assert mapped.requested_by_employee_id == "emp_0014"
    assert mapped.reviewer_employee_id == "emp_0001"
    assert mapped.subject_id == "inv_0011"
    assert mapped.decision_history == ()


def test_audit_event_mapping_uses_business_ids() -> None:
    now = datetime(2026, 8, 19, 10, 45, tzinfo=UTC)
    actor = EmployeeORM(id=uuid.uuid4(), business_id="emp_0006")
    approval = ApprovalRequestORM(id=uuid.uuid4(), business_id="apr_0001")
    row = AuditEventORM(
        id=uuid.uuid4(),
        business_id="aud_0045",
        occurred_at=now,
        actor_type="employee",
        actor_employee_id=actor.id,
        action="approval.updated",
        subject_type="approval_request",
        subject_id="apr_0001",
        outcome="pending",
        approval_request_id=approval.id,
        details={"synthetic": True},
    )
    row.actor_employee = actor
    row.approval_request = approval
    mapped = audit_event_from_orm(row)
    assert mapped.id == "aud_0045"
    assert mapped.id != str(row.id)
    assert mapped.actor_employee_id == "emp_0006"
    assert mapped.approval_request_id == "apr_0001"
    assert mapped.subject_id == "apr_0001"
    assert mapped.details == {"synthetic": True}
    assert not hasattr(mapped, "updated_at")


def test_role_mapping_reads_is_approver_from_the_role() -> None:
    now = datetime(2026, 1, 5, 14, 0, tzinfo=UTC)
    role = RoleORM(
        id=uuid.uuid4(),
        business_id="role_0004",
        name="Dispatcher",
        department="dispatch",
        is_approver=False,
        description="Schedules technicians",
        created_at=now,
        updated_at=now,
    )
    employee = EmployeeORM(
        id=uuid.uuid4(),
        business_id="emp_0004",
        status="active",
        role=role,
    )
    mapped_role = role_from_orm(role)
    actor = laboratory_actor_from_employee(employee)
    assert mapped_role.id == "role_0004"
    assert mapped_role.id != str(role.id)
    assert mapped_role.is_approver is False
    assert actor.employee_id == "emp_0004"
    assert actor.role_id == "role_0004"
    assert actor.is_approver is False
    assert not hasattr(actor, "team_id")


def test_team_mapping_uses_lead_business_id() -> None:
    now = datetime(2026, 1, 5, 14, 10, tzinfo=UTC)
    lead = EmployeeORM(id=uuid.uuid4(), business_id="emp_0010")
    team = TeamORM(
        id=uuid.uuid4(),
        business_id="team_0001",
        name="Field Crew A",
        department="field_operations",
        service_area="Salt Lake County",
        lead_employee_id=lead.id,
        created_at=now,
        updated_at=now,
        lead=lead,
    )
    mapped = team_from_orm(team)
    assert mapped.id == "team_0001"
    assert mapped.id != str(team.id)
    assert mapped.lead_employee_id == "emp_0010"


def test_document_mapping_uses_business_ids() -> None:
    now = datetime(2026, 6, 2, 13, 0, tzinfo=UTC)
    reviewed = datetime(2026, 6, 8, 10, 0, tzinfo=UTC)
    customer = CustomerORM(id=uuid.uuid4(), business_id="cust_0003")
    location = ServiceLocationORM(id=uuid.uuid4(), business_id="loc_0004")
    uploader = EmployeeORM(id=uuid.uuid4(), business_id="emp_0007")
    reviewer = EmployeeORM(id=uuid.uuid4(), business_id="emp_0008")
    author = EmployeeORM(id=uuid.uuid4(), business_id="emp_0009")
    document = DocumentORM(
        id=uuid.uuid4(),
        business_id="doc_0004",
        title="Synthetic document 4",
        document_type="vendor_bill",
        status="needs_review",
        source="generated",
        mime_type="image/jpeg",
        untrusted=False,
        customer_id=customer.id,
        service_location_id=location.id,
        invoice_id="inv_0004",
        uploaded_by_employee_id=uploader.id,
        created_at=now,
        updated_at=now,
    )
    first = DocumentVersionORM(
        id=uuid.uuid4(),
        business_id="dv_0004",
        document_id=document.id,
        version_number=1,
        storage_path="synthetic/documents/doc_0004/v1.bin",
        checksum_sha256="a" * 64,
        byte_size=12548,
        created_by_employee_id=uploader.id,
        created_at=now,
    )
    current = DocumentVersionORM(
        id=uuid.uuid4(),
        business_id="dv_0031",
        document_id=document.id,
        version_number=2,
        storage_path="synthetic/documents/doc_0004/v2.bin",
        checksum_sha256="b" * 64,
        byte_size=15001,
        created_by_employee_id=author.id,
        created_at=reviewed,
    )
    extraction = DocumentExtractionORM(
        id=uuid.uuid4(),
        business_id="dx_0004",
        document_id=document.id,
        document_version_id=first.id,
        status="accepted",
        extractor="model",
        confidence=Decimal("0.8"),
        extracted_fields={
            "vendor_name": "Synthetic Vendor",
            "invoice_number": "V-0004",
        },
        reviewed_by_employee_id=reviewer.id,
        reviewed_at=reviewed,
        review_notes="Accepted for posting",
        extracted_at=now,
        created_at=now,
        updated_at=now,
    )
    document.customer = customer
    document.service_location = location
    document.work_order = None
    document.uploaded_by = uploader
    document.current_version = current
    document.current_version_id = current.id
    first.document = document
    first.created_by = uploader
    current.document = document
    current.created_by = author
    extraction.document = document
    extraction.document_version = first
    extraction.reviewed_by = reviewer
    document.versions = [first, current]
    document.extractions = [extraction]

    mapped = document_from_orm(document, detail=True)
    assert mapped.id == "doc_0004"
    assert mapped.id != str(document.id)
    assert mapped.customer_id == "cust_0003"
    assert mapped.service_location_id == "loc_0004"
    assert mapped.work_order_id is None
    assert mapped.invoice_id == "inv_0004"
    assert mapped.current_version_id == "dv_0031"
    assert mapped.current_version_id != str(current.id)
    assert mapped.uploaded_by_employee_id == "emp_0007"
    assert mapped.untrusted is False
    assert [item.id for item in mapped.versions] == ["dv_0004", "dv_0031"]
    assert mapped.versions[1].version_number == 2
    assert mapped.versions[1].created_by_employee_id == "emp_0009"
    assert mapped.versions[1].storage_path == "synthetic/documents/doc_0004/v2.bin"
    assert mapped.extractions[0].id == "dx_0004"
    assert mapped.extractions[0].id != str(extraction.id)
    assert mapped.extractions[0].document_version_id == "dv_0004"
    assert mapped.extractions[0].status == "accepted"
    assert mapped.extractions[0].confidence == 0.8
    assert mapped.extractions[0].reviewed_by_employee_id == "emp_0008"
    assert mapped.extractions[0].extracted_fields == {
        "vendor_name": "Synthetic Vendor",
        "invoice_number": "V-0004",
    }

    summary = document_from_orm(document, detail=False)
    assert summary.current_version_id == "dv_0031"
    assert summary.versions == []
    assert summary.extractions == []
