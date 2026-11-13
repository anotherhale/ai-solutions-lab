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
| [0007](0007-starlette-security-remediation.md) | Starlette security advisories and remediation plan | Accepted |
| [0008](0008-development-activity-log-schema.md) | Development activity log schema | Accepted |
| [0009](0009-coordinator-continuity-scheduling.md) | Coordinator continuity scheduling | Accepted |
| [0010](0010-autonomous-integration-branch.md) | Autonomous integration on `ai-dev` and merge safety | Accepted |
| [0011](0011-test-database-isolation.md) | Test database isolation for operational telemetry | Accepted |
| [0012](0012-isolated-worktrees-for-child-agents.md) | Isolated Git worktrees for coordinator child agents | Accepted |
| [0013](0013-persistent-coordinator-runner.md) | Persistent coordinator runner with single-workstation ownership | Accepted |
| [0014](0014-autonomous-integration-branch-consolidation.md) | One authoritative integration branch and coordinator-owned backlog catalog | Accepted |
| [0015](0015-bounded-concurrent-child-agents.md) | Bounded concurrent child-agent orchestration | Accepted |
| [0016](0016-branch-promotion-policy.md) | Branch roles and deliberate promotion flow | Accepted |
