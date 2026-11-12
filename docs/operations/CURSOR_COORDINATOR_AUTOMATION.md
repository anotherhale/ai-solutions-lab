# Cursor automation — coordinator entrypoint

Automation **AI Solutions Lab — Continue Development**
(`cdb207fb-d865-11f1-ba91-f63b1661ac50`) should **not** pick backlog items by prose alone.
It must invoke the coordinator script first.

## Primary command

```bash
scripts/coordinator_automation_entrypoint.sh
```

Before the entrypoint, reconcile the working tree with `origin/develop` when the
automation branch lags integration (`git fetch origin develop` and merge or rebase).
The tick reads `data/coordinator/backlog.yaml` from the working tree; a stale catalog
marks completed work as still active and hides open pull requests from scheduling.

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

## Independent code review

Keep Bugbot / review automations **separate**. They must not select backlog tasks or run coordinator tick.
