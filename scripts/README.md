# Scripts

Repository maintenance scripts. These are not application services.

| Script | Purpose |
|---|---|
| `validate_repo.py` | Required files, ADR naming, and secret-assignment checks |
| `validate_wasatch_domain.py` | JSON Schema, referential integrity, and invariants |
| `generate_wasatch_fixtures.py` | Deterministic generator for `data/fixtures/valid/` |
| `wasatch_dev.sh` | Start Postgres, migrate, seed, and run the API |

```bash
python3 scripts/validate_repo.py
python3 scripts/validate_wasatch_domain.py
```
