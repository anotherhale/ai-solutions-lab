# Architecture Decision Records

This directory records significant, durable choices for AI Solutions Lab.

## Numbering

- Files use the pattern `NNNN-short-kebab-title.md`.
- Numbers are sequential four-digit integers: `0001`, `0002`, `0003`.
- Do not reuse a number after an ADR is published.
- Do not renumber ADRs to close gaps. Supersede instead.

## Status Values

| Status | Meaning |
|---|---|
| Proposed | The decision is the current intent, but implementation or validation is outstanding |
| Accepted | The decision has been implemented or otherwise validated in this repository |
| Superseded | A later ADR replaced this decision. Link the replacement |
| Rejected | The option was considered and will not be used. Record why |

Mark a decision `Proposed` when the repository only contains the written choice. Do not mark `Accepted` merely because the document exists.

## Required Sections

Every ADR must include:

1. **Title** and number
2. **Status** and date
3. **Context** — the problem, constraint, or forcing event
4. **Decision** — the choice in definite language
5. **Alternatives considered** — options that were rejected or deferred, and why
6. **Consequences** — benefits, costs, and follow-up work

Optional sections such as related ADRs or rollback notes may be added when they help a future reader.

## Template

```markdown
# ADR NNNN: Title

- Status: Proposed
- Date: YYYY-MM-DD

## Context

## Decision

## Alternatives Considered

## Consequences
```

## Current Records

| ID | Title | Status |
|---|---|---|
| [0001](0001-modular-monolith-architecture.md) | Modular monolith architecture | Accepted |
| [0002](0002-python-fastapi-backend.md) | Python and FastAPI backend | Accepted |
| [0003](0003-postgresql-pgvector.md) | PostgreSQL and pgvector | Accepted |
| [0004](0004-openai-provider-abstraction.md) | OpenAI provider abstraction | Accepted |
| [0005](0005-docker-compose-local-development.md) | Docker Compose local development | Accepted |
| [0006](0006-laboratory-actor-development-only.md) | Laboratory actor adapter is development-only | Accepted |
| [0007](0007-starlette-security-remediation.md) | Starlette security advisories and remediation plan | Proposed |
