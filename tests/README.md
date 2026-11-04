# Tests

Cross-service and end-to-end suites will live here later.

The first application tests are in `services/wasatch-api/tests/`.

| Directory | Purpose |
|---|---|
| `services/wasatch-api/tests/unit/` | Domain, mapping, pagination, configuration |
| `services/wasatch-api/tests/integration/` | Migrations, seed, PostgreSQL constraints |
| `services/wasatch-api/tests/api/` | FastAPI HTTP contracts |
| `integration/` | Reserved for later cross-service tests |
| `e2e/` | User-visible flow tests once a frontend exists |

Use synthetic Wasatch Business Systems data only.
