# ADR 0003: PostgreSQL and pgvector

- Status: Accepted
- Date: 2026-11-03

## Context

Wasatch Business Systems laboratory applications need relational records for customers, work orders, invoices, approvals, and audit events. They also need vector search for knowledge retrieval and document similarity.

A separate vector database would add another moving part before the first use case is implemented.

## Decision

Use PostgreSQL as the system of record and pgvector in the same database instance for embeddings and similarity search.

Redis remains the intended cache and short-lived coordination store. It is not the source of truth for business records.

Local PostgreSQL with pgvector is provisioned by Docker Compose. The first migration enables the `vector` extension. Embedding columns are still deferred.

## Alternatives Considered

- **A dedicated vector database.** Deferred. It may be justified later if retrieval volume or isolation needs exceed PostgreSQL.
- **SQLite for the laboratory.** Rejected as the target store. It would hide operational issues that matter when the same design is taken to an SMB client.
- **Document-only persistence.** Rejected. The business processes are relational and require constraints, transactions, and auditability.

## Consequences

- Local Compose and later Azure Database for PostgreSQL can share one mental model.
- Schema migrations and embedding storage must be designed together.
- Operational simplicity is favored over specialized vector features.
- The first relational slice and local Compose environment now exist.
