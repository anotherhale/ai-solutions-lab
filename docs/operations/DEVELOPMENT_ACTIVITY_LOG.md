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

## Database isolation

Laboratory agents record into PostgreSQL database **`wasatch_development_ops`**
(schema `development_ops`), not the Wasatch API database **`wasatch`** and not
the pytest database **`wasatch_test`**.

| Database | Purpose |
|---|---|
| `wasatch` | Synthetic business data and local API |
| `wasatch_test` | Pytest migrations, downgrade/upgrade cycles, seeds |
| `wasatch_development_ops` | Append-only development activity (durable) |

Pytest resolves its URL from **`WASATCH_TEST_DATABASE_URL`**, or from
`WASATCH_DATABASE_URL` only when that URL’s database name is **`wasatch_test`**
(GitHub Actions). Exports aimed at **`wasatch`** or **`wasatch_development_ops`**
do not redirect migration tests.

Provision the ops database once per environment:

```bash
python3 scripts/prepare_development_ops_database.py
```

**Telemetry gaps:** If events are missing (for example after an ops database was
wiped before isolation landed), record a `blocker.reported` or `progress.report`
with metadata describing the gap. Do **not** backfill fabricated `run.started` or
`task.selected` rows.

## Configuration

| Variable | Purpose |
|---|---|
| `DEVELOPMENT_OPS_DATABASE_URL` | Activity log PostgreSQL URL (default `…/wasatch_development_ops`) |
| `WASATCH_DATABASE_URL` | Wasatch API only — not used by `development-ops-record` |
| `DEVELOPMENT_OPS_RUN_ID` | Correlate all events in one agent/coordinator run |
| `DEVELOPMENT_OPS_TASK_ID` | Active backlog/task identifier |
| `DEVELOPMENT_OPS_GITHUB_REPOSITORY` | `owner/repo` for PR links |
| `DEVELOPMENT_OPS_AGENT_NAME` | Agent or coordinator label |
| `DEVELOPMENT_OPS_SLACK_BOT_TOKEN` | Optional bot token for `chat.postMessage` automation |
| `DEVELOPMENT_OPS_SLACK_CHANNEL_ID` | Default `C0CFJDH7PTJ` |
| `DEVELOPMENT_OPS_REPORT_TZ` | Report timezone (default `America/Denver`) |

## CLI (Phase 2)

Install: `python3 -m pip install -e libs/development_ops`

```bash
export DEVELOPMENT_OPS_RUN_ID="$(uuidgen)"
export DEVELOPMENT_OPS_DATABASE_URL=postgresql+psycopg://wasatch:replace-me@localhost:5432/wasatch_development_ops
python3 scripts/prepare_development_ops_database.py

development-ops-record record \
  --event-type implementation.milestone \
  --title "CLI available" \
  --metadata '{"phase":2}' \
  --idempotency-key "${DEVELOPMENT_OPS_RUN_ID}:cli"

# Exit codes: 0 ok, 1 persistence failed, 2 Slack failed (row retained)
```

Confirm Slack after Cursor MCP post (Phase 3):

```bash
development-ops-record confirm-slack \
  --event-id "<uuid from record JSON>" \
  --channel-id C0CFJDH7PTJ \
  --message-ts "<ts from chat.postMessage or MCP>"
```

Coordinator shorthand:

```bash
scripts/coordinator_activity.sh run-start "My run"
scripts/coordinator_activity.sh tests-passed "pytest green"
scripts/coordinator_activity.sh pr-opened "Phase 2 PR" --github-pull-number 34
```

## Library

Package: `libs/development_ops` (`development-ops` on `pip install -e`).

```python
from development_ops.coordinator import CoordinatorWorkflow, coordinator_run

with coordinator_run() as ctx:
    flow = CoordinatorWorkflow(ctx)
    flow.start()
    flow.select_task("DEV-activity-2", "Agent instrumentation")
    flow.implementation("CLI and coordinator hooks")
    flow.tests_passed(metadata={"pytest": "passed"})
```

## Reporting (Phase 4)

```bash
python3 scripts/activity_report.py --date 2026-11-04
python3 scripts/activity_report.py --week-start 2026-11-03
python3 scripts/activity_report.py --run-id <uuid>
python3 scripts/activity_report.py --run-id <uuid> --event-type test.completed
```

Run reports list milestones in time order, GitHub PR links, and Slack delivery
status per event.

### Sample run report

See [samples/run-correlation-sample.md](samples/run-correlation-sample.md).

## Recovery

| Situation | Action |
|---|---|
| Slack down | Events remain in PostgreSQL; retry delivery or post manually, then `confirm-slack` |
| Duplicate MCP post | Use idempotency keys; pass `--duplicate` to `confirm-slack` when replaying |
| `development-ops-record` exit 1 | Persistence failed — check DB URL/migrations; report blocker in Slack |
| Migration pending | Run `python3 scripts/prepare_development_ops_database.py` for ops; `alembic upgrade head` for Wasatch API |
| Activity wiped by pytest | Use `wasatch_development_ops`; ensure `WASATCH_TEST_DATABASE_URL` targets `wasatch_test` |
| No telemetry | Treat as unknown; investigate run logs and GitHub Actions |

## Security

- No secrets, tokens, or customer data in `metadata` or message bodies.
- No public HTTP write endpoint for events.
- Laboratory-only synthetic context.
