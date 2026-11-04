# Fixtures

Synthetic Wasatch Business Systems records for tests and later application work.

| Path | Load as business data? |
|---|---|
| `valid/` | Yes. Referential integrity and invariants hold. |
| `quality-issues/` | No. Intentionally defective examples. |

Regenerate the valid set with:

```bash
python3 scripts/generate_wasatch_fixtures.py
python3 scripts/validate_wasatch_domain.py
```

The valid set is a slice of the fictional company, not 65 employees or 450 customers.
