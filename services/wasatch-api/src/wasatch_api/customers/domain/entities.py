"""Customer-kernel domain records used by application services."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(frozen=True)
class Address:
    line1: str
    city: str
    state: str
    postal_code: str
    country: str
    line2: str | None = None


@dataclass(frozen=True)
class Contact:
    id: str
    customer_id: str
    first_name: str
    last_name: str
    contact_role: str
    is_primary: bool
    status: str
    title: str | None = None
    email: str | None = None
    phone: str | None = None


@dataclass(frozen=True)
class ServiceLocation:
    id: str
    customer_id: str
    name: str
    address: Address
    site_type: str
    timezone: str
    status: str
    access_notes: str | None = None
    square_footage: int | None = None


@dataclass(frozen=True)
class CustomerSummary:
    id: str
    legal_name: str
    trade_name: str | None
    account_number: str
    status: str
    customer_type: str


@dataclass
class Customer:
    id: str
    legal_name: str
    account_number: str
    status: str
    customer_type: str
    billing_address: Address
    payment_terms: str
    service_agreement: str
    created_at: datetime
    updated_at: datetime
    trade_name: str | None = None
    billing_email: str | None = None
    billing_phone: str | None = None
    agreement_expires_on: date | None = None
    primary_contact_id: str | None = None
    notes: str | None = None
    contacts: list[Contact] = field(default_factory=list)
    service_locations: list[ServiceLocation] = field(default_factory=list)


@dataclass
class ServiceLocationDetail:
    location: ServiceLocation
    customer: CustomerSummary
