# ADR 0015: Bounded concurrent child-agent orchestration

- Status: Accepted
- Date: 2026-11-08

## Context

The coordinator schedules one backlog task per tick onto the integration branch
`ai-dev` (ADR 0009, ADR 0010). ADR 0012 gave each task an isolated Git worktree
and a durable task→branch→worktree→conversation link, but the coordinator still
launched at most one child and did not track a child's lifecycle after launch.

Phase D asks for **controlled concurrency**: run a small, bounded number of
child agents at once, keep each one observable, and recover or escalate safely
when a launch, a process, or a coordinator restart goes wrong. Concurrency
multiplies the ways a coordinator can lose track of work, so the design favors
conservatism over throughput.

The hard constraints that shaped this decision:

- A child runs a paid model. Concurrency must be capped by policy, not by
  whatever the operator happens to export.
- A coordinator restart must never double-run a task. A conversation that was
  created but not recorded is worse than one that never started.
- A live process is not evidence of progress. A child can be alive and stuck.
- Cleanup is destructive. It must remain gated on a verified merge (ADR 0012).

## Decision

Add a child-orchestration layer alongside scheduling. It owns a child's
lifecycle; scheduling continues to own which task runs.

### Domain: an explicit lifecycle and a small concurrency policy

- `development_ops.child_lifecycle` defines eleven states — `queued`, `claimed`,
  `launch_pending`, `running`, `stalled`, `failed`, `completed`, `pr_open`,
  `awaiting_merge`, `merged`, `cancelled` — and the legal transitions between
  them. `require_legal_transition` is enforced in the repository, so an illegal
  transition raises rather than silently corrupting state.
- Two state sets drive accounting. `ACTIVE_STATES` (`claimed`, `launch_pending`,
  `running`, `stalled`) consume a concurrency slot. `LAUNCHED_STATES` add
  `pr_open` and `awaiting_merge`: those have launched and must never be
  relaunched, but they no longer occupy a slot. A child that opened a PR frees
  its slot while its merge is pending.
- `development_ops.child_config` validates policy: concurrency defaults to **2**
  and is capped at a phase hard ceiling of **2**; the stall window must exceed
  the heartbeat; the launch timeout must be positive.

### Enablement is a durable operator decision, never an environment variable

`resolve_enabled` returns enabled only when the durable
`orchestration_settings.child_execution_enabled` flag is set by an operator
(`development-ops-record child enable`). An exported environment variable can
express *intent* but can never switch on paid execution. The flag is seeded
`false` by the migration and survives restarts.

### Persistence: one active execution per task, atomic transitions

- `child_executions` records every attempt; a **partial unique index**
  (`state IN ACTIVE_STATES`) enforces one active execution per task while
  preserving the history of failed, completed, and merged attempts.
- Every state change is a conditional compare-and-set
  (`UPDATE ... WHERE state = :expected`). A zero-row update raises
  `ChildTransitionConflict`, so two coordinators cannot both advance the same
  row. Progress is a monotonic `progress_seq`, advanced only on a *meaningful*
  signal.

### Application: launch, monitor, recover, and expose status

`ChildOrchestrator.tick` runs one pass and is idempotent:

1. **Monitor** every active child. A rising conversation event count is
   progress. An unchanged count past the stall window is `stalled` (it keeps its
   slot — it has not been proven dead). A missing conversation or a server error
   is escalated with `operator_intervention`, never silently relaunched. A
   transient unreachable server is not a failure.
2. **Recover** interrupted work. A child whose conversation exists is never
   relaunched; a child that was registered but never launched is returned to the
   launch queue. A child already stalled at tick start whose lease has also
   expired has no live signal and is escalated.
3. **Launch** ready tasks up to the limit, through the existing
   `TaskWorktreeOrchestrator` so the worktree-first ordering (ADR 0012) is
   preserved. The launch runs in a worker thread bounded by
   `launch_timeout_seconds`; a timeout fails the row *with operator
   intervention* rather than retrying a launch that may have created an orphan
   conversation.
4. **Reconcile** child state with task state (`pr_open`, `awaiting_merge`,
   `merged`) and with a closed-unmerged PR, which is preserved and escalated,
   never treated as success.

`development_ops.agent_server.AgentServerObserver` is a read-only probe of the
agent-server (`X-Session-API-Key`); it distinguishes reachable, missing, and
unreachable without ever logging a credential.

### CLI

`development-ops-record child status|enable|disable` exposes and controls the
capability. `status` is read-only; `enable`/`disable` write the durable flag.
Disabling stops new launches but never kills an active child.

## Alternatives Considered

- **A high or unbounded concurrency limit.** Rejected. Each child is a paid
  model call and a Git worktree; the phase ceiling is 2 until a demonstrated
  requirement justifies more.
- **Enabling via environment variable.** Rejected. It makes an accidental export
  spend money and hides the decision from the audit trail. The durable flag is
  explicit and recorded.
- **Treating a reachable process as "running".** Rejected. A stuck child would
  hold a slot forever. Progress requires a rising event count; a live-but-idle
  child is `stalled`.
- **Relaunching on stall.** Rejected. A stalled child may still be mid-edit;
  relaunching risks two agents on one branch. Ambiguity is escalated to the
  operator instead.
- **A separate `status` table.** Rejected. Child state belongs in
  `child_executions`; a mirror invites drift.
- **Retrying after a launch timeout.** Rejected. A timed-out launch may have
  created a conversation; retrying could orphan it. The row fails with operator
  intervention and no slot is reclaimed.
- **Merging child state into `coordinator_tasks`.** Rejected. Scheduling state
  and execution state are different concerns with different lifecycles;
  ADR 0012 already separated the worktree registry for the same reason.

## Consequences

- At most two children run at once, enforced in the database and in policy, so
  two racing ticks cannot oversubscribe.
- A coordinator restart never double-runs a task: a child with a recorded
  conversation is adopted, not relaunched.
- Stalled, missing, and ambiguous children surface to an operator instead of
  being guessed at, and the cleanup gate from ADR 0012 is untouched.
- Paid execution is off until an operator enables it, and the enable/disable
  decision is durable and auditable.
- The stall and launch timeouts are wall-clock based. On a single workstation
  this is sufficient; a distributed deployment would need a shared clock and a
  database-backed lease instead (not required today).
