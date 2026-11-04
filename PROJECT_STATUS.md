# Project Status

Snapshot of AI Solutions Lab as verified on 2026-11-04. Wasatch Business Systems is a fictional company. All business records in this repository are synthetic.

This file records what is in the repository and what was run. Forward work is in [ENGINEERING_BACKLOG.md](ENGINEERING_BACKLOG.md). Phase design is in [docs/architecture/IMPLEMENTATION_PLAN.md](docs/architecture/IMPLEMENTATION_PLAN.md). Contributor and agent rules for integration are in [docs/architecture/AGENT_OPERATING_MODEL.md](docs/architecture/AGENT_OPERATING_MODEL.md).

If this snapshot disagrees with the code, the code wins. Update this file in the same change that alters the snapshot.

## Baseline

| Item | Value |
|---|---|
| Assessed commit | `881cfc08db1fc609e531a3f0be3230938d07f561` |
| Commit subject | Keep the Wasatch API test database password visible (#1) |
| Integration branch | `develop` at that commit |
| Production branch | `main` at that commit |
| Relationship | `develop` and `main` point at the same commit. `develop` was created from `main` with a normal push. |

`main` is the production branch. Work integrates on `develop`. Merges to `main` are out of scope for laboratory agents.

That relationship was true at `881cfc0`. `develop` later received the Ruff pin (`ec6465f`), the `develop` CI trigger (`ecd3015`), ADR 0001 acceptance (`c18ad80`), and this planning set (`6cb587a`).

## Remote branches observed

| Branch | Tip | Notes |
|---|---|---|
| `main` | `881cfc0` | Production branch. Same commit as `develop` at the assessment. |
| `develop` | `881cfc0` | Integration branch at the assessment. Later merges are under Current work. |
| `cursor/pin-ruff-0-17-3-6c1a` | `afdd60f` | Merged. Pull request [#2](https://github.com/anotherhale/ai-solutions-lab/pull/2) (`ec6465f`) pins Ruff 0.17.3 on `develop`. |
| `cursor/wasatch-pytest-db-url-de06` | `9bf8bd5` | Tree matches `develop`. No unique files remain to merge. |

## Completed milestones

### Phase 1 — foundation

Present and checked in this session:

- Charter, architecture, security, roadmap, and development workflow
- ADRs 0001–0005
- Wasatch profile, domain model, and workflows (synthetic)
- JSON Schema Draft 2020-12 contracts under `data/schemas/v1/`
- Valid fixtures and separate quality-issue fixtures
- `scripts/validate_repo.py` and `scripts/validate_wasatch_domain.py`
- GitHub Actions workflow `.github/workflows/validate.yml`
- Repository Python tooling in the root `pyproject.toml`

The valid fixture manifest counts 15 customers and 15 employees. That is a laboratory slice of the synthetic company (about 450 customers and about 65 employees), not a second dataset.

### Phase 2.1.1 — read-only operational slice

Phase 2.1.1 is implemented on `develop`. Do not rebuild it.

| Requirement | Evidence in the repository |
|---|---|
| PostgreSQL with pgvector | `compose.yaml` service uses `pgvector/pgvector:pg16`. Alembic revision `0001` runs `CREATE EXTENSION IF NOT EXISTS vector`. |
| SQLAlchemy 2 models | `services/wasatch-api/src/wasatch_api/shared/database/models.py` uses `Mapped` and `mapped_column`. |
| Alembic migrations | `services/wasatch-api/alembic/versions/0001_initial_wasatch_slice.py` has `upgrade` and `downgrade`. |
| Synthetic fixture loading | `wasatch_api.shared.seed` loads `data/fixtures/valid/` and refuses `quality-issues/`. |
| FastAPI foundation | `wasatch_api.main:create_app`, health routes, error handlers, pagination. |
| Read-only customer, service-location, and work-order endpoints | `GET /api/v1/customers`, `GET /api/v1/customers/{customer_id}`, `GET /api/v1/service-locations/{location_id}`, `GET /api/v1/work-orders`, `GET /api/v1/work-orders/{work_order_id}`. |
| Automated tests | Unit, integration, and API tests under `services/wasatch-api/tests/`. This session: 29 passed. |
| Docker Compose | Root `compose.yaml` defines `postgres` and `api`. |
| CI | `.github/workflows/validate.yml` runs Ruff, both validators, and pytest against `pgvector/pgvector:pg16`. |
| Developer docs | Root `README.md`, `services/wasatch-api/README.md`, `docs/architecture/API_CONVENTIONS.md`, `docs/architecture/DATABASE_MAPPING.md`. |

Persisted tables: `customers`, `contacts`, `service_locations`, `employees`, `equipment`, `work_orders`, `work_order_assignments`, `work_order_equipment`, `work_order_tasks`, `appointments`.

Package layout for the slice is hexagonal inside one process: domain entities, application queries, infrastructure repositories, and FastAPI adapters. Customer and work-order modules share one SQLAlchemy metadata graph, as documented in the models module.

Seeded counts asserted by the integration test: 15 customers, 20 service locations, 40 work orders.

## Current work

| Item | State |
|---|---|
| This planning set | Documentation only. No application code in this change. Merged as pull request [#3](https://github.com/anotherhale/ai-solutions-lab/pull/3) (`6cb587a`). |
| RUFF-1 Ruff 0.17.3 pin | Done. Pull request [#2](https://github.com/anotherhale/ai-solutions-lab/pull/2) merged as `ec6465f`. Root and service dev extras, the Actions install, and the README command pin `ruff==0.17.3`. |
| CI-1 develop push trigger | Done. Pull request [#4](https://github.com/anotherhale/ai-solutions-lab/pull/4) merged as `ecd3015`. `.github/workflows/validate.yml` runs on pushes to `main` and `develop`. Existing jobs stayed in place. |
| ADR-1 modular host | Done. Pull request [#5](https://github.com/anotherhale/ai-solutions-lab/pull/5) merged as `c18ad80`. ADR 0001 is Accepted. |
| Phase 2.2 customer-service slice | Not started. Next implementation priority is CS-1. |

## Not implemented

These items are absent. Later documents must not describe them as running:

- React or any other user interface (`apps/` is a placeholder)
- AI provider port, OpenAI adapter, or any model call
- Embedding columns (the `vector` extension is enabled; no vector column exists)
- Write APIs, including approval decisions and outbound message sends
- Authentication and authorization
- Structured application logging and OpenTelemetry
- Redis, n8n, Azure, and Terraform resources (`infrastructure/terraform/` is a placeholder)
- Persistence for roles, teams, invoices, payments, documents, tickets, messages, interactions, approvals, and audit events
- File bytes for documents (`data/documents/` is a placeholder; version rows point at synthetic `storage_path` values only)

ADR status in `docs/adr/README.md`: 0001, 0002, 0003, and 0005 are Accepted. ADR 0001 was accepted in pull request [#5](https://github.com/anotherhale/ai-solutions-lab/pull/5) (`c18ad80`): `services/wasatch-api` is the host, one process, and the customer and work-order modules are the first packages. ADR 0004 stays Proposed until a port and adapter exist.

## Phase 2.1.1 residuals

These are gaps inside an implemented slice. They are not a reason to recreate the database, models, or fixtures.

- HTTP contract coverage is `tests/unit/test_contract_alignment.py`, which checks customer and work-order status enums against JSON Schema. Responses are not validated against the full schemas.
- Tests run Alembic `upgrade` to `head`. They do not run `downgrade`.
- `tests/conftest.py` skips the suite when PostgreSQL cannot be reached. CI provides PostgreSQL, so CI does not rely on that skip. A local run without the database can skip rather than fail.
- The read API has no authentication. `docs/SECURITY.md` requires least-privilege authorization before customer and employee data are exposed beyond the laboratory. The current process is a local synthetic slice.
- No application logger is configured. `APP_LOG_LEVEL` is accepted and unused.
- `work_orders.support_ticket_id` and `work_orders.invoice_id` are strings. `employees.role_id` and `employees.team_id` are strings. Foreign keys wait for those tables.

## Verification in this session

Working tree parent: `881cfc0`. The first pass ran on that commit before these planning files existed. The second pass ran from the repository root after the four files were on disk and before they were committed. Python behavior and fixture counts were unchanged. Ruff's formatted-file count rose from 93 to 97 because the four new Markdown files are included in the format check.

| Command | First pass (`881cfc0`) | Second pass (docs present) | Exit |
|---|---|---|---|
| `python3 --version` | Python 3.12.3 | same | 0 |
| `ruff --version` | ruff 0.17.3 | same | 0 |
| `ruff format --check .` | 93 files already formatted | 97 files already formatted | 0 |
| `ruff check .` | All checks passed | All checks passed | 0 |
| `python3 -m ruff --version` | `/usr/bin/python3: No module named ruff` | same | 1 |
| `python3 scripts/validate_repo.py` | `Repository conventions validated.` | same | 0 |
| `python3 scripts/validate_wasatch_domain.py` | `Wasatch domain fixtures validated.` Counts below. | same counts | 0 |
| `docker --version` | Docker version 28.5.2, build ecc6942 | not re-run | 0 |
| `docker compose version` | Docker Compose version v5.7.0 | not re-run | 0 |
| `docker compose ps` | `wasatch-postgres` (`pgvector/pgvector:pg16`) up and healthy. API container not running. | not re-run | 0 |

From `services/wasatch-api` using `services/wasatch-api/.venv`:

| Command | First pass | Second pass | Exit |
|---|---|---|---|
| `python --version` | Python 3.12.3 | not re-run | 0 |
| `pytest --version` | pytest 8.4.2 | not re-run | 0 |
| `alembic --version` | alembic 1.16.5 | not re-run | 0 |
| `pytest` | 29 passed, 1 warning in 1.68s | 29 passed, 1 warning in 1.21s | 0 |

The warning is Starlette's deprecation of `anyio.abc.BlockingPortal` inside `starlette/testclient.py`. Installed application packages in that virtualenv: FastAPI 0.121.3, SQLAlchemy 2.0.57, Alembic 1.16.5, psycopg 3.2.13, Pydantic 2.11.10, jsonschema 4.26.0.

Domain validator counts:

| Entity | Count |
|---|---|
| role | 12 |
| team | 5 |
| employee | 15 |
| customer | 15 |
| contact | 25 |
| service_location | 20 |
| equipment | 30 |
| work_order | 40 |
| work_order_task | 63 |
| appointment | 25 |
| invoice | 30 |
| invoice_line | 40 |
| payment | 20 |
| document | 30 |
| document_version | 31 |
| document_extraction | 18 |
| support_ticket | 15 |
| message | 17 |
| interaction | 15 |
| approval_request | 10 |
| audit_event | 50 |

Pytest used the Compose PostgreSQL service and created the `wasatch_test` database. Routes were exercised with FastAPI `TestClient`. This session did not start the API container, did not call a live uvicorn process, did not run `alembic downgrade`, and did not observe a GitHub Actions run.

Pull request [#2](https://github.com/anotherhale/ai-solutions-lab/pull/2) merged as `ec6465f` and pinned Ruff to 0.17.3 in the root and service dev extras, the Actions install, and the README command. The cloud environment install described in that pull request is separate from the git diff.
