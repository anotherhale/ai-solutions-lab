# Database Mapping

This document describes how the first Wasatch FastAPI slice persists synthetic laboratory data.

JSON Schema remains the canonical **external** contract. SQLAlchemy maps a subset of those entities to PostgreSQL. Pydantic validates HTTP responses. Domain dataclasses carry application read models.

```text
JSON Schema  →  fixture files  →  seed loader  →  SQLAlchemy  →  PostgreSQL
                                      ↑
                               domain/application
                                      ↓
                                 Pydantic HTTP
```

No production database has been deployed. Local PostgreSQL is provided by Docker Compose.

## Persistence strategy

| Concern | Choice |
|---|---|
| Internal primary key | UUID |
| External API identifier | Existing business id (`cust_0001`, `wo_0001`) stored uniquely as `business_id` |
| Money | Not mapped in this slice. Future finance tables will use `NUMERIC(12,2)` plus a currency column |
| Timestamps | `TIMESTAMPTZ` |
| Addresses | Discrete columns, not JSON documents |
| Lists of enumerations | PostgreSQL `TEXT[]` (employee certifications) |
| Flexible documents | Deferred. JSONB is reserved for later extraction payloads |
| Vectors | `CREATE EXTENSION vector` is applied now; no embedding columns yet |

## Tables in this slice

| Table | Source fixture | Notes |
|---|---|---|
| `customers` | `customers.json` | `primary_contact_id` is a deferred FK to `contacts` |
| `contacts` | `contacts.json` | |
| `service_locations` | `service_locations.json` | |
| `employees` | `employees.json` | `role_id` and `team_id` are stored as strings; Role/Team tables are deferred |
| `equipment` | `equipment.json` | |
| `work_orders` | `work_orders.json` | `support_ticket_id` and `invoice_id` are strings until those modules exist |
| `work_order_assignments` | `assigned_employee_ids` | Many-to-many |
| `work_order_equipment` | `equipment_ids` | Many-to-many |
| `work_order_tasks` | `work_order_tasks.json` | |
| `appointments` | `appointments.json` | Self-FK `replaces_appointment_id` |

## Deferred entities

Not mapped yet: Role, Team, Invoice, InvoiceLine, Payment, Document, DocumentVersion, DocumentExtraction, SupportTicket, Message, Interaction, ApprovalRequest, AuditEvent.

Add them in later slices with the same UUID + `business_id` pattern. Do not load `data/fixtures/quality-issues/` into this database.

## Contract layers

| Layer | Responsibility |
|---|---|
| JSON Schema (`data/schemas/v1`) | External data contract and fixture shape |
| Domain dataclasses | In-process business records for read use cases |
| Application queries | Pagination, filters, not-found rules |
| SQLAlchemy | Persistence adapter |
| Pydantic | HTTP request/response models |

Do not treat SQLAlchemy models as API contracts. Do not treat Pydantic models as the source of fixture truth.
