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
| Python 3.12 and FastAPI | ADR 0002 | Accepted | `services/wasatch-api` is the host. React and TypeScript wait for a user interface. |
| PostgreSQL and pgvector | ADR 0003 | Accepted | System of record and future embeddings share one database. The extension is installed. Embedding columns are still deferred. |
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
- Synthetic data only. No live customer system. No production deployment in the phases below except the later non-production Azure definition in Phase 5, which is still not a customer production environment.
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

**State: in progress.** CS-1 (`047702e`) and CS-2 (`7760106`) are on `develop`. CS-3 persists roles and requires an authenticated synthetic employee before a write.

Roadmap exit: a dispatcher or customer-service agent can review an inbound inquiry, inspect a suggested reply, and approve or reject it, using synthetic data.

### Boundaries

- Inquiries, messages, interactions, approvals, and audit events already have JSON Schemas and valid fixtures. Persistence reuses those files.
- Suggested replies do not exist yet. The draft use case creates them. It does not rewrite historical fixture messages.
- One pending outbound example is already in the fixtures: `msg_0016` on `tkt_0007`, status `pending_approval`, approval `apr_0001`. Decision tests should use that row.
- Customer history text exists on tickets, messages, interactions, and work orders. Procedure documents do not. `data/documents/` is empty, and `storage_path` values are not files in the repository. Phase 2.2 adds a small synthetic procedure corpus when retrieval starts.
- The slice stops at approve or reject. Delivery to the customer is a later consequential action and needs its own approval execution step, which is not part of this exit.
- OpenAI is reached only through a port. Tests use a fake. No key is committed.

### Sequence

Tasks and dependencies are specified in [../../ENGINEERING_BACKLOG.md](../../ENGINEERING_BACKLOG.md). The order is:

1. **CS-1.** Read tickets, messages, and interactions. Link work orders to tickets with a foreign key.
2. **CS-2.** Read approvals and audit events. Audit rows stay insert-only.
3. **CS-3.** Persist roles so `is_approver` is real, and require an authenticated synthetic employee before any write.
4. **CS-4.** Human approve or reject of `send_customer_message`, with an audit event, without marking the message sent.
5. **CS-5.** Retrieval port over persisted history plus a new synthetic procedure corpus. Vector storage stays in PostgreSQL and waits for an embedding port.
6. **CS-6.** Draft a suggested reply through the AI port and open an approval request when the text would commit the company.
7. **CS-7.** React review surface under `apps/` for that approve and reject flow.

CS-5 may proceed in parallel with CS-3 and CS-4 after CS-1. CS-6 waits for CS-4 and CS-5. CS-7 waits for CS-6.

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

Structured logs use `APP_LOG_LEVEL`. Each access record has the actor, action, subject identifier, and outcome. Message bodies, contact details, and secrets stay out of the log. OpenTelemetry export remains Phase 5.

## Phase 3 — intelligent document processing

**State: not started.** Depends on Phase 2.2.

Schemas and fixtures for documents, versions, and extractions already exist (30 documents, 31 versions, 18 extractions). There are no bytes to ingest. The phase adds synthetic file content, classification, extraction, and human review for low-confidence results and any financial effect. Embeddings, when added, use pgvector in the same PostgreSQL instance. Model output stays untrusted until a person accepts it.

## Phase 4 — workflow automation

**State: not started.** Depends on the approval and audit path from CS-4, and on document review when the workflow uses documents.

Canonical rules stay in the monolith. n8n is an edge adapter for intake or notification once a workflow needs it. Redis is added only for cache or short-lived coordination that the use case actually performs. The exit is one multi-step workflow with human approval and an audit trail.

Knowledge search beyond the Phase 2.2 procedure corpus, sales qualification, and dispatch assistance belong here only when they complete a Wasatch process. They are not separate products.

## Phase 5 — production engineering and cloud definition

**State: not started.** Depends on a running module worth operating.

Add OpenTelemetry to the host, Terraform for a non-production Azure environment, and runbooks for backup and secrets. GitHub Actions remains credential-free for the laboratory checks. This phase defines a deployment path. It is not a production customer deployment and it does not authorize live HVAC data.

## Phase 6 — consulting portfolio

**State: not started.** Depends on a finished slice whose limits can be stated honestly.

Write a case study from laboratory results. Say what was simulated, what was measured, and what has not been deployed.

## Architectural conflicts to close in documentation

These are wording drift, not competing designs:

| Location | Drift | Resolution |
|---|---|---|
| `docs/architecture/README.md` | Said no runtime modules exist | Closed by DOC-1. The host is `services/wasatch-api`. |
| `docs/DEVELOPMENT_WORKFLOW.md` | Said open pull requests against `main` | Closed by DOC-1. Integration is `develop`. |
| ADR 0001 | Was Proposed after the host landed | Closed by ADR-1 (`c18ad80`). Status is Accepted. |
| `.github/workflows/validate.yml` | Push trigger listed `main` only | Closed by CI-1 (`ecd3015`). Pushes to `develop` run the workflow. |

No ADR is superseded by this plan.
