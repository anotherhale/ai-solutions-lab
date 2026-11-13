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

## Amendment — one task lifecycle and merge readiness (2026-11-13)

## Status

Accepted — 2026-11-13

## Context

Coordinator task state was spread across ad-hoc transitions: catalog statuses
(`pending`, `in_progress`, `merged`, `blocked`) did not name an assigned-but-not-started
task or a pull request that is open and green. Two PRs against the same catalog row
(the `pr_open` work) diverged, and a stale catalog row could regress a task that GitHub
had already merged. Merge readiness was conflated with auto-merge eligibility, so a
clean pull request that GitHub refuses to auto-merge looked like a failure.

## Decision

- Define **one lifecycle** for `coordinator_tasks.status` and the backlog catalog:
  `pending → assigned → in_progress → pr_open → merge_ready → merged`, with `blocked`
  as a side state (Alembic `0013` widens the check constraint).
- Make **catalog sync monotonic**: the later of the current runtime status and the
  catalog status wins, and `merged`/`blocked` are terminal, so a stale row never
  reopens a merged task.
- Treat **merge readiness** as a property of the change (green required checks, no
  conflict, still open), independent of whether GitHub accepts
  `enablePullRequestAutoMerge`. A refusal such as “Pull request is in clean status”
  marks the task `merge_ready`, not failed, and never authorizes a direct merge or a
  bypass of branch rules.
- A task that already carries an open pull request is never dispatched again.
- One variable (`DEVELOPMENT_OPS_INTEGRATION_BRANCH`) governs both the catalog sync
  source and the delegation target, so a run never integrates on a different branch
  than the one it read catalog state from.

## Consequences

- Open pull requests awaiting human review (`pr_open`, `merge_ready`) do not consume an
  implementation slot, so they never serialize the backlog.
- The merge lifecycle state stays visible in `coordinator_tasks` and the catalog for
  the coordinator and the human reviewing the queue.
- Feature branches that add Alembic `0013` must renumber if another revision merges
  first.
