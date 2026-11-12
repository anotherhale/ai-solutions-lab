# Cursor automation — coordinator entrypoint

Automation **AI Solutions Lab — Continue Development**
(`cdb207fb-d865-11f1-ba91-f63b1661ac50`) should **not** pick backlog items by prose alone.
It must invoke the coordinator script first.

## Primary command

```bash
scripts/coordinator_automation_entrypoint.sh
```

When the automation working tree is not on `develop`, the entrypoint fetches
`origin/develop` and checks out `data/coordinator/backlog.yaml` and
`libs/development_ops` from that ref before the tick. A stale catalog marks
completed work as active and can hide open pull requests from scheduling.

That script:

1. Migrates/prepares `wasatch_development_ops` (never `wasatch_test`).
2. Runs `development-ops-record coordinator tick` (GitHub reconcile, optional auto-merge).
3. Emits JSON including `selected_task_id` when a new assignment is made.
4. Records `task.delegated` when a task is handed to an implementation agent.

## Automation prompt (coordinator)

Use this as the **first step** of the Continue Development automation (implementation agent is separate):

```
You are the AI Solutions Lab development coordinator. From the repository root, run:
  scripts/coordinator_automation_entrypoint.sh
Parse the JSON output. If delegation is "implementation", spawn or continue work on that
task_id only. Do not wait for open PRs to merge before selecting work. Do not assign the
same task twice: if tick reports skipped duplicate or no selected_task_id, stop without
opening redundant branches. Record milestones via scripts/coordinator_activity.sh.
Post summaries to Slack #ai-development after persistence, then confirm-slack.
Never merge PRs yourself; use GraphQL enablePullRequestAutoMerge only via coordinator tick.
```

## Triggers (recommended)

| Trigger | Action |
|---|---|
| Scheduled (e.g. every 6h) | Run entrypoint; delegate if task selected |
| GitHub PR opened / synchronized | Run entrypoint (ignore merge-wait) |
| GitHub PR merged to `develop` | Run entrypoint to unblock dependents |
| CI completed (Repository Validation) | Run entrypoint to retry auto-merge + schedule |

Avoid duplicate triggers on the same commit within 15 minutes (use idempotency keys in activity log).

## When the tick selects no task

`{"delegation":"none","reason":"no eligible task"}` is normal when:

1. **Stale catalog** — the working tree was not on `develop` and the entrypoint had not yet synced
   `data/coordinator/backlog.yaml` from `origin/develop`. After
   [COORD-BACKLOG-3](https://github.com/anotherhale/ai-solutions-lab/pull/64), the entrypoint syncs
   automatically; operators should still merge that pull request so every host picks up the change.
2. **Open pull requests awaiting human review** — catalog `in_progress` rows with runtime `pr_open`
   are not reassigned. Concurrency slots count only `in_progress`, not `pr_open` (COORD-PR-SLOT-1).
3. **Held dependencies** — the next `pending` task (for example `STATUS-2`) stays queued until named
   dependencies reach `merged` in the catalog or runtime.

The coordinator should post a short `#ai-development` summary listing open integration pull requests
and the held task ids, then stop without opening duplicate branches. When the backlog lacks
independent `pending` work, add well-scoped items to `ENGINEERING_BACKLOG.md` and
`data/coordinator/backlog.yaml` in one catalog pull request rather than improvising assignments.

## Independent code review

Keep Bugbot / review automations **separate**. They must not select backlog tasks or run coordinator tick.
