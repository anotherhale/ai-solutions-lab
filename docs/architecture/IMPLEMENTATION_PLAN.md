# Implementation Plan

Authoritative sequencing for AI Solutions Lab. Wasatch Business Systems is a fictional commercial HVAC company. Every customer, employee, and financial figure in this repository is synthetic.

This plan follows [../ARCHITECTURE.md](../ARCHITECTURE.md), [../ROADMAP.md](../ROADMAP.md), and the ADRs. It does not replace them. A change to deployment shape, module boundaries, or the stack is an ADR first.

The verified snapshot is [../../PROJECT_STATUS.md](../../PROJECT_STATUS.md). The ordered task list is [../../ENGINEERING_BACKLOG.md](../../ENGINEERING_BACKLOG.md).

## Mission

Build a production-quality laboratory that can be reused for small and midsize businesses. The first simulated customer is Wasatch Business Systems. Shared platform concerns are data contracts, persistence, security, integrations, and observability. Capabilities arrive in this order:

1. Customer service AI
2. Intelligent document processing
3. Workflow automation
4. Internal knowledge
5. Sales intelligence
6. Operations reporting

The laboratory stays portable: business rules live in the application, and vendor systems sit behind adapters.

## Decisions in force

| Decision | Source | Status | Effect on implementation |
|---|---|---|---|
| Modular monolith, hexagonal, explicit modules | ADR 0001, `AGENTS.md` | Proposed in the ADR. The first host is already implemented. | One FastAPI process. Customer and work-order packages are the pattern for later modules. |
| Python 3.12 and FastAPI | ADR 0002 | Accepted | `services/wasatch-api` is the host. `apps/wasatch-review` is the React and TypeScript review screen. |
| PostgreSQL and pgvector | ADR 0003 | Accepted | System of record and embeddings share one database. Revision `0006` stores procedure-page vectors in `procedure_page_embeddings.embedding` (`vector(8)`, the fake port's width). No second vector database. |
| OpenAI behind a port | ADR 0004 | Proposed | No SDK until a use case needs it. Domain code never imports the SDK. CI must not need an API key. |
| Docker Compose for local dependencies | ADR 0005 | Accepted | `compose.yaml` is the local topology. Redis and n8n stay out until a feature consumes them. |
| Human approval for consequential operations | `docs/SECURITY.md`, domain model | In force | Draft and recommend are allowed. Sending customer commitments, changing money, and changing field work require an approval record. |
| API-first contracts | `DATA_CONTRACTS.md` | In force | `data/schemas/v1/` is the external contract. SQLAlchemy and Pydantic follow it. |
| No Nx, Kubernetes, or microservices | ADR 0001, architecture | In force | Revisit only with an ADR that names a requirement the monolith cannot meet. |

## Platform rules for every phase

- Keep domain, application, infrastructure, and presentation separate.
- Put business rules in domain or application code.
- Name modules with Wasatch language when they model that business.
- Add a dependency only when the current task needs it, with a stated purpose, the thing it replaces, and the risk.
- Synthetic data only. No live customer system. No production deployment. Phase 5 does not define an Azure environment. No workspace exists.
- No purchased services, cloud credentials, or production API keys in the repository or in CI.
- Tests use the existing fixtures. Quality-issue files stay out of the valid database.
- Quality bar for a behavior change: unit tests, integration tests, API tests, contract checks against the JSON Schemas, migration upgrade (and downgrade when it is safe), security review when access or tools expand, dependency review when dependencies change, doc updates, and a green CI run. Existing checks stay as strict as they are.

## Phase 1 — foundation

**State: complete** on `881cfc0`.

Documentation, ADRs, repository conventions, the synthetic domain, JSON Schemas, valid and quality-issue fixtures, and validators are in the tree. Exit criterion from the roadmap: a new contributor can explain purpose, architecture, and working agreements from the repository. That criterion is met, with the documentation drift listed in [../../PROJECT_STATUS.md](../../PROJECT_STATUS.md).

## Phase 2.1.1 — read-only operational foundation

**State: complete.** The next implementation does not repeat this phase.

The phase means all of the following, and each one is in the repository:

- PostgreSQL with pgvector
- SQLAlchemy 2 models
- Alembic migrations
- Synthetic fixture loading from the existing valid fixtures
- FastAPI foundation
- Read-only customer, service-location, and work-order endpoints
- Automated tests
- Docker Compose
- CI
- Developer documentation

Evidence, residuals, and the commands run on 2026-11-04 are in [../../PROJECT_STATUS.md](../../PROJECT_STATUS.md). Residuals (no auth on reads, no logs, thin contract tests, untested downgrade, string foreign keys) are backlog debt. They do not reopen Phase 2.1.1.

Mapped scope is the customer kernel plus the field slice required by those endpoints: contacts, employees, equipment, work-order tasks, appointments, and assignment links. Finance, documents, customer service, and governance remain fixtures and schemas only.

## Phase 2.2 — customer-service vertical slice

**State: in progress.** CS-1 (`047702e`), CS-2 (`7760106`), and CS-3 (`5b2ffc4`) are on `develop`. The laboratory actor header is a local synthetic development simulation (`ac26535`), and a production configuration fails startup. CI fails when the Wasatch API database tests are skipped (`d1178e8`). CS-5 retrieval is on `develop` (`a03fea9`, pull request [#12](https://github.com/anotherhale/ai-solutions-lab/pull/12)). CS-4 records the human approve or reject for a pending customer message and does not send it (`0785ab9`, pull request [#13](https://github.com/anotherhale/ai-solutions-lab/pull/13)). CS-6 drafts a suggested reply through the model port (`781bcc0`, pull request [#14](https://github.com/anotherhale/ai-solutions-lab/pull/14)). CS-7 is the React review surface for that decision (`13826ed`, pull request [#15](https://github.com/anotherhale/ai-solutions-lab/pull/15)).

Roadmap exit: a dispatcher or customer-service agent can review an inbound inquiry, inspect a suggested reply, and approve or reject it, using synthetic data.

### Boundaries

- Inquiries, messages, interactions, approvals, and audit events already have JSON Schemas and valid fixtures. Persistence reuses those files.
- Suggested replies are created by the draft use case on an existing ticket. It does not rewrite historical fixture messages.
- One pending outbound example is already in the fixtures: `msg_0016` on `tkt_0007`, status `pending_approval`, approval `apr_0001`. Decision tests should use that row.
- Customer history text exists on tickets, messages, interactions, and work orders. A small synthetic procedure corpus lives under `data/documents/procedures/` and is labeled synthetic. It does not replace `data/fixtures/valid/`. Document version `storage_path` values such as `synthetic/documents/doc_0001/v1.bin` are still not files in the repository. Retrieval reads persisted history with a relational query and matches procedure pages from that corpus. Revision `0006` stores embeddings of the procedure text. Those vectors come from the fake port and are not a trusted model.
- The slice stops at approve or reject. Delivery to the customer is a later consequential action and needs its own approval execution step, which is not part of this exit.
- OpenAI is reached only through a port. Tests use a fake. No key is committed.

### Sequence

Tasks and dependencies are specified in [../../ENGINEERING_BACKLOG.md](../../ENGINEERING_BACKLOG.md). The order is:

1. **CS-1.** Read tickets, messages, and interactions. Link work orders to tickets with a foreign key.
2. **CS-2.** Read approvals and audit events. Audit rows stay insert-only.
3. **CS-3.** Persist roles so `is_approver` is real, and require an authenticated synthetic employee before any write. Done in `5b2ffc4`. The header adapter is local synthetic development only and is not a production authenticator.
4. **CS-4.** Human approve or reject of `send_customer_message`, with an audit event, without marking the message sent. Done in `0785ab9`.
5. **CS-5.** Retrieval port over persisted history plus a new synthetic procedure corpus. Done in `a03fea9`. Procedure-page embeddings are revision `0006` (EMB-1). Customer history stays relational.
6. **CS-6.** Draft a suggested reply through the AI port and open an approval request when the text would commit the company. Done in `781bcc0`.
7. **CS-7.** React review surface under `apps/` for that approve and reject flow. Done in `13826ed`.

CS-5 landed beside CS-4 after CS-1. CS-6 and CS-7 are on `develop`.

### Module shape

Follow the existing customer and work-order packages:

```text
services/wasatch-api/src/wasatch_api/
├── customer_service/
│   ├── domain/
│   ├── application/
│   └── infrastructure/
├── governance/
│   ├── domain/
│   ├── application/
│   └── infrastructure/
└── shared/database/models.py    # one metadata graph for foreign keys
```

Application services own the approval decision and the draft-reply use case. Routes stay thin. Prompts, model names, and the provider client stay in the AI adapter.

Structured logs use `APP_LOG_LEVEL`. Each access record has the actor, action, subject identifier, and outcome. Message bodies, contact details, and secrets stay out of the log. Span export is Phase 5 and stays off unless `OTEL_EXPORTER_OTLP_ENDPOINT` is set.

## Phase 3 — intelligent document processing

**State: procedure-page embeddings are stored. WF-1 is the follow-up visit in Phase 4. The case study is PORT-1 ([../case-studies/wasatch-laboratory-slice.md](../case-studies/wasatch-laboratory-slice.md)).** Depends on Phase 2.2. CS-7 is on `develop` (`13826ed`). Fixture persistence is on `develop` (`78877e6`, pull request [#16](https://github.com/anotherhale/ai-solutions-lab/pull/16)). Human review of extractions is on `develop` (`6e92af9`, pull request [#17](https://github.com/anotherhale/ai-solutions-lab/pull/17)).

Schemas and fixtures for documents, versions, and extractions already exist (30 documents, 31 versions, 18 extractions). Alembic `0005` persists those fixtures. Read routes serve them. `POST /api/v1/document-extractions/{extraction_id}/decisions` lets an approver accept or reject an extraction that is awaiting review. Confidence below 0.8, a missing score, `needs_review`, an invoice or money field, or a document linked to an invoice stays untrusted until that decision. A read, a seed, and a background job do not accept those rows. The decision records status, reviewer, `reviewed_at`, optional `review_notes`, and an audit event. It does not post a payment, change an invoice total, or mark an invoice posted. There are no bytes to ingest. `storage_path` stays a string. Alembic `0006` adds `procedure_page_embeddings.embedding` (`vector(8)`). An application service fills it by calling `EmbeddingPort`. The laboratory default is the fake port: 8-dimensional and deterministic. It is not a trusted semantic model. Only synthetic procedure page text is embedded. Document version bytes are not embedded. Unaccepted, `needs_review`, low-confidence, and financial extractions are not written into that index. Accepting an extraction does not post a payment, change an invoice, or insert the extraction into the index. `AI_PROVIDER` stays `fake`. WF-1 is the follow-up visit below. The case study is PORT-1 ([../case-studies/wasatch-laboratory-slice.md](../case-studies/wasatch-laboratory-slice.md)).

## Phase 4 — workflow automation

**State: WF-1 is this slice. The case study is PORT-1 ([../case-studies/wasatch-laboratory-slice.md](../case-studies/wasatch-laboratory-slice.md)).** Depends on the approval and audit path from CS-4. This workflow does not use documents.

Canonical rules stay in the monolith. The command is `POST /api/v1/approval-requests/{approval_id}/follow-up-visits`.

Two human steps:

1. An approver approves a pending `send_customer_message`. The decision leaves the message unsent. It does not open the visit and does not dispatch a technician.
2. A dispatcher (`role_0004`, including `emp_0004`) confirms or cancels the visit. The visit can be opened only from that approved request. It stays `unscheduled` until the dispatcher confirms or cancels it.

Each transition inserts an audit event. Audit storage stays insert-only. Confirming or canceling does not post a payment, change an invoice total, mark an invoice posted, send a message, assign a technician, or create an appointment. Alembic `0007` stores `follow_up_visits`. It does not add a vector column and does not embed extractions.

n8n remains an edge adapter for intake or notification once a workflow needs it. Redis is added only for cache or short-lived coordination that a use case actually performs. This slice adds neither, and it adds no Kafka, queue, or new service. No React screen was added. The review screen has no send control. Knowledge search beyond the Phase 2.2 procedure corpus, sales qualification, and further dispatch assistance are not started. The case study is PORT-1 ([../case-studies/wasatch-laboratory-slice.md](../case-studies/wasatch-laboratory-slice.md)).

## Phase 5 — production engineering and cloud definition

**State: OPS-1 is this bounded slice. The case study is PORT-1 ([../case-studies/wasatch-laboratory-slice.md](../case-studies/wasatch-laboratory-slice.md)).** Depends on a running module worth operating. The host qualifies. No workspace exists, so this slice does not define a cloud environment.

The Wasatch API records OpenTelemetry spans. Export uses OTLP over HTTP only when `OTEL_EXPORTER_OTLP_ENDPOINT` is a non-empty URL. An unset or blank value does not construct an exporter, does not open a socket, and does not require a collector. Domain code does not import the SDK. `wasatch_api.observability` is called from `create_app`. Request headers are not copied onto spans. Metrics export and log export are not wired. Structured logs stay on `APP_LOG_LEVEL`.

Compose and GitHub Actions do not gain a collector, Redis, n8n, or a cloud account. GitHub Actions stays credential-free.

`infrastructure/terraform/` stays empty of modules, backends, subscription ids, tenant ids, and credentials. Do not run `terraform plan` or `terraform apply` there. Backup expectations and secret-management notes are in [../operations/](../operations/). Local secrets stay in an uncommitted `.env`. Managed secrets apply only after a cloud deployment exists. That deployment does not exist. These notes, Compose, and the laboratory host are not an Azure deployment and not a production deployment.

This phase does not authorize live HVAC data. An Azure deployment path is not defined.

## Phase 6 — consulting portfolio

**State: PORT-1 is this case study.** Depends on the finished slice through OPS-1 (`1be4181`). The study is [../case-studies/wasatch-laboratory-slice.md](../case-studies/wasatch-laboratory-slice.md).

It says what was simulated, which measurements are already in [../../PROJECT_STATUS.md](../../PROJECT_STATUS.md), and what has not been deployed. It does not add a running system. Reusable discovery packs and a separate portability catalog are not additional files. An Azure deployment is still not defined.

## Architectural conflicts to close in documentation

These are wording drift, not competing designs:

| Location | Drift | Resolution |
|---|---|---|
| `docs/architecture/README.md` | Said no runtime modules exist | Closed by DOC-1. The host is `services/wasatch-api`. |
| `docs/DEVELOPMENT_WORKFLOW.md` | Said open pull requests against `main` | Closed by DOC-1. Integration is `develop`. |
| ADR 0001 | Was Proposed after the host landed | Closed by ADR-1 (`c18ad80`). Status is Accepted. |
| `.github/workflows/validate.yml` | Push trigger listed `main` only | Closed by CI-1 (`ecd3015`). Pushes to `develop` run the workflow. |

No ADR is superseded by this plan.
