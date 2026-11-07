# Coordinator continuity

Autonomous development must keep moving when pull requests stay open, auto-merge
cannot be enabled, or cloud agents exit after a single run.

## Root cause (previous behavior)

1. **Operating model** — [AGENT_OPERATING_MODEL.md](../architecture/AGENT_OPERATING_MODEL.md)
   told agents to open a pull request and **stop**, without selecting the next
   independent backlog item.
2. **No scheduler** — Phase 2 added the Development Activity Log (events only).
   Nothing reconciled GitHub state, dependencies, or outstanding assignments.
3. **PR-merge coupling** — Follow-up work was often triggered manually or implied
   by merge webhooks instead of a coordinator **tick** that inspects open PRs and
   the backlog together.
4. **Activity log durability** — Recording through `WASATCH_DATABASE_URL` pointed
   at the same database pytest downgrades for migration tests, which could drop
   `development_ops` and make early lifecycle events disappear.

## Current behavior

The coordinator runs as a **tick** (library, CLI, or `scripts/coordinator_tick.sh`):

1. Sync `data/coordinator/backlog.yaml` into `development_ops.coordinator_tasks`.
2. Optionally reclaim in-flight tasks whose lease expired (see [Recovery](#recovery)).
3. List open pull requests (via `gh` when available) and refresh task status.
4. Optionally attempt **GraphQL** `enablePullRequestAutoMerge` (squash only) for green pull
   requests targeting `ai-dev`. Record the exact error when `autoMergeRequest` stays null;
   **do not block** unrelated tasks.
5. Select the next **eligible** task (respecting `depends_on` and
   `DEVELOPMENT_OPS_MAX_CONCURRENT`). Open PRs on other tasks do not serialize the
   entire backlog.
6. Persist `coordinator.recovery`, `coordinator.scheduled`, and `task.selected`
   events before Slack notification.

### Implementation slots

Concurrency is measured by **implementation slots**, not by open pull requests. Only a task in
`in_progress` consumes a slot. A task whose pull request is open (`pr_open`) or awaiting merge
(`awaiting_merge`) has already released its implementer, so it never blocks new work. This is why
three open pull requests do not consume three slots.

A task is claimed with a single conditional `UPDATE`, so two concurrent ticks cannot own the same
task. The losing tick records a skipped duplicate assignment and continues. Each claim sets a
**lease** (`DEVELOPMENT_OPS_LEASE_SECONDS`, default 900). A live run extends it with a heartbeat;
`mark_merged` and `mark_blocked` clear ownership and release the slot.

### Merge safety

Autonomy integrates only into **`ai-dev`** ([ADR 0010](../adr/0010-autonomous-integration-branch.md)).
The auto-merge gate is enforced in `github_client`:

- the base branch must be `ai-dev`; a pull request targeting `main` or any other branch is refused;
- the status check rollup must be green — `CheckRun` (GitHub Actions) and `StatusContext` (legacy
  commit statuses) are both classified, and an empty rollup is unknown, never green;
- merged and closed-without-merge pull requests are refused.

A task whose pull request is closed without merge is marked `blocked` for human attention instead
of being recorded as merged.

### Isolated child worktrees (Phase C — implemented and wired in)

Each autonomous task runs in its own Git worktree and branch, cut from the latest
`origin/ai-dev`. The coordinator creates the worktree itself and launches the child with
`workspace.working_dir` set to it and `worktree: false`. The agent runtime's built-in worktree
isolation is deliberately **not** used: it starts from the repository default branch (`main`) and
server-derives the path and branch, so it cannot be pinned to `ai-dev` or to a coordinator-chosen
location.

| Concern | Where | State |
|---|---|---|
| Create/reuse worktree from `origin/ai-dev`; branch `cursor/<task-id>` | `development_ops.worktrees.WorktreeManager` | Implemented, unit-tested |
| Build conversation payload bound to the worktree (`worktree: false`) | `development_ops.child_agents` | Implemented, unit-tested |
| Order register → prepare → launch → PR → cleanup | `development_ops.task_worktrees.TaskWorktreeOrchestrator` | Implemented, integration-tested |
| Registry of task/branch/worktree/conversation | `development_ops.agent_worktrees` (migration `0014`) | Implemented, integration-tested |
| Cleanup only after verified merge + clean tree | `TaskWorktreeOrchestrator.cleanup_after_merge` (re-verifies via `verify_pull_request_merged`) | Implemented, integration-tested |
| Coordinator loop uses it | `development_ops.coordinator_engine` (`coordinator tick --worktrees`) | Implemented, end-to-end tested |
| CLI subcommands | `development-ops worktree list\|status\|prepare\|launch\|cleanup` | Implemented, integration-tested |
| Decision recorded in an ADR | `docs/adr/0012-isolated-worktrees-for-child-agents.md` | Written |

Concurrency: two tasks get distinct paths (`<worktree_root>/<repo>/<task-id>`) and branches, so
there is no shared writable directory. A per-task `fcntl` advisory lock (`WorktreeManager.task_lock`)
serializes `prepare` and `cleanup`, and the registry's unique constraints on branch and worktree path
back it at the database. A second `prepare` for the same task is idempotent.

Failure handling: a failed launch marks the registry row `failed` and leaves the worktree in place;
`recover_interrupted()` returns tasks in `preparing`/`failed` (never a task whose child was launched)
so the coordinator can re-drive them, and the next `launch` reuses the existing worktree. A duplicate
launch returns the existing conversation instead of starting a second child.

Merge verification: cleanup never trusts a caller-supplied boolean. `cleanup_after_merge` requires the
recorded pull request to exist, be merged, and target `ai-dev`; an unverifiable or wrong-branch merge
fails closed and leaves the worktree in place. GitHub remains the only authority on merge status.

The coordinator prepares worktrees automatically, but launching a real (paid) child conversation is an
explicit operator action: `development-ops worktree launch` requires `--agent-settings`. See
[../architecture/AGENT_OPERATING_MODEL.md](../architecture/AGENT_OPERATING_MODEL.md) and ADR 0012.

### Recovery

| Variable | Purpose |
|---|---|
| `DEVELOPMENT_OPS_RECLAIM_STALE=1` | Release in-flight tasks whose lease expired. A live run with a fresh heartbeat is not touched |
| `DEVELOPMENT_OPS_TASK_ID` | Resume an in-flight task instead of picking a new one |
| `DEVELOPMENT_OPS_LEASE_SECONDS` | Lease length for a claim (default 900) |
| `DEVELOPMENT_OPS_DISABLE_GITHUB=1` | Offline tick using backlog + persisted state only |

### Databases

| Database | Role |
|---|---|
| `wasatch` / `wasatch_test` | Wasatch API synthetic data and pytest |
| `wasatch_development_ops` | Activity log + coordinator state (never downgraded by pytest) |

Prepare locally:

```bash
python3 scripts/prepare_development_ops_database.py
export DEVELOPMENT_OPS_RUN_ID="$(uuidgen)"
export DEVELOPMENT_OPS_GITHUB_REPOSITORY=anotherhale/ai-solutions-lab
scripts/coordinator_tick.sh
```

## Slack

Continue posting meaningful events to `#ai-development`. Persist first, confirm
delivery with `development-ops-record confirm-slack` when using MCP.

## Human intervention still required

- Pull request **review** and ruleset enforcement on `ai-dev`
- **Auto-merge** when GraphQL returns errors such as “Pull request is in clean status”
- **Merge** of coordinated pull requests (agents never REST-merge)
- Backlog edits in `ENGINEERING_BACKLOG.md` and `data/coordinator/backlog.yaml`
- Resolving Alembic revision ordering when feature branches both add migrations
