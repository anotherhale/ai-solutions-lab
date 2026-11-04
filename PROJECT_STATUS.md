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

That relationship was true at `881cfc0`. `develop` later received the Ruff pin (`ec6465f`), the `develop` CI trigger (`ecd3015`), ADR 0001 acceptance (`c18ad80`), this planning set (`6cb587a`), CS-1 (`047702e`, pull request [#7](https://github.com/anotherhale/ai-solutions-lab/pull/7)), CS-2 (`7760106`, pull request [#8](https://github.com/anotherhale/ai-solutions-lab/pull/8)), CS-3 (`5b2ffc4`, pull request [#9](https://github.com/anotherhale/ai-solutions-lab/pull/9)), the laboratory-actor production boundary (`ac26535`, pull request [#10](https://github.com/anotherhale/ai-solutions-lab/pull/10)), the CI database gate (`d1178e8`, pull request [#11](https://github.com/anotherhale/ai-solutions-lab/pull/11)), CS-5 retrieval (`a03fea9`, pull request [#12](https://github.com/anotherhale/ai-solutions-lab/pull/12)), CS-4 approval decisions (`0785ab9`, pull request [#13](https://github.com/anotherhale/ai-solutions-lab/pull/13)), and CS-6 suggested replies (`781bcc0`, pull request [#14](https://github.com/anotherhale/ai-solutions-lab/pull/14)).

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
| CS-1 support tickets, messages, and interactions | Done. Pull request [#7](https://github.com/anotherhale/ai-solutions-lab/pull/7) merged as `047702e`. Read-only `/api/v1` routes and Alembic revision `0002`. |
| CS-2 approval requests and audit events | Done. Pull request [#8](https://github.com/anotherhale/ai-solutions-lab/pull/8) merged as `7760106`. Read-only `/api/v1` routes and Alembic revision `0003`. No approval decision route. |
| CS-3 laboratory actor and approver role | Done. Pull request [#9](https://github.com/anotherhale/ai-solutions-lab/pull/9) merged as `5b2ffc4`. Alembic revision `0004` persists roles and teams. `employees.role_id` references `roles`, and `is_approver` comes from that role. A local authenticator resolves `X-Laboratory-Actor` to an active synthetic employee. `/api/v1` reads require that actor. |
| Laboratory actor production boundary | Done. Pull request [#10](https://github.com/anotherhale/ai-solutions-lab/pull/10) merged as `ac26535`. The header adapter runs only for `APP_ENV` `local`, `development`, or `test`. `APP_ENV=production` and `APP_ENV=prod` raise `UnsafeProductionConfiguration` from `create_app` and from `LocalEmployeeAuthenticator` before a request is served. Any other environment fails the same way. There is no password system and no identity provider. ADR 0006 records the future production authenticator as a different `EmployeeAuthenticator` adapter. Role checks stay in the workforce application service. |
| CI database gate | Done. Pull request [#11](https://github.com/anotherhale/ai-solutions-lab/pull/11) merged as `d1178e8`. CI sets `WASATCH_REQUIRE_DATABASE=1`. `scripts/check_wasatch_api_pytest.py` fails the job when the Wasatch API database tests were skipped. A local run without PostgreSQL can still skip. |
| CS-4 approve or reject a customer message | Done. Pull request [#13](https://github.com/anotherhale/ai-solutions-lab/pull/13) merged as `0785ab9`. An approver can approve or reject pending `apr_0001` (`send_customer_message` for `msg_0016`). The command appends `decision_history`, sets `reviewer_employee_id` and `decided_at`, and inserts an audit event. The message body stays unchanged and the message is not marked `sent`. `emp_0004` is denied. No email, SMS, or other delivery. |
| CS-5 retrieval over synthetic history and procedures | Done. Pull request [#12](https://github.com/anotherhale/ai-solutions-lab/pull/12) merged as `a03fea9`. `GET /api/v1/support-tickets/{ticket_id}/retrieval` returns that customer's persisted history and matching synthetic procedure pages. The route does not call a model and does not add an embedding column. |
| CS-6 draft a suggested reply | Done. Pull request [#14](https://github.com/anotherhale/ai-solutions-lab/pull/14) merged as `781bcc0`. `POST /api/v1/support-tickets/{ticket_id}/draft-replies` creates an unsent reply for an existing ticket, grounded in that retrieval. For synthetic `tkt_0015` the reply cites `msg_0015` and `proc_0001`. Text that would commit Wasatch is `pending_approval` with `requires_approval` and a new `send_customer_message` request. Other text stays `draft` with no approval. Rejecting the approval leaves the message unsent. The default provider is the in-process fake. `AI_PROVIDER=openai` uses the OpenAI adapter only when `OPENAI_API_KEY` is not a placeholder. Tests and CI do not send a provider credential and do not call the network. |
| CS-7 review surface | This change. `apps/wasatch-review` is the first React and TypeScript application. No Nx. A reviewer opens one synthetic inquiry, reads the suggested reply, and approves or rejects it through the local API with `X-Laboratory-Actor`. `emp_0001` is an approver. `emp_0004` is not. Anonymous access is unauthorized. The screen has no send control and does not call a delivery system. |

Seeded governance counts: 10 approval requests, 11 decision-history rows, and 50 audit events. `msg_0016` (`pending_approval`, `requires_approval` true) references `apr_0001`. Audit rows are insert-only: revision `0003` installs a trigger that rejects `UPDATE` and `DELETE`. The customer-message decision inserts one new audit row and does not update or delete audit events. A second seed skips existing audit rows.

## Not implemented

These items are absent. Later documents must not describe them as running:

- Any user interface besides the customer-service review screen (`apps/wasatch-review`). That screen opens one synthetic inquiry and records approve or reject. It does not send email, SMS, or any other customer message.
- A model call in tests or CI. Chat and embedding ports exist. The OpenAI adapter is installed and stays behind `AI_PROVIDER`. The default provider is a fake and does not call the network. No provider credential is committed.
- Embedding columns (the `vector` extension is enabled; no vector column exists). The embedding port is not used to fill one.
- Outbound message delivery. The approval decision and the suggested-reply draft are the writes. Neither delivers email, SMS, or another channel, and neither marks the message `sent`.
- An external identity provider, purchased identity service, password system, or production credential. The local laboratory authenticator is a development-only header simulation. Production configuration fails startup instead of activating that header.
- OpenTelemetry export
- Redis, n8n, Azure, and Terraform resources (`infrastructure/terraform/` is a placeholder)
- Persistence for invoices, payments, and documents
- File bytes for documents (`data/documents/` is a placeholder; version rows point at synthetic `storage_path` values only)

ADR status in `docs/adr/README.md`: 0001, 0002, 0003, 0004, and 0005 are Accepted. ADR 0001 was accepted in pull request [#5](https://github.com/anotherhale/ai-solutions-lab/pull/5) (`c18ad80`): `services/wasatch-api` is the host, one process, and the customer and work-order modules are the first packages. ADR 0004 is Accepted: chat and embedding ports are in the application layer, and the OpenAI client stays in the infrastructure adapter.

## Phase 2.1.1 residuals

These are gaps inside an implemented slice. They are not a reason to recreate the database, models, or fixtures.

- HTTP contract coverage is `tests/unit/test_contract_alignment.py`, which checks customer and work-order status enums against JSON Schema. Responses are not validated against the full schemas.
- Tests run Alembic `upgrade` to `head`. Revision `0001` downgrade is still untested. Revisions `0002`, `0003`, and `0004` include upgrade and downgrade tests on the synthetic database.
- `tests/conftest.py` skips the suite when PostgreSQL cannot be reached. A local run without the database can skip rather than fail. CI does not rely on that skip: pull request [#11](https://github.com/anotherhale/ai-solutions-lab/pull/11) (`d1178e8`) sets `WASATCH_REQUIRE_DATABASE=1`, and `scripts/check_wasatch_api_pytest.py` fails the job when the database tests were skipped. The skip predicate was not removed.
- `/api/v1` reads require an active synthetic employee presented in `X-Laboratory-Actor`. That header is a local laboratory adapter. It runs only when `APP_ENV` is `local`, `development`, or `test`. `APP_ENV=production` and `APP_ENV=prod` fail startup. Health probes stay open. An active employee may `POST /api/v1/support-tickets/{ticket_id}/draft-replies`. An approver may `POST /api/v1/approval-requests/{approval_id}/decisions` for a pending customer message. Neither command marks the message `sent`. Every other authenticated write returns 403, and an anonymous write returns 401. The pytest skip predicate in `tests/conftest.py` is unchanged.
- `APP_LOG_LEVEL` configures structured logs of actor, action, subject, and outcome. Message bodies and secrets are omitted. OpenTelemetry export is still absent.
- `work_orders.invoice_id` remains a string. `employees.role_id` references `roles`. `employees.team_id` references `teams`. `work_orders.support_ticket_id` references `support_tickets`. `messages.approval_request_id` references `approval_requests`.

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

## Verification for CS-2

Run from `services/wasatch-api` with `services/wasatch-api/.venv` against the Compose PostgreSQL service (`pgvector/pgvector:pg16`). The suite created or reused `wasatch_test`. The skip in `tests/conftest.py` was not changed. This run did not skip.

| Command | Result | Exit |
|---|---|---|
| `.venv/bin/pytest` | 56 passed, 1 warning in 3.89s | 0 |

The warning is the existing Starlette deprecation of `anyio.abc.BlockingPortal` in `starlette/testclient.py`. The run upgraded and downgraded revision `0003` on the synthetic database. It did not start the API container and did not observe GitHub Actions.

From the repository root, same session:

| Command | Result | Exit |
|---|---|---|
| `ruff format --check .` | 121 files already formatted | 0 |
| `ruff check .` | All checks passed | 0 |
| `python3 scripts/validate_repo.py` | `Repository conventions validated.` | 0 |
| `python3 scripts/validate_wasatch_domain.py` | `Wasatch domain fixtures validated.` | 0 |

## Verification for CS-3

Run from `services/wasatch-api` with `services/wasatch-api/.venv` against the Compose PostgreSQL service (`pgvector/pgvector:pg16`). The suite created or reused `wasatch_test`. The skip in `tests/conftest.py` was not changed. This run did not skip.

| Command | Result | Exit |
|---|---|---|
| `.venv/bin/pytest` | 74 passed, 1 warning in 5.37s | 0 |

The warning is the existing Starlette deprecation of `anyio.abc.BlockingPortal` in `starlette/testclient.py`. The run upgraded and downgraded revision `0004` on the synthetic database. It did not start the API container and did not observe GitHub Actions.

From the repository root, same session:

| Command | Result | Exit |
|---|---|---|
| `ruff format --check .` | 139 files already formatted | 0 |
| `ruff check .` | All checks passed | 0 |
| `python3 scripts/validate_repo.py` | `Repository conventions validated.` | 0 |
| `python3 scripts/validate_wasatch_domain.py` | `Wasatch domain fixtures validated.` | 0 |

## Verification for the laboratory actor boundary

Run from `services/wasatch-api` with `services/wasatch-api/.venv` against the Compose PostgreSQL service (`pgvector/pgvector:pg16`). The suite created or reused `wasatch_test`. The skip predicate in `tests/conftest.py` was not edited. This run did not skip.

| Command | Result | Exit |
|---|---|---|
| `.venv/bin/pytest` | 93 passed, 0 failed, 0 skipped, 1 warning in 4.78s | 0 |

The warning is the existing Starlette deprecation of `anyio.abc.BlockingPortal` in `starlette/testclient.py`. The run did not start the API container and did not observe GitHub Actions.

From the repository root, same session:

| Command | Result | Exit |
|---|---|---|
| `ruff format --check .` | 141 files already formatted | 0 |
| `ruff check .` | All checks passed | 0 |
| `python3 scripts/validate_repo.py` | `Repository conventions validated.` | 0 |
| `python3 scripts/validate_wasatch_domain.py` | `Wasatch domain fixtures validated.` | 0 |

## Verification for CS-4

Run from `services/wasatch-api` with `services/wasatch-api/.venv` against the Compose PostgreSQL service (`pgvector/pgvector:pg16`), after rebasing onto `develop` at `a03fea9` (retrieval, pull request [#12](https://github.com/anotherhale/ai-solutions-lab/pull/12)). The suite created or reused `wasatch_test`. `tests/conftest.py` was not edited. This run did not skip.

| Command | Result | Exit |
|---|---|---|
| `.venv/bin/pytest --tb=line -rfEs` | 124 passed, 0 failed, 0 skipped, 1 warning in 5.85s | 0 |

The warning is the existing Starlette deprecation of `anyio.abc.BlockingPortal` in `starlette/testclient.py`. The run did not start the API container and did not observe GitHub Actions.

From the repository root, same session:

| Command | Result | Exit |
|---|---|---|
| `services/wasatch-api/.venv/bin/ruff format --check .` | 154 files already formatted | 0 |
| `services/wasatch-api/.venv/bin/ruff check .` | All checks passed | 0 |
| `python3 scripts/validate_repo.py` | `Repository conventions validated.` | 0 |
| `python3 scripts/validate_wasatch_domain.py` | `Wasatch domain fixtures validated.` | 0 |

## Verification for CS-6

Run from `services/wasatch-api` with `services/wasatch-api/.venv` against the Compose PostgreSQL service (`pgvector/pgvector:pg16`). The parent is `develop` at `0785ab9`. The suite created or reused `wasatch_test`. `tests/conftest.py`, `.github/workflows/validate.yml`, and `scripts/check_wasatch_api_pytest.py` were not edited. `WASATCH_REQUIRE_DATABASE=1` was set. This run did not skip. No `OPENAI_API_KEY` was set. `AI_PROVIDER` was unset, so the draft route used the fake port.

| Command | Result | Exit |
|---|---|---|
| `WASATCH_REQUIRE_DATABASE=1 .venv/bin/pytest --tb=line -rfEs` | 142 passed, 0 failed, 0 skipped, 1 warning in 6.93s | 0 |

The warning is the existing Starlette deprecation of `anyio.abc.BlockingPortal` in `starlette/testclient.py`. The run did not start the API container, did not call OpenAI, and did not observe GitHub Actions.

From the repository root, same session:

| Command | Result | Exit |
|---|---|---|
| `services/wasatch-api/.venv/bin/ruff format --check .` | 167 files already formatted | 0 |
| `services/wasatch-api/.venv/bin/ruff check .` | All checks passed | 0 |
| `python3 scripts/validate_repo.py` | `Repository conventions validated.` | 0 |
| `python3 scripts/validate_wasatch_domain.py` | `Wasatch domain fixtures validated.` | 0 |

## Verification for CS-7

Run from `apps/wasatch-review` with Node.js 22.23.4. These checks do not use PostgreSQL, a provider key, or `OPENAI_API_KEY`. `.github/workflows/validate.yml`, `scripts/check_wasatch_api_pytest.py`, and `services/wasatch-api/tests/conftest.py` were not edited. The review-screen checks are not part of GitHub Actions.

| Command | Result | Exit |
|---|---|---|
| `npm test` | Vitest 5.1.0. 9 passed across 2 files | 0 |
| `npm run typecheck` | `tsc --noEmit` | 0 |
| `npm run build` | Vite production build succeeded | 0 |

From the repository root, same session:

| Command | Result | Exit |
|---|---|---|
| `services/wasatch-api/.venv/bin/ruff format --check .` | 168 files already formatted | 0 |
| `services/wasatch-api/.venv/bin/ruff check .` | All checks passed | 0 |
| `python3 scripts/validate_repo.py` | `Repository conventions validated.` | 0 |
| `python3 scripts/validate_wasatch_domain.py` | `Wasatch domain fixtures validated.` | 0 |

The workstation virtualenv was missing the `openai` package already declared by the API. After `pip install -e 'services/wasatch-api[dev]'`, `WASATCH_REQUIRE_DATABASE=1 pytest` from `services/wasatch-api` exited 0. Collection lists 142 tests. The progress output showed no failures. The warning is the existing Starlette deprecation. The run did not call OpenAI and did not observe GitHub Actions. The first attempt, before that install, failed one unit test because `openai` was not importable.

Browser check against the local API on port 8000, with the Vite dev server proxying `/api` from http://127.0.0.1:5173. Wasatch data is synthetic. The page never showed a send control.

| Path | What the browser showed |
|---|---|
| Empty suggestion | Jordan Hale (`emp_0001`) opened `tkt_0015`. The inbound rooftop message was visible. The suggestion panel said no suggested reply was waiting. Approve and reject were absent. |
| Unauthorized actor | Anonymous, with no `X-Laboratory-Actor` header, opened `tkt_0007`. The API returned 401. The banner said `Unauthorized. a laboratory actor is required`. The inquiry did not load. |
| Non-approver | Elena Voss (`emp_0004`) opened `tkt_0007` and clicked Approve reply. The banner said this actor cannot approve or reject the suggested reply, and the API message was `writes are denied`. The reply stayed pending. |
| Approve | Jordan Hale approved `apr_0001` with the note `Overtime approved for Thursday.` The banner said `Approved. The message was not sent.` `msg_0016` stayed `pending_approval`. The approval was `approved`, reviewer `emp_0001`, and `executed_at` was null. |
| Reject | After seed restored `apr_0001` to pending, Jordan Hale rejected it with the note `Customer did not approve overtime.` The banner said `Rejected. The message was not sent.` `msg_0016` stayed `pending_approval`. The approval was `rejected`, and `executed_at` was null. |

A later seed put `apr_0001` back to pending and cleared its decision history. Audit storage is insert-only, so the two decision rows (`aud_0051` approved, `aud_0052` rejected) remain in the local `wasatch` database. GitHub Actions was not observed.
