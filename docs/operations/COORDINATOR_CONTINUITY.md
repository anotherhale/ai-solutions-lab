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
2. List open pull requests (via `gh` when available) and refresh task status.
3. Optionally attempt **GraphQL** `enablePullRequestAutoMerge` (squash only).
   Record the exact error when `autoMergeRequest` stays null; **do not block**
   unrelated tasks.
4. Select the next **eligible** task (respecting `depends_on` and
   `DEVELOPMENT_OPS_MAX_CONCURRENT`). Only tasks with runtime status `in_progress`
   (an agent is implementing) count toward the concurrency limit. Tasks in `pr_open`
   awaiting human review do not. Open PRs on other tasks do not serialize the entire
   backlog.
5. Persist `coordinator.recovery`, `coordinator.scheduled`, and `task.selected`
   events before Slack notification.

### Recovery

| Variable | Purpose |
|---|---|
| `DEVELOPMENT_OPS_RECLAIM_STALE=1` | Release in-progress assignments owned by another `DEVELOPMENT_OPS_RUN_ID` |
| `DEVELOPMENT_OPS_TASK_ID` | Resume an in-flight task instead of picking a new one |
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

- Pull request **review** and ruleset enforcement on `develop`
- **Auto-merge** when GraphQL returns errors such as “Pull request is in clean status”
- **Merge** of coordinated pull requests (agents never REST-merge)
- Backlog edits in `ENGINEERING_BACKLOG.md` and `data/coordinator/backlog.yaml`
- Resolving Alembic revision ordering when feature branches both add migrations
- Closing **superseded** pull requests that only touched `data/coordinator/backlog.yaml`
  after a consolidated catalog change merged

## Superseded catalog-only pull requests

After [pull request #61](https://github.com/anotherhale/ai-solutions-lab/pull/61)
(`COORD-CATALOG-2`), these open pull requests repeat merged-marker catalog edits. A
human may close them without merging:

| Pull request | Superseded by |
|---|---|
| [#53](https://github.com/anotherhale/ai-solutions-lab/pull/53) | [#58](https://github.com/anotherhale/ai-solutions-lab/pull/58) (`COORD-PR-SLOT-1`, on `develop`) |
| [#55](https://github.com/anotherhale/ai-solutions-lab/pull/55) | [#61](https://github.com/anotherhale/ai-solutions-lab/pull/61) / [#62](https://github.com/anotherhale/ai-solutions-lab/pull/62) |
| [#57](https://github.com/anotherhale/ai-solutions-lab/pull/57) | [#61](https://github.com/anotherhale/ai-solutions-lab/pull/61) |
| [#59](https://github.com/anotherhale/ai-solutions-lab/pull/59) | [#61](https://github.com/anotherhale/ai-solutions-lab/pull/61) |
| [#60](https://github.com/anotherhale/ai-solutions-lab/pull/60) | [#61](https://github.com/anotherhale/ai-solutions-lab/pull/61) |

Agents must not open additional catalog-only branches for those merges.
