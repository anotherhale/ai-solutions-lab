# ADR 0008: Development activity log schema

## Status

Accepted — 2026-11-04

## Context

Autonomous agents and coordinators need a durable, searchable record of development
work that is separate from Wasatch synthetic business tables. Humans expect
notifications in Slack `#ai-development`. The laboratory already runs PostgreSQL
for the Wasatch slice via Docker Compose and Alembic.

Introducing a second database, external SaaS log store, or independently deployed
microservice would add operational cost without a demonstrated requirement.

## Decision

- Store development telemetry in PostgreSQL schema **`development_ops`**, table
  **`activity_events`**, migrated through the existing Wasatch API Alembic chain
  (revision `0009`).
- Implement persistence and reporting in **`libs/development_ops`**, imported by
  scripts and agents; do not expose a public write HTTP API.
- Persist every event before Slack notification; update only Slack delivery columns
  after confirmed delivery.
- Use standardized event types, severities, UUID identifiers, optional
  idempotency keys, run/task correlation, JSONB metadata, and GitHub reference
  columns.

## Alternatives considered

- **Wasatch `public` tables.** Rejected. Mixes laboratory product data with
  operational telemetry and complicates retention policies.
- **External observability SaaS as system of record.** Rejected for now. No
  subscription or egress requirement is justified; PostgreSQL already exists.
- **Slack as source of truth.** Rejected. Messages are not structured, queryable,
  or idempotent.

## Consequences

- Alembic migrations and pytest integration tests must cover `development_ops`.
- Agents should log milestones, not chain-of-thought or every tool invocation.
- Slack failures must not roll back persisted events.
- Follow-up work may add coordinator hooks and richer reporting; schema changes
  require a new Alembic revision.
