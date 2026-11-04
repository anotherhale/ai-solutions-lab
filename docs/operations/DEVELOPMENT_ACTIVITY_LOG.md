# Development Activity Log

Structured, append-only record of autonomous development work for AI Solutions Lab.
Wasatch synthetic business data stays in the `public` schema; operational development
telemetry lives in **`development_ops`**.

Slack **`#ai-development`** (channel ID `C0CFJDH7PTJ`, workspace
**wasatch-ai-solutions-lab**) is the human-readable notification surface. Missing
Slack delivery or missing database rows is **not** evidence that work succeeded.

## Schema

| Object | Purpose |
|---|---|
| `development_ops.activity_events` | Append-only events with JSONB metadata, GitHub refs, Slack delivery state |

Migration: `services/wasatch-api/alembic/versions/0009_development_ops_activity_log.py`.

### Event taxonomy

| Type | Typical use |
|---|---|
| `run.started` / `run.completed` / `run.failed` | Agent run lifecycle |
| `task.selected` / `task.delegated` | Coordinator/worker task flow |
| `implementation.milestone` | Meaningful implementation progress (not every tool call) |
| `test.started` / `test.completed` / `test.failed` | Verification milestones |
| `review.started` / `review.completed` | Review gates |
| `pr.opened` / `pr.updated` / `pr.merged` | GitHub pull request activity |
| `progress.report` / `blocker.reported` / `milestone.reached` | Status to humans |

Severities: `debug`, `info`, `notice`, `warning`, `error`, `critical`.

### Idempotency

Optional `idempotency_key` (unique). Replays return the existing row and do not
insert duplicates.

### Slack delivery fields

Events are **persisted before** Slack is attempted. Delivery columns may be updated
after insert; event content remains append-only.

| Status | Meaning |
|---|---|
| `pending` | Not yet delivered |
| `delivered` | Confirmed message timestamp recorded |
| `failed` | Attempt failed; event row retained |
| `skipped` | Notification intentionally disabled |
| `duplicate` | Idempotent Slack replay |

## Configuration

| Variable | Purpose |
|---|---|
| `WASATCH_DATABASE_URL` | PostgreSQL URL (same instance as Wasatch) |
| `DEVELOPMENT_OPS_SLACK_BOT_TOKEN` | Optional bot token for `chat.postMessage` automation |
| `DEVELOPMENT_OPS_SLACK_CHANNEL_ID` | Default `C0CFJDH7PTJ` |
| `DEVELOPMENT_OPS_REPORT_TZ` | Report timezone (default `America/Denver`) |

Cursor Cloud Agents with the authorized Slack MCP should:

1. Persist via `ActivityRecorder` (or SQL) first.
2. Post to `#ai-development` with MCP.
3. Call `ActivityRecorder.confirm_slack_delivery` with `channel_id` and `message_ts`.

Do not mark `delivered` without a confirmed timestamp.

## Library

Package: `libs/development_ops` (`development-ops` on `pip install -e`).

```python
from sqlalchemy.orm import Session
from development_ops.recorder import ActivityRecorder
from development_ops.instrumentation import RunContext

recorder = ActivityRecorder(session, notify_slack=False)
ctx = RunContext(recorder, agent_name="cursor-cloud", github_repository="org/repo")
ctx.run_started()
ctx.milestone("Schema migration added")
ctx.tests_completed()
```

## Reporting

```bash
python3 scripts/activity_report.py --date 2026-11-04
python3 scripts/activity_report.py --week-start 2026-11-03
python3 scripts/activity_report.py --run-id <uuid> --event-type progress.report
```

## Recovery

| Situation | Action |
|---|---|
| Slack down | Events remain in PostgreSQL; retry delivery or post manually, then `confirm_slack_delivery` |
| Duplicate MCP post | Use idempotency keys; set delivery status `duplicate` when replaying confirmation |
| Migration pending | From `services/wasatch-api`, run `alembic upgrade head` |
| No telemetry | Treat as unknown; investigate run logs and GitHub Actions |

## Security

- No secrets, tokens, or customer data in `metadata` or message bodies.
- No public HTTP write endpoint for events.
- Laboratory-only synthetic context.
