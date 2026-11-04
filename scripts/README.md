# Scripts

Repository maintenance scripts. These are not application services.

| Script | Purpose |
|---|---|
| `validate_repo.py` | Required files, ADR naming, and secret-assignment checks |
| `validate_wasatch_domain.py` | JSON Schema, referential integrity, and invariants |
| `generate_wasatch_fixtures.py` | Deterministic generator for `data/fixtures/valid/` |
| `wasatch_dev.sh` | Start Postgres, migrate, seed, and run the API |
| `bootstrap_laboratory.sh` | Postgres, Python venv, review app, and Playwright setup |
| `prepare_wasatch_database.py` | Create DB, migrate, and seed for CI or host-run API |
| `run_wasatch_api_host.sh` | Prepare database and serve API on port 8000 (no reload) |
| `smoke_compose.sh` | Build Compose API image, start stack, verify health and routes |
| `audit_wasatch_dependencies.sh` | Run `pip-audit` on the installed Wasatch API package (CI and local) |

```bash
python3 scripts/validate_repo.py
python3 scripts/validate_wasatch_domain.py
```
