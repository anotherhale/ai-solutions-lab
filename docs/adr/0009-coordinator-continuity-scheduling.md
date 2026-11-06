# ADR 0009: Coordinator continuity scheduling

## Status

Accepted — 2026-11-05

## Context

Cloud agents exit after a run. Pull requests often remain open waiting for human
review. GraphQL auto-merge frequently returns errors such as “Pull request is in
clean status” while `autoMergeRequest` stays null. The activity log recorded progress
but did not schedule the next task or survive pytest migration downgrades on a shared
database.

## Decision

- Add **`development_ops.coordinator_tasks`** (Alembic `0010`) for runtime task
  state alongside the existing activity log.
- Maintain a machine-readable backlog at **`data/coordinator/backlog.yaml`**; human
  narrative stays in `ENGINEERING_BACKLOG.md`.
- Implement scheduling and reconciliation in **`libs/development_ops`** with
  `CoordinatorEngine.tick()`.
- Store operational telemetry in database **`wasatch_development_ops`**, separate from
  **`wasatch_test`**, so migration tests do not drop activity rows.
- Auto-merge uses **GraphQL `enablePullRequestAutoMerge` only**; failures are recorded
  and do not block other tasks.

## Consequences

- Open PRs on FIN-2 / FIN-3 must not prevent starting independent tasks (for example
  documentation or debt) when concurrency allows.
- Feature branches that add Alembic `0010` must renumber when this revision merges
  first.
- Coordinators run `scripts/coordinator_tick.sh` on startup and after each PR opened.
