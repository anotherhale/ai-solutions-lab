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
| Flexible documents | `audit_events.details` uses JSONB for the open audit map. Extraction payloads stay deferred |
| Vectors | `CREATE EXTENSION vector` is applied now; no embedding columns yet. The embedding port exists and does not fill one |

## Tables in this slice

| Table | Source fixture | Notes |
|---|---|---|
| `customers` | `customers.json` | `primary_contact_id` is a deferred FK to `contacts` |
| `contacts` | `contacts.json` | |
| `service_locations` | `service_locations.json` | |
| `roles` | `roles.json` | `is_approver` lives on the role. UUID primary key and unique `business_id` |
| `teams` | `teams.json` | `lead_employee_id` references `employees`. Team membership is not required to approve a message |
| `employees` | `employees.json` | `role_id` references `roles`; `team_id` references `teams`. An unmatched business id becomes NULL during upgrade; seed sets the fixture links |
| `equipment` | `equipment.json` | |
| `work_orders` | `work_orders.json` | `support_ticket_id` references `support_tickets.id`; `invoice_id` remains a string |
| `work_order_assignments` | `assigned_employee_ids` | Many-to-many |
| `work_order_equipment` | `equipment_ids` | Many-to-many |
| `work_order_tasks` | `work_order_tasks.json` | |
| `appointments` | `appointments.json` | Self-FK `replaces_appointment_id` |
| `support_tickets` | `support_tickets.json` | `related_document_ids` is `TEXT[]` of document business ids |
| `messages` | `messages.json` | `approval_request_id` references `approval_requests.id` |
| `interactions` | `interactions.json` | Optional links to a ticket and a work order |
| `approval_requests` | `approval_requests.json` | `subject_id` stays the subject's business id |
| `approval_decision_history` | `decision_history` on each approval | Child rows ordered by `position`; replaced when the approval is reseeded. The customer-message decision appends one row |
| `audit_events` | `audit_events.json` | Insert-only. No `updated_at`. Optional `approval_request_id` references `approval_requests.id`. `details` is JSONB for the open map; extraction payloads stay deferred. The customer-message decision inserts one row and does not update the message |

## Deferred entities

Not mapped yet: Invoice, InvoiceLine, Payment, Document, DocumentVersion, DocumentExtraction.

Add them in later slices with the same UUID + `business_id` pattern. Do not load `data/fixtures/quality-issues/` into this database.

## Retrieval

Ticket retrieval reads one customer's persisted text: ticket subjects, message bodies, interaction summaries, and work-order text (summary, description, completion notes, cancellation reason, reopen reason, and task descriptions). Procedure pages stay files under `data/documents/procedures/`. They are not rows in a document table and they are not seeded from `data/fixtures/valid/`. Matching is whole-word text search over the ticket subject and message bodies. There is no vector column and no second vector database. The embedding port can produce vectors, and this slice does not store them.

Revision `0002` downgrade copies ticket business ids back onto `work_orders.support_ticket_id` and drops the customer-service tables. Reload `data/fixtures/valid/` after that downgrade.

Revision `0003` downgrade copies approval business ids back onto `messages.approval_request_id`, then drops `audit_events`, `approval_decision_history`, and `approval_requests`. It does not `UPDATE` or `DELETE` individual audit rows; dropping the table is the schema rollback and is safe on the synthetic database. Reload `data/fixtures/valid/` after that downgrade. The database trigger `audit_events_insert_only` rejects row updates and deletes while the table exists.

Revision `0004` downgrade copies role and team business ids back onto `employees.role_id` and `employees.team_id`, then drops `teams` and `roles`. That is safe on the synthetic database. Reload `data/fixtures/valid/` after that downgrade. `is_approver` is not stored on `employees`.

## Contract layers

| Layer | Responsibility |
|---|---|
| JSON Schema (`data/schemas/v1`) | External data contract and fixture shape |
| Domain dataclasses | In-process business records for read use cases |
| Application queries | Pagination, filters, not-found rules |
| SQLAlchemy | Persistence adapter |
| Pydantic | HTTP request/response models |

Do not treat SQLAlchemy models as API contracts. Do not treat Pydantic models as the source of fixture truth.
