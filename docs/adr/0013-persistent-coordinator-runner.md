# ADR 0013: Persistent coordinator runner with single-workstation ownership

- Status: Accepted
- Date: 2026-11-07

## Context

The coordinator's scheduling cycle is implemented as a one-shot tick
(`development-ops-record coordinator tick`). On the Mac mini laboratory host it
was driven by a shell script and a short-lived scheduled job. That works for a
single reconciliation but has no durable process identity, no restart recovery,
no lease heartbeat while idle between ticks, and no operator-facing health
surface.

Phase B of the coordinator roadmap requires a long-running, restart-safe runner
that repeatedly executes the existing tick, recovers from interruption, keeps
task and run state consistent, and exposes operational health. It must not
introduce a second scheduling implementation, and it must not activate Phase D
concurrent child-agent orchestration.

Constraints:

- The laboratory host is a single Mac mini. There is no cluster.
- The coordinator already owns atomic task claims and leases in PostgreSQL
  (`coordinator_tasks`), so correctness must not depend on the runner process
  staying alive.
- `development_ops` telemetry and the operational database must be preserved;
  tests must use disposable databases only.
- launchd does not load interactive shell initialization files.

## Decision

Add a persistent runner in `libs/development_ops/src/development_ops/runner.py`
that owns only process lifecycle. It:

1. Calls the existing `CoordinatorEngine.tick` through an injected callable on a
   single thread, so ticks can never overlap. Scheduling policy stays in the
   engine; the runner adds no scheduling logic.
2. Uses a configurable poll interval, installs SIGTERM/SIGINT handlers for
   graceful shutdown, and treats a transient tick failure as recoverable: it is
   logged and recorded, then the loop continues.
3. Writes structured JSON logs suitable for launchd `StandardErrorPath`.
4. Records lifecycle milestones (`run.started`, `run.completed`,
   `coordinator.recovery`, `coordinator.scheduled`, `blocker.reported`) in
   `development_ops.activity_events` through the existing recorder.

Single-instance ownership uses an `flock` on a dedicated lock file
(`instance_lock.py`), not a PID file. A PID file cannot prove ownership: the
process may have exited or the PID may be recycled. The kernel releases the
`flock` when the owning process dies, so a crash never leaves a permanent lock,
and stale PID metadata is diagnostic only.

Startup recovery reconciles interrupted runs and expired leases using the
existing repository methods (`reclaim_expired_leases`, `recover_interrupted`).
It is idempotent: a second pass over already-reclaimed rows is a no-op. Tasks
awaiting PR review, checks, or merge are preserved, a closed-but-unmerged PR
blocks the task rather than being treated as merged, and a worktree is removed
only after GitHub confirms the specific PR merged.

Pause is durable state in a JSON file under the runner state directory, so it
survives a restart. A paused tick still reconciles GitHub PR state and cleans up
merged worktrees, but passes a concurrency limit of zero so no new task is
claimed. Running work is never destroyed.

launchd integration is a template LaunchAgent plist plus a launcher script that
builds the environment explicitly. Nothing installs or activates the agent as
part of CI or the PR workflow.

## Alternatives Considered

- **A PID file for single-instance protection.** Rejected: PID reuse and stale
  files make it unreliable. Used only as diagnostic metadata alongside `flock`.
- **A system-wide `launchd` daemon (`/Library/LaunchDaemons`).** Rejected: the
  coordinator runs as the developer user and needs that user's Git and GitHub
  credentials. A user-level LaunchAgent is the correct scope.
- **A database advisory lock for single-instance protection.** Deferred: the
  current model is explicitly single-workstation. A database lock would be the
  natural extension if the coordinator ever runs on more than one host, but it
  adds a connection-holding failure mode the laboratory does not yet need.
- **A cron job re-running the one-shot tick.** Rejected: no durable ownership,
  no heartbeat, overlapping invocations are possible, and there is no health
  surface.
- **A second scheduling loop inside the runner.** Rejected: it would duplicate
  the engine and risk divergent scheduling decisions.

## Consequences

Benefits:

- The coordinator runs continuously, survives restarts, and recovers abandoned
  work without operator intervention.
- Ownership, health, and pause state are inspectable and durable.
- The runner is testable without a live model provider or GitHub: the tick,
  recovery, and heartbeat are injected callables.

Costs and limitations:

- The locking model is **single-workstation**. It gives no protection across
  machines; running two coordinators on two hosts against one database is not
  supported by this mechanism.
- The runner is single-threaded by design. Phase D concurrency, when authorized,
  must introduce its own model rather than threading this loop.
- A paused runner still holds the instance lock, so pause is not a way to run a
  second runner.
- Live launchd installation and long-duration operation on the Mac mini are not
  verified by the test suite; only the process behavior is.

## Related

- ADR 0009: coordinator continuity scheduling.
- ADR 0010: autonomous integration branch and merge safety.
- ADR 0011: test database isolation.
- ADR 0012: isolated Git worktrees for child agents.
