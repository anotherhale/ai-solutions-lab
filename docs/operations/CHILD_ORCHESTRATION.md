# Concurrent child-agent orchestration operations

Phase D lets the persistent coordinator runner drive a small, bounded number of
child agents at once. A child works in its own Git worktree (ADR 0012) on the
integration branch `ai-dev`, and the coordinator owns the child's lifecycle —
launch, monitoring, recovery, and reconciliation with GitHub.

This is **not** a production service and **not** an Azure deployment. It runs on
the single Mac mini laboratory host, as the developer user, and it can spend
money: a launched child runs a paid model. Treat enabling it as a deliberate,
reversible operator action.

See [ADR 0015](../adr/0015-bounded-concurrent-child-agents.md) for the design
decision and [COORDINATOR_RUNNER.md](COORDINATOR_RUNNER.md) for the runner that
drives the tick.

## Enablement is a durable operator decision

Child execution is **disabled by default**. Enabling it is a durable database
write, not an environment variable:

```bash
# Inspect current state and child health (read-only).
development-ops-record child status

# Turn paid child execution ON. Records who and why.
development-ops-record child enable --by "$USER" --reason "Phase D validation"

# Turn it OFF. Stops new launches; active children are NOT killed.
development-ops-record child disable --by "$USER" --reason "pause spend"
```

- An environment variable (`DEVELOPMENT_OPS_ENABLE_CHILD_EXECUTION`) can express
  *intent* but can never enable execution on its own. `resolve_enabled` requires
  the durable flag.
- `disable` stops new launches only. An active child keeps its slot and runs to a
  safe state; disable is not an emergency stop.
- The flag lives in `development_ops.orchestration_settings` and survives
  restarts.

## Concurrency policy

| Setting | Default | Meaning |
|---|---|---|
| `DEVELOPMENT_OPS_MAX_CONCURRENT_CHILDREN` | `2` | Simultaneous children. Hard ceiling for the phase is `2`. |
| `DEVELOPMENT_OPS_CHILD_HEARTBEAT_SECONDS` | `300` | Expected progress cadence per child. |
| `DEVELOPMENT_OPS_CHILD_STALL_SECONDS` | `1800` | Silence past this window marks a child `stalled`. Must exceed the heartbeat. |
| `DEVELOPMENT_OPS_CHILD_LAUNCH_TIMEOUT_SECONDS` | `60` | Bound on a single child launch. |
| `DEVELOPMENT_OPS_CHILD_MAX_ATTEMPTS` | `3` | Maximum launch attempts per task. |
| `DEVELOPMENT_OPS_CHILD_AGENT_SETTINGS` | unset | JSON agent settings forwarded to the agent-server. Required to launch. |

Validation fails fast: a concurrency above the ceiling, a stall window not
greater than the heartbeat, or a non-positive timeout is rejected with a clear
message rather than silently misbehaving.

The limit is enforced **twice** — in policy and by a partial unique index in the
database — so two racing ticks cannot oversubscribe. A child that has opened a PR
(`pr_open`, `awaiting_merge`) frees its slot while its merge is pending; only
`claimed`, `launch_pending`, `running`, and `stalled` hold a slot.

## Child lifecycle

```
queued → claimed → launch_pending → running → stalled
                                      │         │
                                      ▼         ▼
                                   pr_open ──► awaiting_merge ──► merged
                                      │
                                      ▼
                              failed / completed / cancelled
```

- **stalled** keeps its slot: a live-but-idle child has not been proven dead.
  Only an *ambiguous* child (stalled and lease expired) is escalated to an
  operator with `operator_intervention`.
- **pr_open / awaiting_merge** are launched and must never be relaunched.
- **merged** is reached only when GitHub confirms the PR merged into `ai-dev`.
  A closed-unmerged PR is preserved and escalated, never treated as success.
- Illegal transitions raise `ChildTransitionConflict`; the repository uses
  conditional compare-and-set updates so a stale coordinator cannot corrupt
  state.

## What a tick does

1. **Monitor** active children. A rising conversation event count is progress.
   Unchanged past the stall window → `stalled`. A missing conversation or a
   server error → escalate. A transient unreachable server is not a failure.
2. **Recover** interrupted work. A child whose conversation exists is adopted,
   never relaunched. A child registered but never launched returns to the launch
   queue. A child already stalled with an expired lease is escalated.
3. **Launch** ready tasks up to the limit, through the existing worktree-first
   ordering. A launch runs in a worker bounded by the launch timeout; a timeout
   fails the row *with operator intervention* rather than retrying a launch that
   may have created an orphan conversation.
4. **Reconcile** child state with task state and with GitHub.

## Operator intervention

A child flagged `operator_intervention` needs a human. Inspect it with
`development-ops-record child status` (JSON includes `children[]` with state,
attempt, conversation id, worktree, PR number, and notes). Typical causes:

- **Missing conversation** — the agent-server returned no conversation id, or a
  conversation recorded at launch no longer exists. The child may have died.
- **Launch timeout** — the launch exceeded `launch_timeout_seconds`. A
  conversation may exist but was not recorded; do not retry blindly.
- **Stalled and lease expired** — no live signal and no heartbeat. The child may
  have crashed mid-edit.
- **Closed-unmerged PR** — the child's PR was closed without merging. The work is
  preserved for review.

Resolve the underlying cause (stop an orphaned conversation, inspect the
worktree) before clearing the flag. Cleanup still refuses any worktree whose PR
GitHub does not confirm merged (ADR 0012).

## Troubleshooting

- **Nothing launches after `child enable`** — check `child status`: an active
  child may be occupying every slot, `DEVELOPMENT_OPS_CHILD_AGENT_SETTINGS` may
  be unset (launch fails with operator intervention), or the agent-server may be
  unreachable.
- **A child is `stalled`** — confirm the child is truly idle (its conversation
  may still be working). A healthy child advances its event count; a stuck one
  does not. Escalated stalls are never auto-relaunched.
- **`launch returned no conversation id`** — the agent-server accepted the
  request but returned no id. The execution is failed with intervention; inspect
  the agent-server before retrying.
- **Two children, one task** — impossible by construction: a partial unique index
  forbids two active executions for one task.

## Verification status

Lifecycle, concurrency accounting, stall detection, recovery, launch timeout and
retry, transition conflicts, persistence guards, and the CLI are covered by
automated tests against disposable databases. **Live concurrent child execution
against a real agent-server and paid model is not exercised by the test suite**
and must be confirmed deliberately on the host.
