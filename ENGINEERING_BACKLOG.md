# Engineering Backlog

Ordered work for AI Solutions Lab. Wasatch Business Systems content is synthetic.

Design constraints and acceptance for each phase live in [docs/architecture/IMPLEMENTATION_PLAN.md](docs/architecture/IMPLEMENTATION_PLAN.md). The verified baseline is [PROJECT_STATUS.md](PROJECT_STATUS.md). Agents follow [docs/architecture/AGENT_OPERATING_MODEL.md](docs/architecture/AGENT_OPERATING_MODEL.md).

Pull requests target `develop`. The coordinator merges. Application code for Phase 2.2 starts only after this planning change is merged, and it starts at CS-1. Phase 2.1.1 is already on `develop`.

## Done

Merged to `develop`. Do not reopen these as new work.

### RUFF-1 — Pin Ruff 0.17.3

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/2
- Merge: `ec6465f`
- Branch: `cursor/pin-ruff-0-17-3-6c1a`
- Base: `develop`
- Scope: pin `ruff==0.17.3` in the root `pyproject.toml` dev extra, the `wasatch-api` dev extra, `.github/workflows/validate.yml`, and the README validation command
- Do not open a second change for the same pin. The cloud environment install described in that pull request is separate from the git diff and is not part of this backlog item's repository files.

### CI-1 — Run the existing workflow on `develop`

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/4
- Merge: `ecd3015`
- Depends on: none
- `develop` is on the `push` branch list in `.github/workflows/validate.yml`. The existing jobs and commands stayed in place.
- Acceptance met: a pull request into `develop` and a push to `develop` both run format, lint, both validators, and the Wasatch API tests. The check set stayed as strict as it was.

### ADR-1 — Record that the modular host exists

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/5
- Merge: `c18ad80`
- Depends on: none
- ADR 0001 is `Accepted`. The index in `docs/adr/README.md` matches. The host is one process, and the customer and work-order modules are the first packages.
- Acceptance met: the ADR matches the repository. No new deployment shape was introduced.

### DOC-1 — Align contributor docs with the integration branch

- Status: done
- Depends on: this planning set
- `docs/DEVELOPMENT_WORKFLOW.md` sends pull requests to `develop`, keeps `main` as the production branch, and forbids force-pushes to either branch.
- `docs/architecture/README.md` points at `services/wasatch-api` and at the plan documents.
- `PROJECT_STATUS.md`, `ENGINEERING_BACKLOG.md`, `docs/architecture/IMPLEMENTATION_PLAN.md`, and `docs/architecture/AGENT_OPERATING_MODEL.md` are linked from `README.md` and `docs/architecture/README.md`.
- Those four paths are in `REQUIRED_FILES` in `scripts/validate_repo.py`.
- Acceptance: `python3 scripts/validate_repo.py` passes, and a new reader can find the plan from the root README.

## Phase 2.2 — customer-service vertical slice

Goal, from [docs/ROADMAP.md](docs/ROADMAP.md): a person can review an inbound synthetic inquiry, inspect a suggested reply, and approve or reject it.

The slice ends at that decision. It does not send email, SMS, or any other customer-visible delivery. It does not post invoices or change field schedules.

Use `data/schemas/v1/` and `data/fixtures/valid/`. Extend the existing seed loader. Do not add a second customer dataset or a parallel domain model.

### CS-1 — Read support tickets, messages, and interactions

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/7
- Merge: `047702e`
- Depends on: Phase 2.1.1 (done)
- Alembic revision after `0001` for `support_tickets`, `messages`, and `interactions`, using UUID primary keys and unique `business_id` values.
- When the ticket table exists, replace `work_orders.support_ticket_id` string storage with a foreign key to the ticket row in that same migration, backfilling from the business identifier.
- SQLAlchemy mappings, domain read models, application queries, repositories, and read-only `/api/v1` routes.
- Extend `seed_valid_fixtures` for `support_tickets.json`, `messages.json`, and `interactions.json`. Keep the quality-issue refusal.
- Tests: mapping, seed counts (15 tickets, 17 messages, 15 interactions), list and detail routes, 404, and status enums aligned with the JSON Schemas.
- Acceptance: seeded synthetic tickets are readable through the API. No write route is added.

### CS-2 — Read approval requests and audit events

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/8
- Merge: `7760106`
- Depends on: CS-1 (done, `047702e`), so seed and migration edits stay serial
- Persist `approval_requests` and `audit_events` from the existing fixtures (10 approvals, 50 audit events).
- Read-only routes. Audit storage is insert-only: the migration and the application expose no update or delete for `audit_events`.
- Message rows that already reference `apr_0001` and `apr_0004` gain a foreign key to approval requests once that table exists.
- Acceptance: `msg_0016` (`pending_approval`, `requires_approval: true`, `apr_0001`) can be read with its approval request. No decision can be recorded yet.

### CS-3 — Laboratory actor and approver role

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/9
- Merge: `5b2ffc4`
- Depends on: CS-2 (done, `7760106`)
- Persist `roles` from `roles.json` and attach `employees.role_id` with a foreign key. `is_approver` comes from that role. Persist `teams` in the same change only if the employee foreign key is straightforward; team membership is not required to approve a message.
- Add a local authentication adapter for synthetic employees. Default deny on writes. Reads of customer and employee data require an authenticated laboratory actor.
- Keep the adapter inside the monolith. No Azure identity provider, no purchased identity service, and no production credentials.
- The `X-Laboratory-Actor` adapter is limited to local synthetic development (`APP_ENV` of `local`, `development`, or `test`). `APP_ENV=production` and `APP_ENV=prod` fail startup. There is no password system and no identity provider. A production authenticator would be a later `EmployeeAuthenticator` adapter, not this header. ADR 0006 records that boundary. Pull request [#10](https://github.com/anotherhale/ai-solutions-lab/pull/10) merged as `ac26535`.
- Tests cover anonymous access, an unauthorized role (`emp_0004`), and a privileged role (`emp_0001`).
- Acceptance: every later write in this slice knows which synthetic employee is acting, and non-approver roles cannot decide approvals.

### CS-4 — Approve or reject a customer message

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/13
- Merge: `0785ab9`
- Depends on: CS-3 (done, `5b2ffc4`)
- Application service for the human decision on `send_customer_message`: approve or reject a pending request.
- The service appends `decision_history`, sets reviewer and `decided_at`, and inserts an audit event.
- The service leaves the message unsent. Status `sent` is not a result of this command.
- Authorization requires `is_approver` on the actor's role.
- Tests use the synthetic pending message and a role that is not an approver.
- Acceptance: an approver can approve or reject `apr_0001` through the API. The message body is unchanged and the message is not marked sent. An audit row exists for the decision.

### CS-5 — Retrieval over synthetic history and procedures

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/12
- Merge: `a03fea9`
- Depends on: CS-1. Can proceed beside CS-3 and CS-4 after CS-1 is merged.
- Retrieval port in the application layer. First adapter queries persisted ticket, message, interaction, and work-order text for one customer.
- `data/documents/` has no bytes. Document version rows point at synthetic paths such as `synthetic/documents/doc_0001/v1.bin`, and those files are not in the repository. Add a small synthetic procedure corpus under `data/documents/` when this task starts, labeled synthetic, and register it without replacing `data/fixtures/valid/`.
- Keep embeddings in PostgreSQL. Add a vector column only when an embedding port can fill it. EMB-1 does that for procedure pages. Customer-history retrieval stays relational. No second vector database.
- Acceptance: a query for a known synthetic ticket returns that customer's history and any matching procedure page, with tests that do not call a network model.

### CS-6 — Draft a suggested reply

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/14
- Merge: `781bcc0`
- Depends on: CS-3, CS-4, CS-5, and ADR 0004
- Define chat and embedding ports. Domain packages do not import a provider SDK.
- OpenAI is the first adapter and stays behind configuration. Tests use a fake port. Repository validation and CI stay free of an API key.
- The use case creates a `draft` or `pending_approval` message on an existing ticket. Outbound text that would commit the company sets `requires_approval` and opens a `send_customer_message` approval request.
- The use case does not set the message to `sent` and does not call an external delivery system.
- Acceptance: given synthetic ticket `tkt_0015` (or another inbound ticket chosen in the test), the API returns a draft reply grounded in retrieval results. Rejecting the approval leaves the draft unsent. CI passes without a provider credential.

### CS-7 — Review surface

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/15
- Merge: `13826ed`
- Depends on: CS-4 and CS-6
- First React and TypeScript application under `apps/wasatch-review`. No Nx.
- A customer-service reviewer can open one inbound inquiry, read the suggested reply, and approve or reject it.
- The screen shows synthetic data and does not offer a send control.
- Acceptance: the roadmap exit for Phase 2 is demonstrable against the local API. Browser verification covers the approve and reject paths, an empty suggestion state, and an unauthorized actor.

### DOC-P3 — Human review of document extractions

- Status: done in this change
- Depends on: document fixture persistence (Alembic `0005`, pull request [#16](https://github.com/anotherhale/ai-solutions-lab/pull/16), `78877e6`) and the CS-4 approval command
- `POST /api/v1/document-extractions/{extraction_id}/decisions` lets an approver accept or reject an extraction that is awaiting review (`needs_review`, `pending`, `succeeded`, or `failed`)
- The command stores status, reviewer, `reviewed_at`, and optional `review_notes`, and inserts an audit event
- Confidence below 0.8, a missing confidence score, `needs_review`, an invoice or money key in `extracted_fields`, or a document linked to an invoice stays untrusted until that decision
- A read, a seed, and a background job do not accept those rows. This service has no background job and does not call a model
- Accepting or rejecting does not post a payment, change an invoice total, or mark an invoice posted
- Embeddings are not part of this slice. No vector column is added. Alembic `0005` already stores the review columns
- Acceptance: `emp_0001` can accept `dx_0003` and reject `dx_0009` while invoice and payment fixtures stay unchanged. `emp_0004` is denied. An anonymous caller receives 401

### EMB-1 — Procedure-page embeddings in PostgreSQL

- Status: done in this change
- Depends on: CS-5 retrieval (`a03fea9`) and the embedding port from CS-6 (`781bcc0`)
- Alembic revision `0006` adds `procedure_page_embeddings.embedding` as `vector(8)`, the width the laboratory embedding port returns. The fake port is that default and is deterministic. Domain code does not choose a different width.
- An application service fills one vector per synthetic procedure page by calling `EmbeddingPort`. Infrastructure writes the column. Domain code does not import a vendor SDK.
- Only procedure text is embedded. Document version `storage_path` values are still not files. Unaccepted, `needs_review`, low-confidence, and financial extractions are not inserted. Accepting an extraction does not post a payment or change an invoice.
- Retrieval for `tkt_0015` still cites `proc_0001`. Customer history stays a relational query. The fake vectors are not a trusted semantic model.
- `AI_PROVIDER` stays `fake`. `openai` with `OPENAI_API_KEY=replace-me` fails before an OpenAI client is constructed. Tests unset `AI_PROVIDER` and `OPENAI_API_KEY` and do not call the network.
- That change did not start a workflow. No Redis, n8n, or second vector database.
- Acceptance: filling the index through the fake port writes the procedure vectors and does not open a provider socket. `tkt_0015` still returns `proc_0001`. The placeholder OpenAI key fails before client construction. An unaccepted financial extraction is not inserted.

### WF-1 — Follow-up visit after an approved customer message

- Status: done. Pull request [#19](https://github.com/anotherhale/ai-solutions-lab/pull/19) merged as `1b22eac`
- Depends on: CS-4 (`0785ab9`). The workflow does not use document extractions
- One command in the monolith: `POST /api/v1/approval-requests/{approval_id}/follow-up-visits`
- Two human steps. An approver approves a pending `send_customer_message`. That decision does not open the visit, does not dispatch a technician, does not mark `msg_0016` sent, and does not change the CS-4 rule that a message decision leaves the message unsent. A dispatcher (`role_0004`, including `emp_0004`) then opens the visit from that approval. The opened visit stays `unscheduled` until the dispatcher confirms or cancels it
- Each transition inserts an audit event. Audit stays insert-only
- Confirming or canceling does not post a payment, change an invoice total, mark an invoice posted, send a message, assign a technician, or create an appointment
- Alembic revision `0007` stores `follow_up_visits` only. No vector column. Extractions are not embedded
- An employee who is not a dispatcher is denied. Anonymous callers receive 401. Other writes stay denied
- No n8n, Redis, Kafka, queue, or new service. No React screen. The review screen does not gain a send control
- `X-Laboratory-Actor` stays limited to `local`, `development`, and `test`. Unsafe production configuration still fails startup
- The case study is PORT-1
- Acceptance: `emp_0001` approves `apr_0001`, and `emp_0004` opens nothing until that approval exists. After the approval, `emp_0004` confirms `fuv_0001`. `msg_0016` stays `pending_approval`. Invoice and payment rows are unchanged. The dispatcher can cancel instead. `emp_0001` and `emp_0006` are denied. An anonymous caller receives 401. The approval alone does not dispatch a technician

### OPS-1 — Observe and operate the laboratory host

- Status: done. Pull request [#20](https://github.com/anotherhale/ai-solutions-lab/pull/20) merged as `1be4181`
- Depends on: a module worth operating. The Wasatch API host qualifies. No production customer deployment
- The host records OpenTelemetry spans. `wasatch_api.observability` is called from `create_app`. Domain and application code does not import the SDK
- Spans export over OTLP/HTTP only when `OTEL_EXPORTER_OTLP_ENDPOINT` is a non-empty URL. An unset or blank value does not construct an exporter, does not open a socket, and does not require a collector
- Compose and GitHub Actions do not gain a collector, Redis, n8n, or a cloud account. GitHub Actions stays credential-free
- Direct dependencies are pinned to the OpenTelemetry 1.45.2 / instrumentation 0.66b2 pair: `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`, and `opentelemetry-instrumentation-fastapi`
- `infrastructure/terraform/` stays free of modules, backends, subscription ids, tenant ids, and credentials. There is no workspace. `terraform plan` and `terraform apply` are not part of this slice
- Backup expectations and secret-management notes are in `docs/operations/`. Local secrets stay in an uncommitted `.env`. Managed secrets apply only after a cloud deployment exists. That deployment does not exist
- No ADR. The stack choice was already OpenTelemetry. This slice does not change the deployment shape
- The case study is PORT-1
- Acceptance: with the exporter unset, the app starts and `GET /health` still returns `status=ok` and `service=wasatch-api`. That test does not call a network

### PORT-1 — Laboratory case study

- Status: done in this change
- Depends on: the laboratory slice through OPS-1 (`1be4181`, pull request [#20](https://github.com/anotherhale/ai-solutions-lab/pull/20))
- The study is [docs/case-studies/wasatch-laboratory-slice.md](docs/case-studies/wasatch-laboratory-slice.md). The index is [docs/case-studies/README.md](docs/case-studies/README.md)
- It states what is in the repository on `develop`, what was simulated, and which measurements are already recorded in `PROJECT_STATUS.md`. Every test count it cites names that file as the source
- `main` stays the production branch name. The study does not describe `main` as a deployed product
- No route, provider call, collector, Azure environment, Terraform module, n8n workflow, Redis instance, or new measurement is added
- Application behavior, tests, and the CI database gate are unchanged
- Acceptance: a reader can finish the study without taking the laboratory actor header, the fake provider, an approval, a follow-up confirmation, or a trace span as a production result

### DOC-UI-1 — Extraction review surface

- Status: done in this change
- Depends on: document extraction review (`6e92af9`) and the existing review screen (`13826ed`)
- `apps/wasatch-review` can open one synthetic extraction such as `dx_0003`, show the untrusted extracted fields, and let an approver accept or reject it.
- The decision route is `/api/v1/document-extractions/{extraction_id}/decisions`.
- The page does not post an invoice, change a payment, trust future extraction output, call a model, send a customer message, or add a new app.
- Acceptance: `emp_0001` can accept or reject `dx_0003` from the review screen. The request body carries only the decision and note, and no invoice, payment, delivery, or provider URL is called.

## After the customer-service slice

These follow [docs/ROADMAP.md](docs/ROADMAP.md). Dates in that roadmap are planning windows, not commitments. Do not start them by pulling infrastructure forward.

| ID | Phase | Work | Depends on |
|---|---|---|---|
| DOC-P3 | 3 | Human review for low-confidence and financial extractions. | Done in this change. See the DOC-P3 section. Embeddings are not this item. |
| EMB-1 | 3 | Embeddings in the existing PostgreSQL instance when a task fills the embedding port. | Done in this change. `procedure_page_embeddings.embedding` is `vector(8)`. Only procedure text is stored. Version rows are still path strings. |
| WF-1 | 4 | One multi-step Wasatch workflow with human approval and an audit trail. n8n only for an edge automation that the monolith does not own as the system of record. | Done. See the WF-1 section. The case study is PORT-1. |
| OPS-1 | 5 | Host traces and laboratory backup and secret notes. Export spans only when `OTEL_EXPORTER_OTLP_ENDPOINT` is set. No collector, no Terraform workspace, no Azure module, no credential. | Done. See the OPS-1 section. The case study is PORT-1. |
| PORT-1 | 6 | One case study that states what was simulated and what was measured. | Done in this change. See the PORT-1 section. Documentation only. No new runtime. |

Redis remains deferred until a module needs a cache or a short-lived lock. Kafka, Kubernetes, and a microservice split stay out until an ADR records a requirement the modular monolith cannot meet.

## Technical debt

Carry these until a task above closes them. Do not weaken the checks that already pass.

| Item | Where it shows up |
|---|---|
| Unauthenticated reads of synthetic customer and employee data | Closed by CS-3. `/api/v1` reads require the `X-Laboratory-Actor` header. |
| No structured logs | Closed by CS-3. `APP_LOG_LEVEL` configures JSON logs of actor, action, subject, and outcome. Message bodies and secrets are omitted. |
| Thin HTTP contract tests | Closed. `tests/api/test_openapi_contract.py` and `openapi_contract_catalog.py` assert the full slice path/method catalog, write-route methods, decision enums, and runtime error envelopes. `tests/unit/test_contract_alignment.py` still aligns JSON Schema status enums. |
| Downgrade is untested | Closed for revisions `0001`–`0012`. Matrix in `services/wasatch-api/tests/integration/README.md`. Each revision has an integration upgrade/downgrade test, including `test_initial_migration.py` for `0001`, `test_invoice_line_migration.py` for `0010`, `test_payment_migration.py` for `0011`, and `test_alembic_migration_graph.py` for `0012`. |
| Pytest skip when PostgreSQL is absent | `tests/conftest.py` still skips a local run when PostgreSQL is down. CI fails that skip. Pull request [#11](https://github.com/anotherhale/ai-solutions-lab/pull/11) (`d1178e8`) sets `WASATCH_REQUIRE_DATABASE=1`, and `scripts/check_wasatch_api_pytest.py` rejects a run that did not execute the database tests. |
| String foreign key for invoices | Closed for `work_orders.invoice_id`. Revision `0008` adds `invoices` and a foreign key to `invoices.business_id`. Document `invoice_id` stays a string. Revisions `0010` and `0011` persist `invoice_lines` and `payments` with read-only routes (FIN-2, FIN-3). |
| `python3 -m ruff` missing on the system interpreter in this environment | RUFF-1's environment install, which is outside the git diff. The pin itself landed in `ec6465f`. |
| Starlette `TestClient` deprecation warning | Closed. Starlette 1.10 uses `anyio.from_thread.BlockingPortal`. `anyio>=4.8.0,<5` matches that bound. The earlier `<4.15` cap applied to Starlette 0.50. |
| No Compose image smoke test in CI | Closed. `scripts/smoke_compose.sh` runs in the **Compose API smoke** GitHub Actions job. |
| Review-screen checks not in CI | Closed. **Wasatch review frontend** job runs Vitest, typecheck, and production build. |
| No browser suite for review workflows | Closed. Playwright specs in `tests/e2e/` run in **Review workbench browser tests**. |
| No dependency-audit tool | Closed. `scripts/audit_wasatch_dependencies.sh` runs `pip-audit` on the installed Wasatch API environment in CI. |
| Starlette PYSEC advisories on the pinned FastAPI stack | Closed by SEC-1. ADR 0007 is Accepted. The audit script does not ignore Starlette IDs. |
| GitHub required checks on `develop` | Closed. Ruleset `develop-protection` is active with all five **Repository Validation** job names required (verified 2026-11-04 via GitHub rulesets API). |

### SEC-1 — Implement ADR 0007 (FastAPI / Starlette remediation)

- Status: done in this change. Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/29
- Depends on: ADR 0007 (pull request [#28](https://github.com/anotherhale/ai-solutions-lab/pull/28), `8c950ce`), which recorded the plan as Proposed
- `fastapi>=0.162.0,<0.163` and direct `starlette>=1.10.0,<1.11`. Resolved versions are FastAPI 0.162.0 and Starlette 1.10.0. The spike minimum was Starlette 1.3.1. 1.10.0 is the patched 1.x release this change audited.
- `create_app` does not pass `on_startup`. FastAPI 0.162 keeps lifecycle handlers off Starlette's `Router`. `TestClient` enters the default lifespan and `GET /health` still returns `status` `ok`.
- `anyio>=4.8.0,<5`. Starlette 1.10 uses `anyio.from_thread.BlockingPortal`, so the `<4.15` cap is gone.
- `scripts/audit_wasatch_dependencies.sh` has no Starlette `--ignore-vuln` entries. `pip-audit` reports no known vulnerabilities.
- ADR 0007 is Accepted. OpenTelemetry instrumentation stays `0.66b2`. Uvicorn stays `>=0.32.1,<0.38`.
- Acceptance: full pytest with `WASATCH_REQUIRE_DATABASE=1` passed locally (198 passed, 0 skipped). `pip-audit` was clean. Repository Validation on the pull request is the remaining check for the five jobs. No customer delivery and no financial posting.

### FIN-1 — Read-only invoice routes

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/31 (`fdb3947`); also on `develop` via [#33](https://github.com/anotherhale/ai-solutions-lab/pull/33)
- Depends on: revision `0008` and SEC-1
- Read-only invoice list and detail routes; no posting.

### FIN-2 — Read-only invoice line routes

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/34 merged as `7ed13ec`
- Depends on: FIN-1, revision `0010`
- Alembic `0010` persists `invoice_lines` from `data/fixtures/valid/invoice_lines.json` (40 rows). Money columns are reference amounts only.
- `GET /api/v1/invoices/{invoice_id}/lines` and `GET /api/v1/invoice-lines/{invoice_line_id}` require the laboratory actor.
- No posting, payment tables, or write routes.
- Acceptance: migration upgrade/downgrade test, API tests, OpenAPI catalog, CI green.

### FIN-3 — Read-only payment routes

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/35 merged as `b0d9c3c`
- Depends on: FIN-2, revision `0011`
- Alembic `0011` persists `payments` from fixtures (20 rows). Reference amounts only; no posting command.
- `GET /api/v1/payments` and `GET /api/v1/payments/{payment_id}` require the laboratory actor.
- Acceptance: migration test, API tests, finance guard tests assert payment row count unchanged on unrelated writes.

### CONTRACT-FIN-1 — Finance enum alignment with JSON Schema

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/39 merged as `3c9a933`
- Depends on: FIN-3
- Extend `tests/unit/test_contract_alignment.py` so invoice, invoice line, and payment filter enums match `data/schemas/v1/finance/*.schema.json`.
- No API or migration changes.
- Acceptance: unit test passes; repository validators unchanged; CI green.

### OPENAPI-FIN-QP-1 — Finance list query parameters in OpenAPI contract tests

- Status: in progress (this change)
- Depends on: CONTRACT-FIN-1 (merged)
- Assert OpenAPI documents optional list filters on finance and work-order read routes in `tests/api/test_openapi_contract.py`.
- No route or migration changes.
- Acceptance: contract tests pass; `python3 scripts/validate_repo.py` passes; CI green.

### COORD-SYNC-1 — Reconcile coordinator backlog catalog after finance slice

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/48 merged as `a5f46e7`
- Depends on: CONTRACT-FIN-1
- Mark `data/coordinator/backlog.yaml` tasks merged for pull requests [#37](https://github.com/anotherhale/ai-solutions-lab/pull/37), [#38](https://github.com/anotherhale/ai-solutions-lab/pull/38), and [#39](https://github.com/anotherhale/ai-solutions-lab/pull/39).
- Record CONTRACT-FIN-1 and coordinator continuity documentation in `PROJECT_STATUS.md`. Close the stale technical-debt note that payments are fixture-only.
- Register follow-on `pending` tasks in `data/coordinator/backlog.yaml` so the coordinator can schedule after merge.
- No application code or migration changes.
- Acceptance: `python3 scripts/validate_repo.py` passes; coordinator tick can select the next pending catalog task.

### COORD-PR-SLOT-1 — PR_OPEN tasks do not consume concurrency slots

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/58 merged as `defca15`
- Depends on: none
- Count only runtime `in_progress` toward `DEVELOPMENT_OPS_MAX_CONCURRENT`, not `pr_open` tasks awaiting human review.
- Acceptance: `libs/development_ops` scheduling tests and `test_coordinator_continuity.py` pass; coordinator tick selects a pending task when several documentation pull requests are open.

### COORD-CATALOG-2 — Consolidate coordinator catalog after finance documentation merges

- Status: done. Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/61 merged as `bcf404b`
- Depends on: none
- Supersedes overlapping catalog-only pull requests that each updated `data/coordinator/backlog.yaml` after merges [#49](https://github.com/anotherhale/ai-solutions-lab/pull/49), [#56](https://github.com/anotherhale/ai-solutions-lab/pull/56), and [#58](https://github.com/anotherhale/ai-solutions-lab/pull/58).
- Mark merged catalog rows for DOC-DBMAP-1, DOC-README-FIN-1, and COORD-PR-SLOT-1. Set STATUS-2 to `pending` with dependencies on the remaining open documentation tasks.
- Documentation only; no application code.
- Acceptance: `python3 scripts/validate_repo.py` passes; coordinator tick does not assign duplicate catalog reconciliation work.

### DOC-DBMAP-1 — Finance persistence in DATABASE_MAPPING.md

- Status: done. Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/49 merged as `76e6e3f`
- Depends on: CONTRACT-FIN-1 (merged); catalog reconciles on COORD-SYNC-1
- Update `docs/architecture/DATABASE_MAPPING.md` for Alembic `0008`, `0010`, and `0011`: `invoices`, `invoice_lines`, and `payments` seeded from `data/fixtures/valid/`. Remove the stale deferred-entity note for Invoice, InvoiceLine, and Payment.
- Document `NUMERIC` money columns as reference amounts only. Read routes do not post finance.
- No schema, migration, or API changes.
- Acceptance: `python3 scripts/validate_repo.py` passes; the table list matches the repository.

### DOC-DEBT-MIG-1 — Downgrade coverage note through revision 0011

- Status: done on `ai-dev` (not yet on `develop`). Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/50 merged as `2ba5877`
- Depends on: CONTRACT-FIN-1 (merged); catalog reconciles on COORD-SYNC-1
- Update the technical-debt table in this file so downgrade coverage cites revisions `0001`–`0011` and points at `services/wasatch-api/tests/integration/README.md` for `0010` and `0011`.
- Documentation only.
- Acceptance: `python3 scripts/validate_repo.py` passes.

### PORT-CASE-FIN-1 — Case study finance read slice

- Status: done on `ai-dev` (not yet on `develop`). Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/51 merged as `997d582`
- Depends on: CONTRACT-FIN-1 (merged)
- Update `docs/case-studies/wasatch-laboratory-slice.md` so finance capabilities match FIN-1–FIN-3: read-only invoices, lines, and payments; no posting.
- Documentation only; independent of COORD-SYNC-1.
- Acceptance: `python3 scripts/validate_repo.py` passes; case study matches `develop` behavior.

### DOC-README-FIN-1 — Finance read routes in wasatch-api README

- Status: done. Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/56 merged as `7df5a56`
- Depends on: FIN-3 (merged)
- Document invoice, invoice line, and payment read routes in `services/wasatch-api/README.md`.
- Documentation only; no API changes.
- Acceptance: `python3 scripts/validate_repo.py` passes.

### DOC-API-FIN-1 — Payment read routes in API_CONVENTIONS.md

- Status: done on `ai-dev` (not yet on `develop`). Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/54 merged as `4fd8680`
- Depends on: FIN-3 (merged)
- Add `GET /api/v1/payments` and `GET /api/v1/payments/{payment_id}` to the route catalog in `docs/architecture/API_CONVENTIONS.md`, with laboratory-actor requirement and reference-amounts-only wording consistent with invoice routes.
- Documentation only; no API changes.
- Acceptance: `python3 scripts/validate_repo.py` passes; the table matches `openapi_contract_catalog.py`.

### STATUS-2 — Refresh PROJECT_STATUS after finance documentation

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/71
- Merge: `0b8a571`
- Depends on: DOC-DEBT-MIG-1, DOC-API-FIN-1, PORT-CASE-FIN-1, and COORD-CATALOG-2
- Updated `PROJECT_STATUS.md` current-work and verification sections after finance documentation integrated on `ai-dev`.
- Documentation only.
- Acceptance met: `python3 scripts/validate_repo.py` passes; coordinator catalog marks STATUS-2 merged.

### COORD-CATALOG-3 — Mark STATUS-2 merged in coordinator catalog

- Status: in progress (pull request [#72](https://github.com/anotherhale/ai-solutions-lab/pull/72))
- Depends on: STATUS-2
- Set `STATUS-2` to `merged` at `0b8a571` in `data/coordinator/backlog.yaml`. Register `DOC-ENG-AIDEV-1` and follow-on `pending` tasks for the coordinator.
- Documentation only.
- Acceptance: `python3 scripts/validate_repo.py` passes; coordinator tick can select a pending task after merge.

### DOC-ENG-AIDEV-1 — Document the `ai-dev` integration branch

- Status: done in this change
- Depends on: STATUS-2
- `develop` remains the integration branch for the Wasatch API laboratory slice and finance read routes documented in this file.
- `ai-dev` is the integration branch for autonomous development capabilities (Phase D child-agent orchestration, AI review gate, extended Alembic head through `0016`). Finance and coordinator documentation may land on `ai-dev` before promotion to `develop`.
- Open pull requests targeting `ai-dev` do not block coordinator scheduling on `develop`. Each branch has its own catalog rows in `data/coordinator/backlog.yaml` when the automation entrypoint runs against that branch.
- Documentation only; no application code.
- Acceptance: `python3 scripts/validate_repo.py` passes; a new reader can tell which branch owns autonomous tooling versus the Wasatch slice.

## Integration branch summary

| Branch | Role |
|---|---|
| `develop` | Wasatch slice, finance read routes, `apps/wasatch-review`, coordinator catalog default |
| `ai-dev` | Autonomous agents, review gate, child orchestration, ahead migrations until promoted |

### FIN-4 — Filter work orders by `invoice_id`

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/73
- Merge: `d54ff60`
- Depends on: FIN-3
- Optional `invoice_id` query parameter on `GET /api/v1/work-orders`; filter uses `work_orders.invoice_id` from Alembic `0008`. Documented in `API_CONVENTIONS.md`; API tests added.
- Acceptance met: filtered list returns only matching work orders; CI green.

### STATUS-3 — Refresh PROJECT_STATUS after DOC-ENG-AIDEV-1

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/74
- Merge: `f6469ea`
- Depends on: DOC-ENG-AIDEV-1
- Updated integration-branch summary and baseline through pull request #72. Documentation only.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### COORD-CATALOG-4 — Mark FIN-4 and STATUS-3 merged in coordinator catalog

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/76
- Merge: `2517ce4`
- Depends on: STATUS-3
- Reconciled `data/coordinator/backlog.yaml` after pull requests #73 and #74. Registered follow-on tasks.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### STATUS-4 — Refresh PROJECT_STATUS after FIN-4 and catalog reconciliation

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/76
- Merge: `2517ce4`
- Depends on: FIN-4 and STATUS-3
- Updated `PROJECT_STATUS.md` for FIN-4 and catalog reconciliation (same pull request as COORD-CATALOG-4).
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### DOC-README-FIN-4 — Work-order `invoice_id` filter in service README

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/77
- Merge: `a0cc77c`
- Depends on: FIN-4
- Documented optional `invoice_id` on `GET /api/v1/work-orders` in `services/wasatch-api/README.md`.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### COORD-CATALOG-5 — Mark DOC-README-FIN-4 merged in coordinator catalog

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/78
- Merge: `c095cfe`
- Depends on: DOC-README-FIN-4
- Reconcile `data/coordinator/backlog.yaml` after pull request #77.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### STATUS-5 — Refresh PROJECT_STATUS after DOC-README-FIN-4

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/78
- Merge: `c095cfe`
- Depends on: DOC-README-FIN-4
- Updated `PROJECT_STATUS.md` baseline and finance documentation rows through #77.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### COORD-CATALOG-6 — Mark COORD-CATALOG-5 and STATUS-5 merged after #78

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/79
- Merge: `274703c`
- Depends on: COORD-CATALOG-5 and STATUS-5
- Reconciled catalog after pull request #78 and registered DOC-API-FIN-4.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### DOC-API-FIN-4 — Work-order `invoice_id` filter in API_CONVENTIONS.md

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/79
- Merge: `274703c`
- Depends on: FIN-4
- Documented optional `invoice_id` on `GET /api/v1/work-orders` in `docs/architecture/API_CONVENTIONS.md`, including an example request.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### COORD-CATALOG-7 — Mark COORD-CATALOG-6 and DOC-API-FIN-4 merged after #79

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/80
- Merge: `0d3d894`
- Depends on: COORD-CATALOG-6 and DOC-API-FIN-4
- Registered PORT-CASE-FIN-2 as `pending` in the coordinator catalog.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### STATUS-6 — Refresh PROJECT_STATUS after DOC-API-FIN-4

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/80
- Merge: `0d3d894`
- Depends on: DOC-API-FIN-4
- Updated `PROJECT_STATUS.md` baseline and finance documentation rows through #79.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### PORT-CASE-FIN-2 — Case study finance read slice on `develop`

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/84
- Merge: `fb27969`
- Depends on: FIN-4 and DOC-API-FIN-4
- Extended `docs/case-studies/wasatch-laboratory-slice.md` with read-only finance routes on `develop`, including optional `invoice_id` on `GET /api/v1/work-orders`.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### COORD-CATALOG-9 — Mark PORT-CASE-FIN-2 merged after #84

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/85
- Merge: `00ef109`
- Depends on: PORT-CASE-FIN-2, COORD-CATALOG-7, and STATUS-6
- Reconciled `data/coordinator/backlog.yaml` after pull request #84; registered `COORD-ENTRY-SYNC-1` and `DOC-DEBT-MIG-2`.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### STATUS-7 — Refresh PROJECT_STATUS after PORT-CASE-FIN-2

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/85
- Merge: `00ef109`
- Depends on: PORT-CASE-FIN-2
- Updated `PROJECT_STATUS.md` baseline through #84 and open-pull-request notes.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### COORD-ENTRY-SYNC-1 — Sync coordinator catalog from origin/develop before tick

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/85
- Merge: `00ef109`
- Depends on: none
- `scripts/coordinator_sync_integration_backlog.sh` copies `data/coordinator/backlog.yaml` from `origin/develop` when the remote catalog lists more tasks than the working tree (typical when Cloud Agents boot from `main`).
- `scripts/coordinator_automation_entrypoint.sh` invokes the sync step before `development-ops-record coordinator tick`.
- Acceptance met: `python3 scripts/validate_repo.py` passes; coordinator continuity integration test still passes.

### DOC-DEBT-MIG-2 — Align ENGINEERING_BACKLOG downgrade debt through Alembic 0012

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/86
- Merge: `62067a2`
- Depends on: COORD-ENTRY-SYNC-1
- Updated the technical-debt table so downgrade coverage cites revisions `0001`–`0012` and matches `services/wasatch-api/tests/integration/README.md`.
- Documentation only.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### COORD-CATALOG-10 — Mark DOC-DEBT-MIG-2 merged after #86

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/87
- Merge: `e8c2a22`
- Depends on: DOC-DEBT-MIG-2, COORD-ENTRY-SYNC-1, and STATUS-7
- Reconciled `data/coordinator/backlog.yaml` after pull request #86; registered `DOC-DBMAP-2`.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### STATUS-8 — Refresh PROJECT_STATUS after DOC-DEBT-MIG-2

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/87
- Merge: `e8c2a22`
- Depends on: DOC-DEBT-MIG-2
- Updated baseline, current-work table, and superseded open-pull-request notes through #85 and #86.
- Documentation only.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### DOC-DBMAP-2 — Coordinator scheduling tables in DATABASE_MAPPING.md

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/95
- Merge: `e3e2e5e8`
- Depends on: COORD-CATALOG-10
- Updated `docs/architecture/DATABASE_MAPPING.md` for the `development_ops` schema and coordinator task lifecycle. Documentation only.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### COORD-CATALOG-11 — Mark DOC-DBMAP-2 merged after #95

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/96
- Merge: `2b9f3e45`
- Depends on: DOC-DBMAP-2
- Reconciled `data/coordinator/backlog.yaml` after pull request #95; marked DOC-DBMAP-2 and COORD-BACKLOG-PR-OPEN-1 merged.
- Acceptance met: coordinator tick runs without held dependency on DOC-DBMAP-2.

### STATUS-9 — Refresh PROJECT_STATUS after DOC-DBMAP-2

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/96
- Merge: `2b9f3e45`
- Depends on: DOC-DBMAP-2
- Updated baseline, current-work table, and open-pull-request notes through #95.
- Documentation only.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### COORD-CATALOG-12 — Mark COORD-CATALOG-11 and STATUS-9 merged after #96

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/97
- Merge: `93c23c5`
- Depends on: COORD-CATALOG-11 and STATUS-9
- Reconciled `data/coordinator/backlog.yaml` after pull request #96.
- Documentation only.
- Acceptance met: `python3 scripts/validate_repo.py` passes; coordinator tick can select work after merge.

### STATUS-10 — Refresh PROJECT_STATUS after #96

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/97
- Merge: `93c23c5`
- Depends on: COORD-CATALOG-11 and STATUS-9
- Updated baseline and open-pull-request notes after #96 merge.
- Documentation only.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### COORD-CATALOG-13 — Mark COORD-CATALOG-12 and STATUS-10 merged after #97

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/98
- Merge: `2ade1ae`
- Depends on: COORD-CATALOG-12 and STATUS-10
- Reconciled `data/coordinator/backlog.yaml` after pull request #97.
- Documentation only.
- Acceptance met: `python3 scripts/validate_repo.py` passes; develop catalog has no stale `in_progress` rows for merged work.

### STATUS-11 — Refresh PROJECT_STATUS after #97

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/98
- Merge: `2ade1ae`
- Depends on: COORD-CATALOG-12 and STATUS-10
- Updated baseline and open-pull-request notes after #97 merge.
- Documentation only.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### COORD-CATALOG-14 — Mark COORD-CATALOG-13 and STATUS-11 merged after #98

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/99
- Merge: `b85f529`
- Depends on: COORD-CATALOG-13 and STATUS-11
- Reconciled `data/coordinator/backlog.yaml` after pull request #98.
- Documentation only.
- Acceptance met: `python3 scripts/validate_repo.py` passes; develop catalog has no stale `in_progress` rows for merged #98 work.

### STATUS-12 — Refresh PROJECT_STATUS after #98

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/99
- Merge: `b85f529`
- Depends on: COORD-CATALOG-13 and STATUS-11
- Updated baseline and open-pull-request notes after #98 merge.
- Documentation only.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### COORD-CATALOG-15 — Mark COORD-CATALOG-14 and STATUS-12 merged after #99

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/100
- Merge: `3e8735a`
- Depends on: COORD-CATALOG-14 and STATUS-12
- Reconciled `data/coordinator/backlog.yaml` after pull request #99.
- Documentation only.
- Acceptance met: `python3 scripts/validate_repo.py` passes; develop catalog has no stale `in_progress` rows for merged #99 work.

### STATUS-13 — Refresh PROJECT_STATUS after #99

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/100
- Merge: `3e8735a`
- Depends on: COORD-CATALOG-14 and STATUS-12
- Updated baseline and open-pull-request notes after #99 merge.
- Documentation only.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### COORD-CATALOG-16 — Mark COORD-CATALOG-15 and STATUS-13 merged after #100

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/101
- Merge: `2ebae87`
- Depends on: COORD-CATALOG-15 and STATUS-13
- Reconciled `data/coordinator/backlog.yaml` after pull request #100.
- Documentation only.
- Acceptance met: `python3 scripts/validate_repo.py` passes; coordinator tick can select work after merge.

### STATUS-14 — Refresh PROJECT_STATUS after #100

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/101
- Merge: `2ebae87`
- Depends on: COORD-CATALOG-15 and STATUS-13
- Updated baseline and open-pull-request notes after #100 merge.
- Documentation only.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### COORD-CATALOG-17 — Mark COORD-CATALOG-16 and STATUS-14 merged after #101

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/102
- Merge: `00a3424`
- Depends on: COORD-CATALOG-16 and STATUS-14
- Reconciled `data/coordinator/backlog.yaml` after pull request #101.
- Documentation only.
- Acceptance met: `python3 scripts/validate_repo.py` passes; develop catalog has no stale `in_progress` rows for merged #101 work.

### STATUS-15 — Refresh PROJECT_STATUS after #101

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/102
- Merge: `00a3424`
- Depends on: COORD-CATALOG-16 and STATUS-14
- Updated baseline and open-pull-request notes after #101 merge.
- Documentation only.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### COORD-CATALOG-18 — Mark COORD-CATALOG-17 and STATUS-15 merged after #102

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/103
- Merge: `d03ba92`
- Depends on: COORD-CATALOG-17 and STATUS-15
- Reconciled `data/coordinator/backlog.yaml` after pull request #102.
- Acceptance met: `python3 scripts/validate_repo.py` passes; coordinator tick can select work after merge.

### STATUS-16 — Refresh PROJECT_STATUS after #102

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/103
- Merge: `d03ba92`
- Depends on: COORD-CATALOG-17 and STATUS-15
- Updated baseline and open-pull-request notes after #102 merge.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### COORD-CATALOG-19 — Mark COORD-CATALOG-18 and STATUS-16 merged after #103

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/104
- Merge: `f97cdda`
- Depends on: COORD-CATALOG-18 and STATUS-16
- Reconciled `data/coordinator/backlog.yaml` after pull request #103.
- Acceptance met: `python3 scripts/validate_repo.py` passes; coordinator tick can select work after merge.

### STATUS-17 — Refresh PROJECT_STATUS after #103

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/104
- Merge: `f97cdda`
- Depends on: COORD-CATALOG-18 and STATUS-16
- Updated baseline and open-pull-request notes after #103 merge.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### COORD-CATALOG-20 — Mark COORD-CATALOG-19 and STATUS-17 merged after #104

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/105
- Merge: `7a93c33`
- Depends on: COORD-CATALOG-19 and STATUS-17
- Reconciled `data/coordinator/backlog.yaml` after pull request #104.
- Acceptance met: `python3 scripts/validate_repo.py` passes; develop catalog has no stale `in_progress` rows for merged #104 work.

### STATUS-18 — Refresh PROJECT_STATUS after #104

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/105
- Merge: `7a93c33`
- Depends on: COORD-CATALOG-19 and STATUS-17
- Updated baseline and open-pull-request notes after #104 merge.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### COORD-CATALOG-21 — Mark COORD-CATALOG-20 and STATUS-18 merged after #105

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/106
- Merge: `a5d9749`
- Depends on: COORD-CATALOG-20 and STATUS-18
- Reconciled `data/coordinator/backlog.yaml` after pull request #105.
- Acceptance met: `python3 scripts/validate_repo.py` passes; develop catalog has no stale `in_progress` rows for merged #105 work.

### STATUS-19 — Refresh PROJECT_STATUS after #105

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/106
- Merge: `a5d9749`
- Depends on: COORD-CATALOG-20 and STATUS-18
- Updated baseline and open-pull-request notes after #105 merge.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### COORD-CATALOG-22 — Mark COORD-CATALOG-21 and STATUS-19 merged after #106

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/107
- Merge: `6ba8f31`
- Depends on: COORD-CATALOG-21 and STATUS-19
- Reconciled `data/coordinator/backlog.yaml` after pull request #106.
- Acceptance met: `python3 scripts/validate_repo.py` passes; develop catalog has no stale `in_progress` rows for merged #106 work.

### STATUS-20 — Refresh PROJECT_STATUS after #106

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/107
- Merge: `6ba8f31`
- Depends on: COORD-CATALOG-21 and STATUS-19
- Updated baseline and open-pull-request notes after #106 merge.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### COORD-CATALOG-23 — Mark COORD-CATALOG-22 and STATUS-20 merged after #107

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/108
- Merge: `1a95933`
- Depends on: COORD-CATALOG-22 and STATUS-20
- Reconciled `data/coordinator/backlog.yaml` after pull request #107.
- Acceptance met: `python3 scripts/validate_repo.py` passes; develop catalog has no stale `in_progress` rows for merged #107 work.

### STATUS-21 — Refresh PROJECT_STATUS after #107

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/108
- Merge: `1a95933`
- Depends on: COORD-CATALOG-22 and STATUS-20
- Updated baseline and open-pull-request notes after #107 merge.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### COORD-CATALOG-24 — Mark COORD-CATALOG-23 and STATUS-21 merged after #108

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/109
- Merge: `55c4386`
- Depends on: COORD-CATALOG-23 and STATUS-21
- Reconciled `data/coordinator/backlog.yaml` after pull request #108.
- Acceptance met: `python3 scripts/validate_repo.py` passes; develop catalog has no stale `in_progress` rows for merged #108 work.

### STATUS-22 — Refresh PROJECT_STATUS after #108

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/109
- Merge: `55c4386`
- Depends on: COORD-CATALOG-23 and STATUS-21
- Updated baseline and open-pull-request notes after #108 merge.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### COORD-CATALOG-25 — Mark COORD-CATALOG-24 and STATUS-22 merged after #109

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/110
- Merge: `a759dcd`
- Depends on: COORD-CATALOG-24 and STATUS-22
- Reconciled `data/coordinator/backlog.yaml` after pull request #109.
- Acceptance met: `python3 scripts/validate_repo.py` passes; develop catalog has no stale `in_progress` rows for merged #109 work.

### STATUS-23 — Refresh PROJECT_STATUS after #109

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/110
- Merge: `a759dcd`
- Depends on: COORD-CATALOG-24 and STATUS-22
- Updated baseline and open-pull-request notes after #109 merge.
- Acceptance met: `python3 scripts/validate_repo.py` passes.

### COORD-CATALOG-26 — Mark COORD-CATALOG-25 and STATUS-23 merged after #110

- Status: in progress
- Depends on: COORD-CATALOG-25 and STATUS-23
- Reconciled `data/coordinator/backlog.yaml` after pull request #110.
- Documentation only.
- Acceptance: `python3 scripts/validate_repo.py` passes; develop catalog has no stale `in_progress` rows for merged #110 work.

### STATUS-24 — Refresh PROJECT_STATUS after #110

- Status: in progress
- Depends on: COORD-CATALOG-25 and STATUS-23
- Updated baseline and open-pull-request notes after #110 merge.
- Documentation only.
- Acceptance: `python3 scripts/validate_repo.py` passes.

### OPENAPI-FIN-QP-1 — Finance list query parameters in OpenAPI contract tests

- Status: pending
- Depends on: STATUS-24
- Extend `tests/api/test_openapi_contract.py` (or a focused companion) so OpenAPI documents optional list filters already implemented in the API: `invoice_id` on `GET /api/v1/work-orders` and `GET /api/v1/payments`, and status or type filters on finance read routes where they exist in the published schema.
- No route or migration changes.
- Acceptance: contract tests pass; `python3 scripts/validate_repo.py` passes; CI green.

### COORD-BACKLOG-PR-OPEN-1 — Catalog lifecycle statuses

- Status: done
- Pull request: https://github.com/anotherhale/ai-solutions-lab/pull/95
- Merge: `e3e2e5e8`
- Depends on: none
- One coordinator task lifecycle with monotonic catalog sync and `merge_ready` independent of auto-merge eligibility (Alembic `0013`).
- Acceptance met: `pytest libs/development_ops` passes; `ruff check` passes.

## Explicitly out of the next implementation

- Rebuilding Phase 2.1.1
- A second fixture generator output or a renamed copy of the domain
- Sending customer communications
- Financial posting, price changes, schedule changes, and bulk export
- Production deployment, purchased services, cloud credentials, and production API keys
- Microservices, Kubernetes, Kafka, and Nx
