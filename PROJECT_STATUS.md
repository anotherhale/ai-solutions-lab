# Project Status

Snapshot of AI Solutions Lab as verified on 2026-11-13. Wasatch Business Systems is a fictional company. All business records in this repository are synthetic.

This file records what is in the repository and what was run. Forward work is in [ENGINEERING_BACKLOG.md](ENGINEERING_BACKLOG.md). Phase design is in [docs/architecture/IMPLEMENTATION_PLAN.md](docs/architecture/IMPLEMENTATION_PLAN.md). Contributor and agent rules for integration are in [docs/architecture/AGENT_OPERATING_MODEL.md](docs/architecture/AGENT_OPERATING_MODEL.md).

If this snapshot disagrees with the code, the code wins. Update this file in the same change that alters the snapshot.

## Baseline

| Item | Value |
|---|---|
| Assessed commit | `93c23c5fee314fb5ac8b4dc54d4b14ef84c9297a` |
| Commit subject | COORD-CATALOG-12: catalog and PROJECT_STATUS after #96 (#97) |
| Integration branch | `develop` at `93c23c5` |
| Autonomous integration branch | `ai-dev` at `0af252d` (`git rev-list --left-right --count develop...ai-dev` → `20`/`21` on 2026-11-13) |
| Production branch | `main` at `881cfc0` (unchanged at assessment) |
| Relationship | `develop` is ahead of `main`. Laboratory work integrates on `develop` only. |

`main` is the production branch. Work integrates on `develop`. Merges to `main` are out of scope for laboratory agents.

That relationship was true at `881cfc0`. `develop` later received the Ruff pin (`ec6465f`), the `develop` CI trigger (`ecd3015`), ADR 0001 acceptance (`c18ad80`), this planning set (`6cb587a`), CS-1 (`047702e`, pull request [#7](https://github.com/anotherhale/ai-solutions-lab/pull/7)), CS-2 (`7760106`, pull request [#8](https://github.com/anotherhale/ai-solutions-lab/pull/8)), CS-3 (`5b2ffc4`, pull request [#9](https://github.com/anotherhale/ai-solutions-lab/pull/9)), the laboratory-actor production boundary (`ac26535`, pull request [#10](https://github.com/anotherhale/ai-solutions-lab/pull/10)), the CI database gate (`d1178e8`, pull request [#11](https://github.com/anotherhale/ai-solutions-lab/pull/11)), CS-5 retrieval (`a03fea9`, pull request [#12](https://github.com/anotherhale/ai-solutions-lab/pull/12)), CS-4 approval decisions (`0785ab9`, pull request [#13](https://github.com/anotherhale/ai-solutions-lab/pull/13)), and CS-6 suggested replies (`781bcc0`, pull request [#14](https://github.com/anotherhale/ai-solutions-lab/pull/14)), and CS-7 review surface (`13826ed`, pull request [#15](https://github.com/anotherhale/ai-solutions-lab/pull/15)). Later merges through OPS-1 are under Current work. The parent of PORT-1 is `develop` at `1be41811fb290a8c026157eeeb0456cbd02c693b`. On 2026-11-04, `origin/main` was still `881cfc0`. `git rev-list --left-right --count origin/main...origin/develop` printed `0` then `19`. `develop` was 19 commits ahead. `main` is not a deployed product.

## Remote branches observed

| Branch | Tip | Notes |
|---|---|---|
| `main` | `881cfc0` | Production branch. Same commit as `develop` at the assessment. |
| `develop` | `93c23c5` | Wasatch slice, finance read routes, coordinator lifecycle (ADR 0009, Alembic `0013`), catalog through COORD-CATALOG-12 (#97). Application database Alembic head `0013` on `development_ops`; Wasatch API head `0012`. |
| `ai-dev` | `0af252d` | Autonomous agents, review gate, Alembic head through `0016` until promoted to `develop`. |
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
| CS-7 review surface | Done. Pull request [#15](https://github.com/anotherhale/ai-solutions-lab/pull/15) merged as `13826ed`. `apps/wasatch-review` is the first React and TypeScript application. No Nx. A reviewer opens one synthetic inquiry, reads the suggested reply, and approves or rejects it through the local API with `X-Laboratory-Actor`. `emp_0001` is an approver. `emp_0004` is not. Anonymous access is unauthorized. The screen has no send control and does not call a delivery system. |
| Document fixture persistence | Done. Pull request [#16](https://github.com/anotherhale/ai-solutions-lab/pull/16) merged as `78877e6`. Alembic revision `0005` stores documents, document versions, and document extractions from `data/fixtures/valid/`. Counts are 30, 31, and 18. Read routes are `GET /api/v1/documents`, `GET /api/v1/documents/{document_id}`, `GET /api/v1/document-versions`, `GET /api/v1/document-versions/{version_id}`, `GET /api/v1/document-extractions`, and `GET /api/v1/document-extractions/{extraction_id}`. They require `X-Laboratory-Actor`. `invoice_id` stays a string. `extracted_fields` is JSONB. Revision `0005` does not add a vector column. Version `storage_path` values are still not files in the repository. |
| Document extraction review | Done. Pull request [#17](https://github.com/anotherhale/ai-solutions-lab/pull/17) merged as `6e92af9`. An approver accepts or rejects an extraction that is awaiting review at `POST /api/v1/document-extractions/{extraction_id}/decisions`. Awaiting review means `needs_review`, `pending`, `succeeded`, or `failed`. `emp_0001` may decide. `emp_0004` is denied. Anonymous callers receive 401. The command stores status, `reviewed_by_employee_id`, `reviewed_at`, and optional `review_notes`, and inserts one `document_extraction.reviewed` audit event. Confidence below 0.8, a missing score, `needs_review`, an invoice or money key in `extracted_fields`, or a document `invoice_id` stays untrusted until that decision. A read, a seed, and a background job do not accept those rows. The command does not post a payment, change an invoice total, or mark an invoice posted. Invoices and payments are still fixtures only. That change did not add an embedding column. Alembic `0005` already stores the review columns. No file ingest, classifier, or model call. |
| EMB-1 procedure-page embeddings | Done. Pull request [#18](https://github.com/anotherhale/ai-solutions-lab/pull/18) merged as `068a185`. Alembic revision `0006` adds `procedure_page_embeddings.embedding` as `vector(8)`, the width the laboratory embedding port returns. The fake port is that default and is deterministic. An application service fills one vector per synthetic procedure page by calling `EmbeddingPort`. Infrastructure persists the vectors. Domain code does not import a vendor SDK and does not choose a different width. Only procedure text is embedded. Document version paths are still not files. Unaccepted, `needs_review`, low-confidence, and financial extractions are not inserted. Accepting an extraction does not post a payment, change an invoice, or index the extraction. Retrieval for `tkt_0015` still cites `proc_0001`, and the customer-history query stays. The stored vectors may order that procedure match. They are not a trusted semantic model. `AI_PROVIDER` stays `fake`. `openai` with the placeholder key `replace-me` fails before an OpenAI client is constructed. That change did not add a workflow. No Redis, n8n, or second vector database. |
| WF-1 follow-up visit | Done. Pull request [#19](https://github.com/anotherhale/ai-solutions-lab/pull/19) merged as `1b22eac`. Alembic revision `0007` stores `follow_up_visits`. `POST /api/v1/approval-requests/{approval_id}/follow-up-visits` is the command. Two human steps: an approver approves a pending `send_customer_message`, then a dispatcher (`role_0004`, including `emp_0004`) confirms or cancels the visit. The visit can be opened only from that approved request and stays `unscheduled` until the dispatcher decides. The approval does not open the visit, does not dispatch a technician, and does not mark `msg_0016` sent. Each transition inserts an audit event. Audit stays insert-only. Confirm and cancel do not post a payment, change an invoice total, mark an invoice posted, send a message, assign a technician, or create an appointment. No vector column. No n8n, Redis, Kafka, queue, or new service. No React screen. The review screen has no send control. `X-Laboratory-Actor` stays local, development, and test only. The case study is PORT-1 ([docs/case-studies/wasatch-laboratory-slice.md](docs/case-studies/wasatch-laboratory-slice.md)). |
| OPS-1 laboratory host traces | Done. Pull request [#20](https://github.com/anotherhale/ai-solutions-lab/pull/20) merged as `1be4181`. `create_app` records OpenTelemetry spans through `wasatch_api.observability`. Domain and application code does not import the SDK. Spans export over OTLP/HTTP only when `OTEL_EXPORTER_OTLP_ENDPOINT` is a non-empty URL. An unset or blank value does not construct an exporter and does not open a socket. Compose and GitHub Actions do not gain a collector, Redis, n8n, or a cloud account. Direct dependencies are pinned: `opentelemetry-api==1.45.2`, `opentelemetry-sdk==1.45.2`, `opentelemetry-exporter-otlp-proto-http==1.45.2`, `opentelemetry-instrumentation-fastapi==0.66b2`. `infrastructure/terraform/` has no module, backend, subscription id, tenant id, or credential. Backup expectations and secret notes are in `docs/operations/`. Local secrets stay in an uncommitted `.env`. GitHub Actions stays credential-free. Managed secrets apply only after a cloud deployment exists. That deployment does not exist. No ADR. The case study is PORT-1 ([docs/case-studies/wasatch-laboratory-slice.md](docs/case-studies/wasatch-laboratory-slice.md)). |
| PORT-1 laboratory case study | This change. Documentation only. The study is [docs/case-studies/wasatch-laboratory-slice.md](docs/case-studies/wasatch-laboratory-slice.md), indexed from [docs/case-studies/README.md](docs/case-studies/README.md). It states what is on `develop`, what was simulated, and which measurements are already recorded in this file. It does not add a route, a provider call, a collector, an Azure environment, a Terraform module, n8n, Redis, or a new measurement. Application behavior, tests, and the CI database gate are unchanged. `main` is not described as a deployed product. |
| Document extraction review screen | Done. Pull request [#22](https://github.com/anotherhale/ai-solutions-lab/pull/22). `apps/wasatch-review` opens synthetic extractions for approver decisions. |
| Work order invoice foreign key | Done. Pull request [#26](https://github.com/anotherhale/ai-solutions-lab/pull/26) merged as `e25fb91`. Alembic revision `0008` adds `invoices` and `work_orders.invoice_id` → `invoices.business_id`. |
| pip-audit in CI | Done. Pull request [#27](https://github.com/anotherhale/ai-solutions-lab/pull/27) merged as `13836b8`. **Wasatch API tests** job runs `scripts/audit_wasatch_dependencies.sh`. |
| Branch protection documentation and ADR 0007 | Done. Pull request [#28](https://github.com/anotherhale/ai-solutions-lab/pull/28) merged as `8c950ce`. `docs/operations/github-branch-protection.md`, migration matrix README, and ADR 0007 (Proposed at merge). |
| SEC-1 Starlette remediation | Done. Pull request [#29](https://github.com/anotherhale/ai-solutions-lab/pull/29) merged as `8b59a90`. FastAPI `>=0.162.0,<0.163` and Starlette `>=1.10.0,<1.11`. `pip-audit` runs without Starlette ignores. ADR 0007 is Accepted. Ruleset `develop-protection` requires all five **Repository Validation** jobs. |
| FIN-1 read-only invoice routes | Done. Pull request [#31](https://github.com/anotherhale/ai-solutions-lab/pull/31) / [#33](https://github.com/anotherhale/ai-solutions-lab/pull/33) (`fdb3947`). `GET /api/v1/invoices` and `GET /api/v1/invoices/{invoice_id}` return persisted reference rows only. No posting. |
| FIN-2 read-only invoice line routes | Done. Pull request [#34](https://github.com/anotherhale/ai-solutions-lab/pull/34) merged as `7ed13ec`. Alembic `0010` persists `invoice_lines` (40 rows). Read routes list lines per invoice and fetch one line by id. Reference amounts only. |
| FIN-3 read-only payment routes | Done. Pull request [#35](https://github.com/anotherhale/ai-solutions-lab/pull/35) merged as `b0d9c3c`. Alembic `0011` persists `payments` (20 rows). `GET /api/v1/payments` and `GET /api/v1/payments/{payment_id}` require the laboratory actor. No posting command. |
| Coordinator continuity (ADR 0009) | Done. Pull request [#37](https://github.com/anotherhale/ai-solutions-lab/pull/37) merged as `c0ed984`. Scheduling tick, `wasatch_development_ops`, and `data/coordinator/backlog.yaml`. See [docs/operations/COORDINATOR_CONTINUITY.md](docs/operations/COORDINATOR_CONTINUITY.md). |
| CONTRACT-FIN-1 finance enum alignment | Done. Pull request [#39](https://github.com/anotherhale/ai-solutions-lab/pull/39) merged as `3c9a933`. Unit contract tests align finance filter enums with `data/schemas/v1/finance/*.schema.json`. |
| COORD-SYNC-1 backlog catalog reconcile | Done. Pull request [#48](https://github.com/anotherhale/ai-solutions-lab/pull/48) merged as `a5f46e7`. `data/coordinator/backlog.yaml` and this file record merged finance and coordinator tasks; follow-on catalog entries are `pending` until their pull requests merge. |
| DOC-DBMAP-1 finance persistence mapping | Done. Pull request [#49](https://github.com/anotherhale/ai-solutions-lab/pull/49) merged as `76e6e3f`. `docs/architecture/DATABASE_MAPPING.md` documents Alembic `0008`, `0010`, and `0011` for `invoices`, `invoice_lines`, and `payments`. Read routes remain reference amounts only. |
| COORD-PR-SLOT-1 PR_OPEN slot accounting | Done. Pull request [#58](https://github.com/anotherhale/ai-solutions-lab/pull/58) merged as `defca15`. `pr_open` catalog rows awaiting human review do not consume `DEVELOPMENT_OPS_MAX_CONCURRENT` slots. |
| DOC-README-FIN-1 finance routes in service README | Done on `develop`. Pull request [#56](https://github.com/anotherhale/ai-solutions-lab/pull/56) merged as `7df5a56`. |
| COORD-CATALOG-2 coordinator catalog consolidate | Done. Pull request [#61](https://github.com/anotherhale/ai-solutions-lab/pull/61) merged as `bcf404b`. Catalog marks DOC-DBMAP-1, DOC-README-FIN-1, and COORD-PR-SLOT-1 merged; sets STATUS-2 pending until finance documentation integrates. |
| STATUS-2 finance documentation refresh | Done. Pull request [#71](https://github.com/anotherhale/ai-solutions-lab/pull/71) merged as `0b8a571`. Documentation only. |
| COORD-CATALOG-3 coordinator catalog after STATUS-2 | Done. Pull request [#72](https://github.com/anotherhale/ai-solutions-lab/pull/72) merged as `0a0ee7b`. Catalog marks STATUS-2 merged; registers DOC-ENG-AIDEV-1, FIN-4, and STATUS-3. |
| DOC-ENG-AIDEV-1 `ai-dev` branch documented in backlog | Done in pull request [#72](https://github.com/anotherhale/ai-solutions-lab/pull/72). `ENGINEERING_BACKLOG.md` integration-branch summary. Documentation only. |
| FIN-4 work-order filter by `invoice_id` | Done. Pull request [#73](https://github.com/anotherhale/ai-solutions-lab/pull/73) merged as `d54ff60`. Optional `invoice_id` on `GET /api/v1/work-orders`; read-only. |
| STATUS-3 integration-branch status refresh | Done. Pull request [#74](https://github.com/anotherhale/ai-solutions-lab/pull/74) merged as `f6469ea`. Documentation only. |
| COORD-CATALOG-4 coordinator catalog after FIN-4 | Done. Pull request [#76](https://github.com/anotherhale/ai-solutions-lab/pull/76) merged as `2517ce4`. Documentation only. |
| DOC-README-FIN-4 work-order `invoice_id` in service README | Done. Pull request [#77](https://github.com/anotherhale/ai-solutions-lab/pull/77) merged as `a0cc77c`. Documents optional `invoice_id` on `GET /api/v1/work-orders` in `services/wasatch-api/README.md`. |
| COORD-CATALOG-5 coordinator catalog after DOC-README-FIN-4 | Done. Pull request [#78](https://github.com/anotherhale/ai-solutions-lab/pull/78) merged as `c095cfe`. Catalog and PROJECT_STATUS reconciled after #77. Superseded stale [#75](https://github.com/anotherhale/ai-solutions-lab/pull/75) (conflicts; close without merging). |
| COORD-CATALOG-6 coordinator catalog after #78 | Done. Pull request [#79](https://github.com/anotherhale/ai-solutions-lab/pull/79) merged as `274703c`. Catalog marks COORD-CATALOG-5 and STATUS-5 merged; documents FIN-4 `invoice_id` filter in `API_CONVENTIONS.md`. |
| DOC-API-FIN-4 work-order `invoice_id` in API_CONVENTIONS | Done in pull request [#79](https://github.com/anotherhale/ai-solutions-lab/pull/79). Documentation only. |
| COORD-CATALOG-7 coordinator catalog after #79 | Done. Pull request [#80](https://github.com/anotherhale/ai-solutions-lab/pull/80) merged as `0d3d894`. Registers PORT-CASE-FIN-2. |
| STATUS-6 PROJECT_STATUS after DOC-API-FIN-4 | Done in pull request [#80](https://github.com/anotherhale/ai-solutions-lab/pull/80). Documentation only. |
| PORT-CASE-FIN-2 case study finance on `develop` | Done. Pull request [#84](https://github.com/anotherhale/ai-solutions-lab/pull/84) merged as `fb27969`. Finance read routes and FIN-4 work-order filter in the case study. Documentation only. |
| COORD-CATALOG-9 coordinator catalog after #84 | Done. Pull request [#85](https://github.com/anotherhale/ai-solutions-lab/pull/85) merged as `00ef109`. Registers COORD-ENTRY-SYNC-1 and DOC-DEBT-MIG-2. |
| STATUS-7 PROJECT_STATUS after PORT-CASE-FIN-2 | Done in pull request [#85](https://github.com/anotherhale/ai-solutions-lab/pull/85). Documentation only. |
| COORD-ENTRY-SYNC-1 catalog sync before coordinator tick | Done in pull request [#85](https://github.com/anotherhale/ai-solutions-lab/pull/85). |
| DOC-DEBT-MIG-2 downgrade debt through Alembic 0012 | Done. Pull request [#86](https://github.com/anotherhale/ai-solutions-lab/pull/86) merged as `62067a2`. Documentation only. |
| COORD-CATALOG-10 coordinator catalog after #86 | Done. Pull request [#87](https://github.com/anotherhale/ai-solutions-lab/pull/87) merged as `e8c2a22`. Marks DOC-DEBT-MIG-2 merged; registers DOC-DBMAP-2. |
| STATUS-8 PROJECT_STATUS after DOC-DEBT-MIG-2 | Done in pull request [#87](https://github.com/anotherhale/ai-solutions-lab/pull/87). Documentation only. |
| DOC-DBMAP-2 coordinator tables in DATABASE_MAPPING | Done. Pull request [#95](https://github.com/anotherhale/ai-solutions-lab/pull/95) merged as `e3e2e5e8`. Documents the `development_ops` schema and task lifecycle. Documentation only. |
| COORD-BACKLOG-PR-OPEN-1 catalog lifecycle statuses | Done. Pull request [#95](https://github.com/anotherhale/ai-solutions-lab/pull/95) merged as `e3e2e5e8`. One task lifecycle with monotonic catalog sync and a `merge_ready` status independent of auto-merge eligibility. |
| COORD-CATALOG-11 coordinator catalog after #95 | Done. Pull request [#96](https://github.com/anotherhale/ai-solutions-lab/pull/96) merged as `2b9f3e45`. Catalog and status reconciliation after #95. |
| STATUS-9 PROJECT_STATUS after DOC-DBMAP-2 | Done in pull request [#96](https://github.com/anotherhale/ai-solutions-lab/pull/96). Documentation only. |
| COORD-CATALOG-12 coordinator catalog after #96 | Done. Pull request [#97](https://github.com/anotherhale/ai-solutions-lab/pull/97) merged as `93c23c5`. Catalog marks #96 tasks merged. |
| STATUS-10 PROJECT_STATUS after #96 | Done in pull request [#97](https://github.com/anotherhale/ai-solutions-lab/pull/97). Documentation only. |
| COORD-CATALOG-13 coordinator catalog after #97 | In progress. Catalog marks #97 tasks merged. |
| STATUS-11 PROJECT_STATUS after #97 | In progress. Documentation only. |

Open pull requests targeting `develop`: COORD-CATALOG-13 / STATUS-11 follow-up opening on branch `cursor/coord-catalog-13-post-97`. Superseded develop pull requests [#88](https://github.com/anotherhale/ai-solutions-lab/pull/88), [#89](https://github.com/anotherhale/ai-solutions-lab/pull/89), [#91](https://github.com/anotherhale/ai-solutions-lab/pull/91), and [#82](https://github.com/anotherhale/ai-solutions-lab/pull/82) were closed without merge when [#95](https://github.com/anotherhale/ai-solutions-lab/pull/95) landed.

Open pull requests targeting `ai-dev` (do not block `develop` scheduling):

| Pull request | Backlog task | Notes |
|---|---|---|
| [#93](https://github.com/anotherhale/ai-solutions-lab/pull/93) | DOC-BRANCH-POLICY-1 | Branch roles and deliberate promotion flow (ADR 0016). |
| [#94](https://github.com/anotherhale/ai-solutions-lab/pull/94) | COORD-ENTRY-CATALOG-1, STATUS-AIDEV-1 | Consolidates #69 and #70 with one catalog entry per task; supersedes them. |
| [#92](https://github.com/anotherhale/ai-solutions-lab/pull/92) | COORD-HARDEN-1 | Hardened coordinator. Blocked: GitHub refuses auto-merge on a clean pull request. |

Autonomous laboratory work continues on `ai-dev` until those pull requests merge.

## Integration branches (laboratory)

| Branch | Role |
|---|---|
| `develop` | Wasatch API slice, finance read routes, `apps/wasatch-review`, coordinator catalog default |
| `ai-dev` | Child-agent orchestration, AI review gate, extended Alembic head through `0016` until promoted |

See [ENGINEERING_BACKLOG.md](ENGINEERING_BACKLOG.md) for backlog ordering and dependencies.

Finance documentation merged on `ai-dev` only (not yet on `develop`; application routes on `develop` are unchanged):

| Pull request | Backlog task | Merge on `ai-dev` | Notes |
|---|---|---|---|
| [#50](https://github.com/anotherhale/ai-solutions-lab/pull/50) | DOC-DEBT-MIG-1 | `2ba5877` | Downgrade coverage note through Alembic `0011`. Documentation only. |
| [#51](https://github.com/anotherhale/ai-solutions-lab/pull/51) | PORT-CASE-FIN-1 | `997d582` | Case study finance read slice. Documentation only. |
| [#54](https://github.com/anotherhale/ai-solutions-lab/pull/54) | DOC-API-FIN-1 | `4fd8680` | Payment read routes in `API_CONVENTIONS.md`. Documentation only. |

Open pull requests on `ai-dev` (do not block `develop` integration):

| Pull request | Backlog task | Notes |
|---|---|---|
| [#93](https://github.com/anotherhale/ai-solutions-lab/pull/93) | DOC-BRANCH-POLICY-1 | Branch roles and deliberate promotion flow (ADR 0016). |
| [#94](https://github.com/anotherhale/ai-solutions-lab/pull/94) | COORD-ENTRY-CATALOG-1, STATUS-AIDEV-1 | Consolidates #69 and #70 with one catalog entry per task. |

Seeded document counts: 30 documents, 31 document versions, and 18 extractions. `doc_0004` has two versions and current version `dv_0031`. Needs-review extractions are `dx_0003`, `dx_0009`, and `dx_0015`. Seeded governance counts: 10 approval requests, 11 decision-history rows, and 50 audit events. `msg_0016` (`pending_approval`, `requires_approval` true) references `apr_0001`. Audit rows are insert-only: revision `0003` installs a trigger that rejects `UPDATE` and `DELETE`. The customer-message decision, the extraction-review decision, and each follow-up transition insert one new audit row and do not update or delete audit events. A second seed skips existing audit rows. Seed copies fixture extraction status and does not accept a low-confidence or financial row.

## Not implemented

These items are absent. Later documents must not describe them as running:

- Any user interface besides `apps/wasatch-review`. That screen opens one synthetic inquiry for suggested-reply review and one synthetic extraction for extraction review. It does not send email, SMS, any other customer message, or any financial posting.
- A model call in tests or CI. Chat and embedding ports exist. The OpenAI adapter is installed and stays behind `AI_PROVIDER`. The default provider is a fake and does not call the network. No provider credential is committed.
- A trusted semantic model or document-packet bytes. Procedure page text is embedded with the fake port into `procedure_page_embeddings.embedding` (`vector(8)`). The vectors are deterministic and are not a trusted model. Document version bytes are not embedded. Unaccepted, `needs_review`, low-confidence, and financial extractions are not in that index. `AI_PROVIDER` defaults to `fake`. `openai` with the placeholder key `replace-me` fails before an OpenAI client is constructed. Tests do not call the network. There is no second vector database. WF-1 is the follow-up visit above. n8n, Redis, Kafka, and further dispatch assistance are not running. OPS-1 is the host trace in the current-work table. PORT-1 does not add a trusted model.
- Outbound message delivery. The approval decision, the suggested-reply draft, the extraction review, and the follow-up confirm or cancel are the writes that touch a customer message or a visit. None of them delivers email or SMS, marks a message `sent`, posts a payment, or changes an invoice. The follow-up command also does not assign a technician or create an appointment.
- An external identity provider, purchased identity service, password system, or production credential. The local laboratory authenticator is a development-only header simulation. Production configuration fails startup instead of activating that header.
- A trace collector, metrics export, and log export. Compose does not run a collector. Span export stays off unless `OTEL_EXPORTER_OTLP_ENDPOINT` is set.
- Redis, n8n, Azure, and Terraform resources (`infrastructure/terraform/` has no workspace, no module, and no credential)
- Financial posting, price changes, or write routes that mutate invoice or payment totals. Revisions `0008`–`0011` persist reference `invoices`, `invoice_lines`, and `payments` for read-only laboratory routes. The extraction review and other commands do not post a payment or change an invoice total.
- File bytes for documents (`data/documents/procedures/` holds procedure pages for retrieval; version rows still point at synthetic `storage_path` values only)

ADR status in `docs/adr/README.md`: 0001–0007 are Accepted. ADR 0007 (Starlette security remediation) is Accepted in this change. ADR 0001 was accepted in pull request [#5](https://github.com/anotherhale/ai-solutions-lab/pull/5) (`c18ad80`): `services/wasatch-api` is the host, one process, and the customer and work-order modules are the first packages. ADR 0004 is Accepted: chat and embedding ports are in the application layer, and the OpenAI client stays in the infrastructure adapter.

## Phase 2.1.1 residuals

These are gaps inside an implemented slice. They are not a reason to recreate the database, models, or fixtures.

- HTTP contract coverage is `tests/api/test_openapi_contract.py` plus `tests/api/openapi_contract_catalog.py` for the full slice path/method catalog, write routes, decision enums, and runtime error envelopes. `tests/unit/test_contract_alignment.py` still aligns status enums with JSON Schema. Response bodies are not validated against the full JSON Schemas.
- Tests run Alembic `upgrade` to `head`. Revisions `0001`–`0011` each have an integration upgrade/downgrade test (plus `0009` development activity log); see `services/wasatch-api/tests/integration/README.md`.
- `tests/conftest.py` skips the suite when PostgreSQL cannot be reached. A local run without the database can skip rather than fail. CI does not rely on that skip: pull request [#11](https://github.com/anotherhale/ai-solutions-lab/pull/11) (`d1178e8`) sets `WASATCH_REQUIRE_DATABASE=1`, and `scripts/check_wasatch_api_pytest.py` fails the job when the database tests were skipped. The skip predicate was not removed.
- `/api/v1` reads require an active synthetic employee presented in `X-Laboratory-Actor`. That header is a local laboratory adapter. It runs only when `APP_ENV` is `local`, `development`, or `test`. `APP_ENV=production` and `APP_ENV=prod` fail startup. Health probes stay open. An active employee may `POST /api/v1/support-tickets/{ticket_id}/draft-replies`. An approver may `POST /api/v1/approval-requests/{approval_id}/decisions` for a pending customer message, and may `POST /api/v1/document-extractions/{extraction_id}/decisions` for an extraction that is awaiting review. A dispatcher (`role_0004`) may `POST /api/v1/approval-requests/{approval_id}/follow-up-visits` to open, confirm, or cancel a follow-up visit. Neither customer-message command marks the message `sent`. The extraction decision does not post a payment or change an invoice. The follow-up command does not either, and it does not assign a technician. Every other authenticated write returns 403, and an anonymous write returns 401. The pytest skip predicate in `tests/conftest.py` is unchanged. That file now clears `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` before importing the app, so the suite does not export spans.
- `APP_LOG_LEVEL` configures structured logs of actor, action, subject, and outcome. Message bodies and secrets are omitted. Spans are recorded in process. They are exported only when `OTEL_EXPORTER_OTLP_ENDPOINT` is set. Request headers are not copied onto spans.
- `work_orders.invoice_id` references `invoices.business_id` (revision `0008`). Document `invoice_id` stays a string. `employees.role_id` references `roles`. `employees.team_id` references `teams`. `work_orders.support_ticket_id` references `support_tickets`. `messages.approval_request_id` references `approval_requests`.

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

## Verification for document persistence

Run from `services/wasatch-api` with `services/wasatch-api/.venv` against the Compose PostgreSQL service (`pgvector/pgvector:pg16`). The parent is `develop` at `13826ed`. The suite created or reused `wasatch_test`. `tests/conftest.py`, `.github/workflows/validate.yml`, and `scripts/check_wasatch_api_pytest.py` were not edited. `WASATCH_REQUIRE_DATABASE=1` was set. This run did not skip. The workforce migration test upgrades to revision `0004` for its schema assertions, then the existing `finally` still upgrades to `head`.

| Command | Result | Exit |
|---|---|---|
| `WASATCH_REQUIRE_DATABASE=1 .venv/bin/pytest --tb=line -rfEs` | 150 passed, 0 failed, 0 skipped, 1 warning in 8.76s | 0 |

The warning is the existing Starlette deprecation of `anyio.abc.BlockingPortal` in `starlette/testclient.py`. The run upgraded and downgraded revision `0005` on the synthetic database. It did not start the API container, did not call OpenAI, and did not observe GitHub Actions.

From the repository root, same session:

| Command | Result | Exit |
|---|---|---|
| `services/wasatch-api/.venv/bin/ruff format --check .` | 180 files already formatted | 0 |
| `services/wasatch-api/.venv/bin/ruff check .` | All checks passed | 0 |
| `python3 scripts/validate_repo.py` | `Repository conventions validated.` | 0 |
| `python3 scripts/validate_wasatch_domain.py` | `Wasatch domain fixtures validated.` Counts include document 30, document_version 31, document_extraction 18. | 0 |

## Verification for extraction review

Run from `services/wasatch-api` with `services/wasatch-api/.venv` against the Compose PostgreSQL service (`pgvector/pgvector:pg16`). The parent is `develop` at `78877e6`. The suite created or reused `wasatch_test`. `tests/conftest.py`, `.github/workflows/validate.yml`, and `scripts/check_wasatch_api_pytest.py` were not edited. `WASATCH_REQUIRE_DATABASE=1` was set. This run did not skip. No Alembic revision was added.

| Command | Result | Exit |
|---|---|---|
| `WASATCH_REQUIRE_DATABASE=1 .venv/bin/pytest --tb=line -rfEs` | 164 passed, 0 failed, 0 skipped, 1 warning in 9.83s | 0 |

The warning is the existing Starlette deprecation of `anyio.abc.BlockingPortal` in `starlette/testclient.py`. The run did not call OpenAI and did not observe GitHub Actions. The virtualenv was missing the already declared `openai` package; `pip install -e '.[dev]'` installed it before this run.

From the repository root, same session:

| Command | Result | Exit |
|---|---|---|
| `services/wasatch-api/.venv/bin/ruff format --check .` | 184 files already formatted | 0 |
| `services/wasatch-api/.venv/bin/ruff check .` | All checks passed | 0 |
| `python3 scripts/validate_repo.py` | `Repository conventions validated.` | 0 |
| `python3 scripts/validate_wasatch_domain.py` | `Wasatch domain fixtures validated.` Counts include document 30, document_version 31, document_extraction 18. | 0 |

## Verification for procedure embeddings

Run from `services/wasatch-api` with `services/wasatch-api/.venv` against the Compose PostgreSQL service (`pgvector/pgvector:pg16`). The parent is `develop` at `6e92af9`. The suite created or reused `wasatch_test`. `tests/conftest.py`, `.github/workflows/validate.yml`, and `scripts/check_wasatch_api_pytest.py` were not edited. `WASATCH_REQUIRE_DATABASE=1` was set. `AI_PROVIDER` and `OPENAI_API_KEY` were unset. This run did not skip. The first attempt failed three tests because the virtualenv was missing the already declared `openai` package. `pip install -e '.[dev]'` installed it. The run below is after that install.

| Command | Result | Exit |
|---|---|---|
| `WASATCH_REQUIRE_DATABASE=1 .venv/bin/pytest --tb=short -rfEs` | 173 passed, 0 failed, 0 skipped, 1 warning in 10.00s | 0 |

The warning is the existing Starlette deprecation of `anyio.abc.BlockingPortal` in `starlette/testclient.py`. The run upgraded and downgraded revision `0006`. Filling the index wrote 3 rows in `procedure_page_embeddings` (`proc_0001`, `proc_0002`, `proc_0003`), column `embedding` `vector(8)`, model `fake-embedding`. The test then deleted those rows. Document versions stayed 31 and document extractions stayed 18. No extraction id was inserted. The run did not call OpenAI and did not observe GitHub Actions.

From the repository root, same session:

| Command | Result | Exit |
|---|---|---|
| `services/wasatch-api/.venv/bin/ruff format --check .` | 192 files already formatted | 0 |
| `services/wasatch-api/.venv/bin/ruff check .` | All checks passed | 0 |
| `python3 scripts/validate_repo.py` | `Repository conventions validated.` | 0 |
| `python3 scripts/validate_wasatch_domain.py` | `Wasatch domain fixtures validated.` Counts include document 30, document_version 31, document_extraction 18. | 0 |

## Verification for the follow-up visit

Run from `services/wasatch-api` with `services/wasatch-api/.venv` against the Compose PostgreSQL service (`pgvector/pgvector:pg16`). The parent is `develop` at `068a185`. The suite created or reused `wasatch_test`. `tests/conftest.py`, `.github/workflows/validate.yml`, and `scripts/check_wasatch_api_pytest.py` were not edited. `WASATCH_REQUIRE_DATABASE=1` was set. `AI_PROVIDER` and `OPENAI_API_KEY` were unset. This run did not skip. The first attempt failed three tests because the virtualenv was missing the already declared `openai` package, and four assertions still expected Alembic head `0006`. `pip install -e '.[dev]'` installed `openai`. The documents migration assertion now expects head `0007` and that `follow_up_visits` exists. The run below is after that install and assertion update.

| Command | Result | Exit |
|---|---|---|
| `WASATCH_REQUIRE_DATABASE=1 .venv/bin/pytest --tb=line -rfEs` | 184 passed, 0 failed, 0 skipped, 1 warning in 11.49s | 0 |

The warning is the existing Starlette deprecation of `anyio.abc.BlockingPortal` in `starlette/testclient.py`. The run did not call OpenAI and did not observe GitHub Actions. Revision `0007` creates `follow_up_visits` and adds no vector column. The scenario leaves no follow-up row before the customer-message approval, and the approval alone does not assign a technician or create an appointment. After that approval, the dispatcher opens `fuv_0001` as `unscheduled` and then confirms it. `msg_0016` stays `pending_approval`. Invoice and payment fixture bytes are unchanged, and `information_schema` has no `invoices`, `invoice_lines`, or `payments` table. A separate case cancels instead. `emp_0001` and `emp_0006` receive 403. An anonymous caller receives 401. Audit stays insert-only.

From the repository root, same session:

| Command | Result | Exit |
|---|---|---|
| `services/wasatch-api/.venv/bin/ruff format --check .` | 206 files already formatted | 0 |
| `services/wasatch-api/.venv/bin/ruff check .` | All checks passed | 0 |
| `python3 scripts/validate_repo.py` | `Repository conventions validated.` | 0 |
| `python3 scripts/validate_wasatch_domain.py` | `Wasatch domain fixtures validated.` Counts include document 30, document_version 31, document_extraction 18. | 0 |

## Verification for host traces

Run from `services/wasatch-api` with `services/wasatch-api/.venv` against the Compose PostgreSQL service (`pgvector/pgvector:pg16`). The parent is `develop` at `1b22eac`. The suite created or reused `wasatch_test`. `.github/workflows/validate.yml` and `scripts/check_wasatch_api_pytest.py` were not edited. `tests/conftest.py` still skips when PostgreSQL is down and CI still fails that skip. The file now clears `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` before importing the app. `WASATCH_REQUIRE_DATABASE=1` was set. `AI_PROVIDER` and `OPENAI_API_KEY` were unset. `OTEL_EXPORTER_OTLP_ENDPOINT` was unset. This run did not skip. The first attempt failed three tests because the virtualenv was missing the already declared `openai` package (`ModuleNotFoundError`). `pip install -e '.[dev]'` installed `openai` 3.45.0 and the pinned OpenTelemetry packages. The run below is after that install.

| Command | Result | Exit |
|---|---|---|
| `WASATCH_REQUIRE_DATABASE=1 .venv/bin/pytest --tb=line -rfEs` | 195 passed locally after revision `0008` and OpenAPI contract tests (CI gate may differ until runs complete) | 0 |

The warning is the existing Starlette deprecation of `anyio.abc.BlockingPortal` in `starlette/testclient.py`. The run did not call OpenAI, did not open a collector socket, and did not observe GitHub Actions. `terraform plan` and `terraform apply` were not run. The new tests start the app with the exporter unset and `GET /health` still returns `status` `ok` and `service` `wasatch-api`.

From the repository root, same session:

| Command | Result | Exit |
|---|---|---|
| `services/wasatch-api/.venv/bin/ruff format --check .` | 211 files already formatted | 0 |
| `services/wasatch-api/.venv/bin/ruff check .` | All checks passed | 0 |
| `python3 scripts/validate_repo.py` | `Repository conventions validated.` | 0 |
| `python3 scripts/validate_wasatch_domain.py` | `Wasatch domain fixtures validated.` Counts include document 30, document_version 31, document_extraction 18. | 0 |

## Verification for PORT-1

Documentation only. The parent is `develop` at `1be4181`. Application tests were not run. `.github/workflows/validate.yml`, `scripts/check_wasatch_api_pytest.py`, and `services/wasatch-api/tests/conftest.py` were not edited. The API suite was not started. GitHub Actions was not observed. No provider key was set. This change does not set `OTEL_EXPORTER_OTLP_ENDPOINT`.

From the repository root, after the case study and these status edits were on disk:

| Command | Result | Exit |
|---|---|---|
| `python3 --version` | Python 3.12.3 | 0 |
| `ruff --version` | ruff 0.17.3 | 0 |
| `ruff format --check .` | 212 files already formatted | 0 |
| `ruff check .` | All checks passed | 0 |
| `python3 scripts/validate_repo.py` | `Repository conventions validated.` | 0 |
| `python3 scripts/validate_wasatch_domain.py` | `Wasatch domain fixtures validated.` Counts include customer 15, employee 15, document 30, document_version 31, document_extraction 18. | 0 |

The formatted-file count is 212. The host-trace session recorded 211. The new file is `docs/case-studies/wasatch-laboratory-slice.md`. Pytest was not re-run. The latest recorded API result remains "Verification for host traces" (`188 passed, 0 failed, 0 skipped`).

## GitHub Actions on `develop` after pull requests #26 and #27

Checked 2026-11-04 (Mountain Time). Integration branch tip: `13836b8` (merge of pull request #27).

| Push commit | Pull request | Workflow run | Status when observed |
|---|---|---|---|
| `e25fb91` | [#26](https://github.com/anotherhale/ai-solutions-lab/pull/26) work order invoice FK | [41864434843](https://github.com/anotherhale/ai-solutions-lab/actions/runs/41864434843) | `queued` — all five jobs waiting for runners |
| `13836b8` | [#27](https://github.com/anotherhale/ai-solutions-lab/pull/27) pip-audit in CI | [41864750539](https://github.com/anotherhale/ai-solutions-lab/actions/runs/41864750539) | `queued` — same |
| `00b0fd6` | earlier merge (#24 HTTP contract) | [41861264021](https://github.com/anotherhale/ai-solutions-lab/actions/runs/41861264021) | `completed` / **success** |

The cloud-agent token could not re-run workflows (`Resource not accessible by integration`) or read branch protection (HTTP 403). `GET /repos/.../rulesets` returned `[]` with that token, so required status checks on `develop` could not be verified from CI; see `docs/operations/github-branch-protection.md` for administrator steps.

Merges while checks were queued are consistent with **no enforced required checks** plus merge permission, not with green CI. Agents must wait for green **Repository Validation** before enabling squash auto-merge.

## Verification for governance, migration matrix, and ADR 0007

Run from repository root and `services/wasatch-api` with Compose PostgreSQL (`pgvector/pgvector:pg16`). Parent branch before this change: `develop` at `13836b8`.

| Command | Result | Exit |
|---|---|---|
| `WASATCH_REQUIRE_DATABASE=1 .venv/bin/pytest tests/integration/test_invoice_migration.py --tb=short` | 2 passed | 0 |
| `WASATCH_REQUIRE_DATABASE=1 .venv/bin/pytest --tb=line -rfEs` | 195 passed, 0 skipped | 0 |
| `scripts/audit_wasatch_dependencies.sh` | No known vulnerabilities found, 5 ignored (Starlette PYSEC IDs per ADR 0007 while it was Proposed) | 0 |
| `ruff format --check .` | All files formatted | 0 |
| `ruff check .` | All checks passed | 0 |
| `python3 scripts/validate_repo.py` | Repository conventions validated | 0 |
| `python3 scripts/validate_wasatch_domain.py` | Wasatch domain fixtures validated | 0 |

## Verification for SEC-1

Run from `services/wasatch-api` with `services/wasatch-api/.venv` against Compose PostgreSQL (`pgvector/pgvector:pg16`). Parent is `develop` at `8c950ce`. `WASATCH_REQUIRE_DATABASE=1` was set. `AI_PROVIDER` and `OPENAI_API_KEY` were unset. This run did not skip. Installed stack: FastAPI 0.162.0, Starlette 1.10.0, anyio 4.16.0. Pytest printed no warning summary.

| Command | Result | Exit |
|---|---|---|
| `WASATCH_REQUIRE_DATABASE=1 .venv/bin/pytest --tb=line -rfEs` | 198 passed, 0 failed, 0 skipped in 16.32s | 0 |
| `scripts/audit_wasatch_dependencies.sh` | `No known vulnerabilities found`. The editable distribution was skipped. No `--ignore-vuln` entries. | 0 |
| `ruff format --check .` | 222 files already formatted | 0 |
| `ruff check .` | All checks passed | 0 |
| `python3 scripts/validate_repo.py` | Repository conventions validated | 0 |
| `python3 scripts/validate_wasatch_domain.py` | Wasatch domain fixtures validated | 0 |

From `apps/wasatch-review` with Node.js 22.23.4:

| Command | Result | Exit |
|---|---|---|
| `npm test` | Vitest 5.1.0. 14 passed across 3 files | 0 |
| `npm run typecheck` | `tsc --noEmit` | 0 |
| `npm run build` | Vite production build succeeded | 0 |

Compose image `ai-solutions-lab-api` built from `services/wasatch-api/Dockerfile` and started with `docker compose up -d`. The container reported FastAPI 0.162.0 and Starlette 1.10.0. `GET /health` returned `status` `ok` and `service` `wasatch-api`. `GET /health/ready` returned `status` `ready` and `database` `up`. OpenAPI listed 29 paths, including document extractions. `scripts/smoke_compose.sh` was not executed as a single script because its cleanup runs `docker compose down`. The health, readiness, and OpenAPI checks from that script were run, and the stack was left up.

From `tests/e2e`, with the API virtualenv on `PATH` so `python3` can import Alembic (the CI job installs that package into the runner interpreter first):

| Command | Result | Exit |
|---|---|---|
| `npm test` | Playwright. 2 passed (reply approval without a send control, extraction accept without posting money) | 0 |

Uvicorn logged `Application startup complete` on port 8010. The run did not call OpenAI. GitHub Actions was not observed. No customer message was sent and no payment was posted.

## Verification for STATUS-2

Documentation only. Parent branch is `develop` at `bcf404b`. This run refreshed the current-work table for COORD-PR-SLOT-1, DOC-README-FIN-1, COORD-CATALOG-2, and finance documentation merged on `ai-dev` ([#50](https://github.com/anotherhale/ai-solutions-lab/pull/50), [#51](https://github.com/anotherhale/ai-solutions-lab/pull/51), [#54](https://github.com/anotherhale/ai-solutions-lab/pull/54)). It does not claim those documentation edits are on `develop`. Application code, migrations, and CI workflow files were not edited. GitHub Actions was not observed.

From the repository root, same session:

| Command | Result | Exit |
|---|---|---|
| `python3 scripts/validate_repo.py` | Repository conventions validated | 0 |
| `ruff format --check PROJECT_STATUS.md ENGINEERING_BACKLOG.md data/coordinator/backlog.yaml` | Files already formatted | 0 |

## Verification for STATUS-3

Documentation only. Parent branch is `develop` at `0a0ee7b` after pull request [#72](https://github.com/anotherhale/ai-solutions-lab/pull/72) merged DOC-ENG-AIDEV-1. This change updates the baseline, integration-branch summary, open pull request [#73](https://github.com/anotherhale/ai-solutions-lab/pull/73), and `ai-dev` divergence counts. No application code, migrations, or CI workflow files were edited.

From the repository root, coordinator run 2026-11-13:

| Command | Result | Exit |
|---|---|---|
| `python3 scripts/validate_repo.py` | Repository conventions validated | 0 |

## Verification for STATUS-4

Documentation only. Parent branch is `develop` at `f6469ea` after pull requests [#73](https://github.com/anotherhale/ai-solutions-lab/pull/73) (FIN-4) and [#74](https://github.com/anotherhale/ai-solutions-lab/pull/74) (STATUS-3). This change updates the baseline through those merges, records FIN-4 and STATUS-3 in the current-work table, lists open `ai-dev` pull requests #69 and #70, and reconciles `data/coordinator/backlog.yaml`. No application code, migrations, or CI workflow files were edited.

From the repository root, coordinator run 2026-11-13 after PR #74 merge:

| Command | Result | Exit |
|---|---|---|
| `python3 scripts/validate_repo.py` | Repository conventions validated | 0 |
| `WASATCH_REQUIRE_DATABASE=1 services/wasatch-api/.venv/bin/pytest services/wasatch-api/tests/api/test_health_and_resources.py -q` | API resource tests including `invoice_id` work-order filter | 0 |
