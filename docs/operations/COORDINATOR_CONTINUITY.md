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
