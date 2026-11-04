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
| Flexible documents | `audit_events.details` and `document_extractions.extracted_fields` use JSONB. Extraction payloads stay untrusted until an approver accepts them. The review command does not post finance |
| Vectors | `CREATE EXTENSION vector` is applied in revision `0001`. Revision `0006` adds `procedure_page_embeddings.embedding` as `vector(8)`, the laboratory fake port's width. Only synthetic procedure text is stored. The vector is not a trusted model |

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
| `work_orders` | `work_orders.json` | `support_ticket_id` references `support_tickets.id`. `invoice_id` references `invoices.id` |
| `work_order_assignments` | `assigned_employee_ids` | Many-to-many |
| `work_order_equipment` | `equipment_ids` | Many-to-many |
| `work_order_tasks` | `work_order_tasks.json` | |
| `appointments` | `appointments.json` | Self-FK `replaces_appointment_id` |
| `support_tickets` | `support_tickets.json` | `related_document_ids` is `TEXT[]` of document business ids |
| `messages` | `messages.json` | `approval_request_id` references `approval_requests.id` |
| `interactions` | `interactions.json` | Optional links to a ticket and a work order |
| `approval_requests` | `approval_requests.json` | `subject_id` stays the subject's business id |
| `approval_decision_history` | `decision_history` on each approval | Child rows ordered by `position`; replaced when the approval is reseeded. The customer-message decision appends one row |
| `audit_events` | `audit_events.json` | Insert-only. No `updated_at`. Optional `approval_request_id` references `approval_requests.id`. `details` is JSONB for the open map. The customer-message decision and the extraction review each insert one row. Neither updates an audit event |
| `documents` | `documents.json` | UUID primary key and unique `business_id`. `invoice_id` stays a string. `current_version_id` references `document_versions`. No vector column |
| `document_versions` | `document_versions.json` | `storage_path` is a synthetic relative path. The bytes are not in the repository. Unique `(document_id, version_number)` |
| `document_extractions` | `document_extractions.json` | `extracted_fields` is JSONB. The review command updates `status`, `reviewed_by_employee_id`, `reviewed_at`, `review_notes`, and `updated_at`. It does not change `extracted_fields` or the document `invoice_id`. No vector column. Unaccepted, `needs_review`, low-confidence, and financial rows are not copied into `procedure_page_embeddings` |
| `procedure_page_embeddings` | `data/documents/procedures/` | Not seeded from `data/fixtures/valid/`. `embedding` is `vector(8)`. One row per synthetic procedure page after the fill service runs. Document version bytes are not stored |
| `follow_up_visits` | Created by the follow-up command, not by seed | One row per approved customer-message approval after a dispatcher opens it. Status is `unscheduled`, `confirmed`, or `cancelled`. No technician column, no appointment, and no vector column. Confirm and cancel do not post finance |
| `invoices` | `invoices.json` | UUID primary key and unique `business_id`. Money is numeric amount plus currency. `work_order_id` references `work_orders`. No posting command |
| `invoice_lines` | `invoice_lines.json` | `invoice_id` references `invoices`. Optional `work_order_id` references `work_orders` |
| `payments` | `payments.json` | `invoice_id` references `invoices`. Fixture status may already be `posted`. A read does not post a new payment |

## Deferred entities

No finance entity from `data/schemas/v1/finance/` remains unmapped. Do not load `data/fixtures/quality-issues/` into this database. File bytes for document versions are still not stored.

## Retrieval

Ticket retrieval reads one customer's persisted text: ticket subjects, message bodies, interaction summaries, and work-order text (summary, description, completion notes, cancellation reason, reopen reason, and task descriptions). Procedure pages stay files under `data/documents/procedures/`. They are not rows in `documents` and they are not seeded from `data/fixtures/valid/`. Matching starts from whole-word text search over the ticket subject and message bodies. When `procedure_page_embeddings` has a vector for a matched page, retrieval orders that match with the stored vector. There is no second vector database. The vectors are the fake port's output and are not a trusted semantic model.

Revision `0002` downgrade copies ticket business ids back onto `work_orders.support_ticket_id` and drops the customer-service tables. Reload `data/fixtures/valid/` after that downgrade.

Revision `0003` downgrade copies approval business ids back onto `messages.approval_request_id`, then drops `audit_events`, `approval_decision_history`, and `approval_requests`. It does not `UPDATE` or `DELETE` individual audit rows; dropping the table is the schema rollback and is safe on the synthetic database. Reload `data/fixtures/valid/` after that downgrade. The database trigger `audit_events_insert_only` rejects row updates and deletes while the table exists.

Revision `0004` downgrade copies role and team business ids back onto `employees.role_id` and `employees.team_id`, then drops `teams` and `roles`. That is safe on the synthetic database. Reload `data/fixtures/valid/` after that downgrade. `is_approver` is not stored on `employees`.

Revision `0005` downgrade drops `document_extractions`, `document_versions`, and `documents`. That is safe on the synthetic database. Reload `data/fixtures/valid/` after that downgrade. The revision does not add a vector column.

Revision `0006` downgrade drops `procedure_page_embeddings`. That is safe on the synthetic database. Procedure pages remain files. The revision does not embed document version bytes or extractions.

Revision `0007` downgrade drops `follow_up_visits`. That is safe on the synthetic database. It does not update or delete audit events. The insert-only trigger on `audit_events` stays in place. The revision does not add a vector column.

Revision `0008` downgrade copies invoice business ids back onto `work_orders.invoice_id`, then drops `payments`, `invoice_lines`, and `invoices`. That is safe on the synthetic database. Reload `data/fixtures/valid/` after that downgrade. `documents.invoice_id` stays a string. The revision does not post a payment or add a vector column.

## Contract layers

| Layer | Responsibility |
|---|---|
| JSON Schema (`data/schemas/v1`) | External data contract and fixture shape |
| Domain dataclasses | In-process business records for read use cases |
| Application queries | Pagination, filters, not-found rules |
| SQLAlchemy | Persistence adapter |
| Pydantic | HTTP request/response models |

Do not treat SQLAlchemy models as API contracts. Do not treat Pydantic models as the source of fixture truth.
