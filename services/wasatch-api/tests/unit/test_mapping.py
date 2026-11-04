from __future__ import annotations

import uuid
from datetime import UTC, datetime

from wasatch_api.customers.infrastructure.mapping import customer_from_orm
from wasatch_api.shared.database.models import CustomerORM


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
