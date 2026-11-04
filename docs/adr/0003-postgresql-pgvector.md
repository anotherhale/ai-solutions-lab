# ADR 0003: PostgreSQL and pgvector

- Status: Accepted
- Date: 2026-11-03
- Updated: 2026-11-04

## Context

Wasatch Business Systems laboratory applications need relational records for customers, work orders, invoices, approvals, and audit events. They also need vector search for knowledge retrieval and document similarity.

A separate vector database would add another moving part before the first use case is implemented.

## Decision

Use PostgreSQL as the system of record and pgvector in the same database instance for embeddings and similarity search.

Redis remains the intended cache and short-lived coordination store. It is not the source of truth for business records.

Local PostgreSQL with pgvector is provisioned by Docker Compose. The first migration enables the `vector` extension. Revision `0006` adds the first embedding column, `procedure_page_embeddings.embedding`. It is `vector(8)`, the width returned by the laboratory embedding port. That default is the deterministic fake adapter. Domain code does not choose a different width. The column stores synthetic procedure page text only. Document version bytes are not in the repository and are not embedded. Unaccepted, `needs_review`, low-confidence, and financial extractions are not written into this index. The fake vectors are not a trusted semantic model. There is no second vector database.

## Alternatives Considered

- **A dedicated vector database.** Deferred. It may be justified later if retrieval volume or isolation needs exceed PostgreSQL.
- **SQLite for the laboratory.** Rejected as the target store. It would hide operational issues that matter when the same design is taken to an SMB client.
- **Document-only persistence.** Rejected. The business processes are relational and require constraints, transactions, and auditability.

## Consequences

- Local Compose and later Azure Database for PostgreSQL can share one mental model.
- Schema migrations and embedding storage share this database. The first embedding column is `procedure_page_embeddings.embedding`.
- Operational simplicity is favored over specialized vector features. Redis and n8n are not part of this column.
- The first relational slice and local Compose environment exist.
- WF-1 stores one follow-up visit in this database. Accepting a document extraction still does not post a payment or change an invoice. Confirming or canceling the visit does not either. OPS-1 traces the API host and does not add a cloud database.
