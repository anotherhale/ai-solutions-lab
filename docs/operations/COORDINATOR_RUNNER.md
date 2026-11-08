# Coordinator runner operations

The persistent coordinator runner (`development-ops-record runner`) executes the
existing coordinator scheduling tick in a loop on the Mac mini laboratory host.
This is **not** a production service and **not** an Azure deployment. It runs as
the developer user and reuses that user's Git and GitHub credentials.

The locking model is **single-workstation**. It gives no protection across
machines. Do not run two coordinators on two hosts against one database.

See [ADR 0013](../adr/0013-persistent-coordinator-runner.md) for the design
decision and [COORDINATOR_CONTINUITY.md](COORDINATOR_CONTINUITY.md) for the
scheduling policy the runner drives.

## Commands

```bash
# Run the loop until SIGTERM/SIGINT (installs signal handlers).
development-ops-record runner run

# Run one recovery + tick cycle and exit (smoke test).
development-ops-record runner once

# Read-only health snapshot (never mutates state).
development-ops-record runner status

# Durably stop new task claims; running work is preserved.
development-ops-record runner pause --by "$USER" --reason "maintenance"

# Clear the pause and re-enable scheduling.
development-ops-record runner resume
```

`scripts/coordinator_runner.sh` wraps `runner run` with the correct PATH and an
optional environment file, and is what the LaunchAgent calls.

## Configuration

All values come from the environment, matching the development-ops convention.

| Variable | Default | Meaning |
|---|---|---|
| `DEVELOPMENT_OPS_GITHUB_REPOSITORY` | `anotherhale/ai-solutions-lab` | Repository the coordinator reconciles |
| `DEVELOPMENT_OPS_RUNNER_POLL_SECONDS` | `30` | Seconds between ticks |
| `DEVELOPMENT_OPS_RUNNER_HEARTBEAT_SECONDS` | `300` | Seconds between lease renewals |
| `DEVELOPMENT_OPS_LEASE_SECONDS` | `900` | Task lease duration |
| `DEVELOPMENT_OPS_RUNNER_RECOVER` | `1` | Run startup recovery on boot |
| `DEVELOPMENT_OPS_RUNNER_RECLAIM` | `1` | Reclaim expired leases each tick |
| `DEVELOPMENT_OPS_RUNNER_STATE_DIR` | `~/.local/state/ai-solutions-lab/coordinator` | Pause/status state and default lock location |
| `DEVELOPMENT_OPS_RUNNER_LOCK_PATH` | `<state dir>/coordinator.lock` | Explicit lock file path |
| `DEVELOPMENT_OPS_RUNNER_LOG_LEVEL` | `INFO` | `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL` |
| `DEVELOPMENT_OPS_RUNNER_LOG_FORMAT` | `json` | `json` or `text` |
| `DEVELOPMENT_OPS_BACKLOG_PATH` | repo default | Backlog YAML override |
| `DEVELOPMENT_OPS_RUNNER_ENV_FILE` | `~/.config/ai-solutions-lab/coordinator-runner.env` | Env file sourced by the launcher (holds secrets) |

Validation fails fast at startup: a non-positive interval, an unknown log level,
a blank repository, or a heartbeat interval longer than the lease is rejected
with a clear message rather than silently misbehaving.

## Pause and resume semantics

- **Pause** writes `paused: true` to the runner state file and is durable across
  restarts. A paused tick still reconciles GitHub PR state, attempts eligible
  auto-merge, and cleans up worktrees whose PRs GitHub confirms merged, but it
  passes a concurrency limit of zero so **no new task is claimed**.
- Active leases and PR tracking are preserved. Running work reaches a safe state
  on its own; pause is not an emergency stop and never destroys active work.
- **Resume** clears the flag; normal scheduling and existing concurrency policy
  resume on the next tick.
- A paused runner still holds the instance lock, so you cannot start a second
  runner while one is paused.

## Health and status

`development-ops-record runner status` prints read-only JSON:

- `database_ok` / `database_error` — connectivity, reported not raised.
- `paused` — durable pause state.
- `runner_active`, `owner_pid`, `owner_hostname`, `owner_run_id`, `lock_path`,
  `lock_stale` — process ownership.
- `last_tick_started_at`, `last_tick_completed_at`, `last_tick_error`,
  `last_tick_run_id` — last tick outcome.
- `last_recovery_at`, `recovery_events` — recovery activity.
- `active_leases`, `awaiting_pull_request` — current leases and PR-blocked tasks.

## launchd installation (Mac mini)

The LaunchAgent is a **template**. Nothing in CI or the PR workflow installs or
activates it. Install it deliberately, per host.

1. **Prepare the environment file** (mode 600, outside the checkout). launchd
   does **not** source `~/.zshrc` or `~/.bash_profile`, so secrets and PATH must
   be declared explicitly. Never put secrets in the plist.

   ```bash
   mkdir -p ~/.config/ai-solutions-lab
   cat > ~/.config/ai-solutions-lab/coordinator-runner.env <<'EOF'
   export GH_TOKEN=...          # GitHub token for gh CLI / API
   export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
   export DEVELOPMENT_OPS_DATABASE_URL="postgresql+psycopg://wasatch:...@localhost:5432/wasatch_development_ops"
   EOF
   chmod 600 ~/.config/ai-solutions-lab/coordinator-runner.env
   ```

2. **Copy and edit the plist.** Replace every `CHANGE_ME` and confirm the
   `ProgramArguments`, `WorkingDirectory`, log paths, and `EnvironmentVariables`.

   ```bash
   cp infrastructure/launchd/dev.ai-solutions-lab.coordinator-runner.plist \
      ~/Library/LaunchAgents/dev.ai-solutions-lab.coordinator-runner.plist
   "$EDITOR" ~/Library/LaunchAgents/dev.ai-solutions-lab.coordinator-runner.plist
   plutil -lint ~/Library/LaunchAgents/dev.ai-solutions-lab.coordinator-runner.plist
   ```

3. **Create the log directory** referenced by the plist.

   ```bash
   mkdir -p ~/Library/Logs/ai-solutions-lab
   ```

4. **Load and start.**

   ```bash
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/dev.ai-solutions-lab.coordinator-runner.plist
   launchctl kickstart -k gui/$(id -u)/dev.ai-solutions-lab.coordinator-runner
   ```

5. **Status.**

   ```bash
   launchctl print gui/$(id -u)/dev.ai-solutions-lab.coordinator-runner | head -40
   development-ops-record runner status
   tail -f ~/Library/Logs/ai-solutions-lab/coordinator-runner.err.log
   ```

6. **Stop / restart.**

   ```bash
   launchctl kill SIGTERM gui/$(id -u)/dev.ai-solutions-lab.coordinator-runner
   launchctl kickstart -k gui/$(id -u)/dev.ai-solutions-lab.coordinator-runner
   ```

7. **Remove.**

   ```bash
   launchctl bootout gui/$(id -u)/dev.ai-solutions-lab.coordinator-runner
   rm ~/Library/LaunchAgents/dev.ai-solutions-lab.coordinator-runner.plist
   ```

`KeepAlive` restarts the runner if it exits; `ThrottleInterval` prevents a tight
restart loop; `ExitTimeOut` gives the runner time to release the lock on SIGTERM.

## Troubleshooting

- **"another coordinator runner holds …"** — a live runner owns the lock. Stop it
  with SIGTERM, or remove the lock only if `runner status` shows `lock_stale`
  true. Never delete the lock while a runner is active.
- **No ticks after load** — check `coordinator-runner.err.log`. A launchd job
  that cannot find `python3` or the repository path exits immediately; confirm
  `ProgramArguments` and `WorkingDirectory` are absolute.
- **Tasks stuck `in_progress`** — a lease longer than the heartbeat means a live
  task looks abandoned. The configuration rejects heartbeat > lease at startup.
  Inspect `runner status` for `active_leases` and `last_tick_error`.

## Verification status

Process behavior (loop, signals, lock, recovery, pause, status, telemetry) is
covered by automated tests against disposable databases. **Live launchd
installation and long-duration operation on the Mac mini are not verified by the
test suite** and must be confirmed on the host.
