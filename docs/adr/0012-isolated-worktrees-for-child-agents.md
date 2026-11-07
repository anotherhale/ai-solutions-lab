# ADR 0012: Isolated Git worktrees for coordinator child agents

- Status: Accepted
- Date: 2026-11-06

## Context

The coordinator schedules one backlog task at a time onto the integration branch
`ai-dev` (ADR 0009, ADR 0010). Until now an implementing child agent worked in
the coordinator's own checkout. Two problems follow.

1. **Shared working tree.** A child that checks out a feature branch, edits
   files, and commits changes the coordinator's checkout. A second child cannot
   run concurrently without both fighting over `HEAD` and the index, and the
   coordinator's own uncommitted work is at risk.
2. **No durable link.** Nothing recorded which branch or working directory
   belonged to which task, so cleanup could not tell a finished worktree from a
   live one, and a crashed launch left an orphan branch.

Git worktrees solve the isolation problem: one repository, one branch per
worktree, separate directories, a shared object store. The open question was how
the coordinator should own the lifecycle safely — especially cleanup, which
deletes a branch and a directory.

## Decision

The coordinator isolates each task in its own Git worktree and owns the
lifecycle through a small, explicit module set.

- `development_ops.worktrees.WorktreeManager` performs the Git operations:
  `prepare` creates `cursor/<task-id>` from `origin/ai-dev` in a worktree outside
  the primary checkout; `cleanup` removes it; `status` reports filesystem state.
  A per-task `fcntl` advisory lock (`task_lock`) serializes `prepare` and
  `cleanup` so two coordinators cannot race the same task.
- `development_ops.task_worktrees.TaskWorktreeOrchestrator` owns the ordering:
  prepare worktree → launch child → record pull request → clean up after merge.
- `development_ops.agent_worktrees` is the durable registry. It is the single
  source of truth for the task→branch→worktree→conversation link. Scheduling
  state stays in `coordinator_tasks`; the two concerns are not merged.
- **GitHub is the only authority on merge status.** Cleanup calls
  `verify_pull_request_merged`, which requires the recorded pull request to
  exist, be merged, and target `ai-dev`. A caller-supplied boolean is never
  trusted, and an unverifiable merge fails closed.
- `WorktreeState` contains only states a real transition produces:
  `preparing`, `launched`, `pr_open`, `merged`, `failed`. There are no
  placeholder states.

The coordinator exposes the capability through `coordinator tick --worktrees`
and a `development-ops worktree {list,status,prepare,cleanup}` command group. The
CLI and the engine call the same application services; neither reimplements the
lifecycle.

## Alternatives Considered

- **`git clone` per task.** Duplicates the object store, cannot share the
  coordinator's fetched refs, and makes `ai-dev` divergence more likely.
- **A single shared checkout with branch switching.** The status quo; it blocks
  concurrency and endangers the coordinator's own work.
- **Trusting a caller-supplied `pr_merged` boolean.** Simpler, but it lets a bug
  or a stale caller delete unmerged work. Rejected: verification is cheap and
  the failure mode is destructive.
- **A second PR-state store in the registry.** Rejected. GitHub already owns
  merge status; mirroring it invites drift. The registry records the pull request
  *number* the coordinator observed, not its state.
- **Reclaiming worktrees whose child was launched.** Rejected. A live child may
  be mid-edit; recovery only re-drives tasks that were never launched or whose
  launch failed.

## Consequences

- Children run concurrently without sharing `HEAD`, and the coordinator's
  checkout is untouched (verified by test).
- Cleanup is safe by construction: it cannot delete a branch that is not merged
  into `ai-dev`, and it refuses a dirty worktree.
- A crashed launch is recoverable: the registry row survives, the worktree is
  reused on retry, and duplicate launches return the existing conversation
  instead of starting a second child.
- The coordinator holds a filesystem lock per task. On a single workstation this
  is sufficient; a distributed deployment would need a database-backed lock
  instead (not required today).
- Worktrees live outside the repository (default
  `/tmp/ai-solutions-lab-worktrees`, overridable via
  `DEVELOPMENT_OPS_WORKTREE_ROOT`). Operators must ensure that path is on a
  local filesystem and is cleaned up after crashes.
- Migration `0014_agent_worktrees` adds the registry table. It extends the
  `development_ops` schema; operational telemetry isolation (ADR 0011) is
  unchanged.

## Related Records

- ADR 0009 — Coordinator continuity scheduling (slot accounting, leases).
- ADR 0010 — Autonomous integration on `ai-dev` and merge safety.
- ADR 0011 — Test database isolation for operational telemetry.
