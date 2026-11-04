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

- Status: this pull request
- Depends on: CS-1 (done, `047702e`), so seed and migration edits stay serial
- Persist `approval_requests` and `audit_events` from the existing fixtures (10 approvals, 50 audit events).
- Read-only routes. Audit storage is insert-only: the migration and the application expose no update or delete for `audit_events`.
- Message rows that already reference `apr_0001` and `apr_0004` gain a foreign key to approval requests once that table exists.
- Acceptance: `msg_0016` (`pending_approval`, `requires_approval: true`, `apr_0001`) can be read with its approval request. No decision can be recorded yet.

### CS-3 — Laboratory actor and approver role

- Status: blocked on CS-2
- Depends on: CS-2
- Persist `roles` from `roles.json` and attach `employees.role_id` with a foreign key. `is_approver` comes from that role. Persist `teams` in the same change only if the employee foreign key is straightforward; team membership is not required to approve a message.
- Add a local authentication adapter for synthetic employees. Default deny on writes. Reads of customer and employee data require an authenticated laboratory actor.
- Keep the adapter inside the monolith. No Azure identity provider, no purchased identity service, and no production credentials.
- Tests cover an anonymous write rejection and an authenticated read of a ticket.
- Acceptance: every later write in this slice knows which synthetic employee is acting, and non-approver roles cannot decide approvals.

### CS-4 — Approve or reject a customer message

- Status: blocked on CS-3
- Depends on: CS-3
- Application service for the human decision on `send_customer_message`: approve or reject a pending request.
- The service appends `decision_history`, sets reviewer and `decided_at`, and inserts an audit event.
- The service leaves the message unsent. Status `sent` is not a result of this command.
- Authorization requires `is_approver` on the actor's role.
- Tests use the synthetic pending message and a role that is not an approver.
- Acceptance: an approver can approve or reject `apr_0001` through the API. The message body is unchanged and the message is not marked sent. An audit row exists for the decision.

### CS-5 — Retrieval over synthetic history and procedures

- Status: blocked on CS-1
- Depends on: CS-1. Can proceed beside CS-3 and CS-4 after CS-1 is merged.
- Retrieval port in the application layer. First adapter queries persisted ticket, message, interaction, and work-order text for one customer.
- `data/documents/` has no bytes. Document version rows point at synthetic paths such as `synthetic/documents/doc_0001/v1.bin`, and those files are not in the repository. Add a small synthetic procedure corpus under `data/documents/` when this task starts, labeled synthetic, and register it without replacing `data/fixtures/valid/`.
- Keep embeddings in PostgreSQL. Add a vector column only when an embedding port can fill it. Until then, retrieval is relational and text search. No second vector database.
- Acceptance: a query for a known synthetic ticket returns that customer's history and any matching procedure page, with tests that do not call a network model.

### CS-6 — Draft a suggested reply

- Status: blocked on CS-4 and CS-5
- Depends on: CS-3, CS-4, CS-5, and ADR 0004
- Define chat and embedding ports. Domain packages do not import a provider SDK.
- OpenAI is the first adapter and stays behind configuration. Tests use a fake port. Repository validation and CI stay free of an API key.
- The use case creates a `draft` or `pending_approval` message on an existing ticket. Outbound text that would commit the company sets `requires_approval` and opens a `send_customer_message` approval request.
- The use case does not set the message to `sent` and does not call an external delivery system.
- Acceptance: given synthetic ticket `tkt_0015` (or another inbound ticket chosen in the test), the API returns a draft reply grounded in retrieval results. Rejecting the approval leaves the draft unsent. CI passes without a provider credential.

### CS-7 — Review surface

- Status: blocked on CS-6
- Depends on: CS-4 and CS-6
- First React and TypeScript application under `apps/`. No Nx.
- A customer-service reviewer can open one inbound inquiry, read the suggested reply, and approve or reject it.
- The screen shows synthetic data and does not offer a send control.
- Acceptance: the roadmap exit for Phase 2 is demonstrable against the local API. Browser verification covers the approve and reject paths, an empty suggestion state, and an unauthorized actor.

## After the customer-service slice

These follow [docs/ROADMAP.md](docs/ROADMAP.md). Dates in that roadmap are planning windows, not commitments. Do not start them by pulling infrastructure forward.

| ID | Phase | Work | Depends on |
|---|---|---|---|
| DOC-P3 | 3 | Persist document, version, and extraction fixtures. Human review for low-confidence and financial extractions. Embeddings in the existing PostgreSQL instance when an embedding port exists. | CS-7, and a real document corpus rather than path strings alone |
| WF-1 | 4 | One multi-step Wasatch workflow with human approval and an audit trail. n8n only for an edge automation that the monolith does not own as the system of record. | CS-4 and the document review path if the workflow uses documents |
| OPS-1 | 5 | OpenTelemetry on the running host, Terraform for a non-production Azure environment, runbooks, backup notes, and secret-management notes. | A module worth operating. No production customer deployment. |
| PORT-1 | 6 | One case study that states what was simulated and what was measured. | A finished laboratory slice with honest limits |

Redis remains deferred until a module needs a cache or a short-lived lock. Kafka, Kubernetes, and a microservice split stay out until an ADR records a requirement the modular monolith cannot meet.

## Technical debt

Carry these until a task above closes them. Do not weaken the checks that already pass.

| Item | Where it shows up |
|---|---|
| Unauthenticated reads of synthetic customer and employee data | Current API. CS-3 closes this before writes. |
| No structured logs | `APP_LOG_LEVEL` is unused. Add logging with CS-3, excluding message bodies and secrets. |
| Thin HTTP contract tests | Status enums only. Each new route extends contract alignment. |
| Downgrade is untested | Revision `0001` defines `downgrade`. New revisions include an upgrade test and a downgrade test when the downgrade is safe on the synthetic database. |
| Pytest skip when PostgreSQL is absent | `tests/conftest.py`. CI is protected by its service container. A later test change can fail closed when `WASATCH_DATABASE_URL` is set and the server is down. |
| String foreign keys for invoices, roles, and teams | `DATABASE_MAPPING.md` |
| `python3 -m ruff` missing on the system interpreter in this environment | RUFF-1's environment install, which is outside the git diff. The pin itself landed in `ec6465f`. |
| Starlette `TestClient` deprecation warning | pytest warning, 1 occurrence |
| No Compose image smoke test in CI | API container is defined and was not started during the 2026-11-04 assessment |
| No dependency-audit tool | Review each new dependency in the pull request for purpose, what it replaces, license, and maintenance. Add a tool only when a task needs it. |

## Explicitly out of the next implementation

- Rebuilding Phase 2.1.1
- A second fixture generator output or a renamed copy of the domain
- Sending customer communications
- Financial posting, price changes, schedule changes, and bulk export
- Production deployment, purchased services, cloud credentials, and production API keys
- Microservices, Kubernetes, Kafka, and Nx
