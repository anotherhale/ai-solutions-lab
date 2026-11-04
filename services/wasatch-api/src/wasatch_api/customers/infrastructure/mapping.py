"""ORM to domain mapping for the customer kernel."""

from __future__ import annotations

from wasatch_api.customers.domain.entities import (
    Address,
    Contact,
    Customer,
    CustomerSummary,
    ServiceLocation,
)
from wasatch_api.shared.database.models import (
    ContactORM,
    CustomerORM,
    ServiceLocationORM,
)


def address_from_billing(row: CustomerORM) -> Address:
    return Address(
        line1=row.billing_line1,
        line2=row.billing_line2,
        city=row.billing_city,
        state=row.billing_state,
        postal_code=row.billing_postal_code,
        country=row.billing_country,
    )


def address_from_location(row: ServiceLocationORM) -> Address:
    return Address(
        line1=row.line1,
        line2=row.line2,
        city=row.city,
        state=row.state,
        postal_code=row.postal_code,
        country=row.country,
    )


def contact_from_orm(row: ContactORM, customer_business_id: str) -> Contact:
    return Contact(
        id=row.business_id,
        customer_id=customer_business_id,
        first_name=row.first_name,
        last_name=row.last_name,
        title=row.title,
        email=row.email,
        phone=row.phone,
        contact_role=row.contact_role,
        is_primary=row.is_primary,
        status=row.status,
    )


def location_from_orm(
    row: ServiceLocationORM, customer_business_id: str
) -> ServiceLocation:
    return ServiceLocation(
        id=row.business_id,
        customer_id=customer_business_id,
        name=row.name,
        address=address_from_location(row),
        site_type=row.site_type,
        timezone=row.timezone,
        access_notes=row.access_notes,
        square_footage=row.square_footage,
        status=row.status,
    )


def customer_summary_from_orm(row: CustomerORM) -> CustomerSummary:
    return CustomerSummary(
        id=row.business_id,
        legal_name=row.legal_name,
        trade_name=row.trade_name,
        account_number=row.account_number,
        status=row.status,
        customer_type=row.customer_type,
    )


def customer_from_orm(row: CustomerORM, *, include_children: bool) -> Customer:
    primary = None
    if include_children and row.primary_contact_id:
        for contact in row.contacts:
            if contact.id == row.primary_contact_id:
                primary = contact.business_id
                break
    customer = Customer(
        id=row.business_id,
        legal_name=row.legal_name,
        trade_name=row.trade_name,
        account_number=row.account_number,
        status=row.status,
        customer_type=row.customer_type,
        billing_address=address_from_billing(row),
        billing_email=row.billing_email,
        billing_phone=row.billing_phone,
        payment_terms=row.payment_terms,
        service_agreement=row.service_agreement,
        agreement_expires_on=row.agreement_expires_on,
        primary_contact_id=primary,
        notes=row.notes,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
    if include_children:
        customer.contacts = [
            contact_from_orm(item, row.business_id) for item in row.contacts
        ]
        customer.service_locations = [
            location_from_orm(item, row.business_id) for item in row.service_locations
        ]
    return customer
