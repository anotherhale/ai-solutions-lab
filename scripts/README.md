# Scripts

Repository maintenance scripts. These are not application services.

| Script | Purpose |
|---|---|
| `validate_repo.py` | Required files, ADR naming, and secret-assignment checks |
| `validate_wasatch_domain.py` | JSON Schema, referential integrity, and invariants |
| `generate_wasatch_fixtures.py` | Deterministic generator for `data/fixtures/valid/` |
| `wasatch_dev.sh` | Start Postgres, migrate, seed, and run the API |
| `activity_report.py` | Summarize `development_ops.activity_events` by date, run, or filters |
| `coordinator_record_activity.sh` | Wrapper for `development-ops-record` |
| `coordinator_activity.sh` | Coordinator lifecycle shorthand (run-start, tests-passed, pr-opened, …) |
| `coordinator_tick.sh` | Reconcile PRs, optional auto-merge, select next eligible backlog task |
| `coordinator_automation_entrypoint.sh` | Automation entry: tick + delegate JSON for implementation agents |
| `coordinator_retarget_develop_prs.sh` | List or retarget open `develop` PRs to `ai-dev` (ADR 0014) |
| `prepare_development_ops_database.py` | Create/migrate `wasatch_development_ops` database |
| `bootstrap_laboratory.sh` | Postgres, Python venv, review app, and Playwright setup |
| `prepare_wasatch_database.py` | Create DB, migrate, and seed for CI or host-run API |
| `run_wasatch_api_host.sh` | Prepare database and serve API on port 8000 (no reload) |
| `smoke_compose.sh` | Build Compose API image, start stack, verify health and routes |
| `audit_wasatch_dependencies.sh` | Run `pip-audit` on the installed Wasatch API package (CI and local) |

```bash
python3 scripts/validate_repo.py
python3 scripts/validate_wasatch_domain.py
```
