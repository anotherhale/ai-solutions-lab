# AI Solutions Lab

Engineering laboratory for practical AI solutions that small and midsize businesses can actually operate.

This repository began as a showcase for AI cloud solutions. It is now the home for a reusable implementation platform, a simulated Utah HVAC business, and a public consulting portfolio.

A FastAPI service and local PostgreSQL environment now exist for synthetic Wasatch data. The service can draft a suggested reply through a model port and can read persisted document, version, and extraction fixtures. The default port is a fake and does not call a provider. `apps/wasatch-review` is a React and TypeScript screen that approves or rejects that reply and accepts or rejects one document extraction. It does not send the message or post financial records. Azure has not been implemented.

## Business Objectives

- Design and demonstrate AI systems that reduce manual work in SMB operations.
- Build reusable implementation capabilities rather than one-off demos.
- Practice the delivery path from discovery through deployment and measurement.
- Create case studies that can be shown to real businesses in the Salt Lake City, Utah area.
- Keep humans in control of financial and customer-impacting decisions.

## Simulated Business

All laboratory work uses **Wasatch Business Systems**, a fictional commercial HVAC and facilities maintenance company based in Salt Lake City, Utah.

| Attribute | Synthetic value |
|---|---|
| Employees | Approximately 65 |
| Customers | Approximately 450 |
| Functions | Sales, customer service, field operations, dispatch and scheduling, accounting and finance, human resources, and management |

All business data in this repository is synthetic. See [docs/business/WASATCH_BUSINESS_PROFILE.md](docs/business/WASATCH_BUSINESS_PROFILE.md), [docs/business/WASATCH_DOMAIN_MODEL.md](docs/business/WASATCH_DOMAIN_MODEL.md), and `data/fixtures/`.

## Planned AI Solutions

1. Customer service automation
2. Intelligent document processing
3. Business workflow automation
4. Internal knowledge management
5. Sales and lead qualification
6. Business intelligence and reporting

## Technology Stack

These are initial architectural decisions and may be revised through ADRs.

| Area | Technology |
|---|---|
| Frontend | React + TypeScript |
| Backend | Python + FastAPI |
| AI integration | OpenAI API |
| Database | PostgreSQL |
| Vector search | pgvector |
| Cache | Redis |
| Workflow automation | n8n |
| Containerization | Docker / Docker Compose |
| Cloud | Microsoft Azure |
| Infrastructure as Code | Terraform |
| CI/CD | GitHub Actions |
| Observability | OpenTelemetry |

Python is the default language for AI application development and integration services. Java, Scala, or Rust may be introduced later for specialized services when an ADR justifies the cost.

Nx is deferred. The repository is not yet a multi-application monorepo, so Nx would add complexity without a current benefit.

## Architecture Overview

The target system is a **modular monolith**.

- One deployable backend with explicit module boundaries.
- Hexagonal architecture: domain and application logic sit behind ports; adapters integrate databases, AI providers, and external systems.
- API-first contracts between the React frontend, backend modules, and workflow automation.
- AI provider access through a replaceable port. OpenAI is the first adapter, not a domain dependency.
- Human approval gates for consequential operations.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/adr](docs/adr).

## Repository Structure

```text
ai-solutions-lab/
├── AGENTS.md
├── README.md
├── LICENSE
├── docs/                     Charter, architecture, security, operations notes, ADRs
├── apps/wasatch-review/      React review screen for bounded human decisions
├── services/wasatch-api/     FastAPI host for synthetic Wasatch data
├── libs/                     Future shared libraries
├── infrastructure/           Docker notes; Terraform placeholder, no workspace
├── compose.yaml              Local PostgreSQL (pgvector) and API
├── data/                     Schemas, synthetic fixtures, and documents
├── scripts/                  Repository maintenance and validation
└── tests/                    Reserved for later cross-service tests
```

`libs/` remains reserved. The review screen is `apps/wasatch-review`. API tests live under `services/wasatch-api/tests/`. Review-screen tests live next to that app and do not need a provider key.

## Local Development Prerequisites

The following tools will be required once application work starts. They are not all required to contribute documentation.

- Git
- Python 3.12 or later
- Docker and Docker Compose
- Node.js 22.12 or later (review screen)
- A GitHub account for pull requests

Optional local environment values belong in `.env`. Copy `.env.example` and replace placeholders only. Never commit `.env` or real credentials.

### Repository validation

```bash
python3 -m pip install 'ruff==0.17.3'
ruff format --check .
ruff check .
python3 scripts/validate_repo.py
python3 scripts/validate_wasatch_domain.py
```

### First application

See [services/wasatch-api/README.md](services/wasatch-api/README.md) and [docs/architecture/API_CONVENTIONS.md](docs/architecture/API_CONVENTIONS.md).

```bash
docker compose up -d postgres   # or: docker-compose up -d postgres
python3.12 -m venv services/wasatch-api/.venv
. services/wasatch-api/.venv/bin/activate
pip install -e 'services/wasatch-api[dev]'
cd services/wasatch-api
alembic upgrade head
wasatch-api seed
uvicorn wasatch_api.main:app --reload
```

The review screen proxies `/api` to that process. From `apps/wasatch-review`: `npm install` then `npm run dev`, and open http://127.0.0.1:5173. See [apps/wasatch-review/README.md](apps/wasatch-review/README.md).

## Development Status

| Area | Status |
|---|---|
| Project documentation | In progress |
| Engineering standards | In progress |
| Repository tooling | In progress |
| Synthetic domain model and fixtures | Defined |
| Wasatch API | On `develop`: customer-service reads, retrieval, draft replies, human approval, document reads, extraction review, procedure-page embeddings, the follow-up visit, host traces, and read-only invoice, line, and payment routes. Those finance routes do not post a payment. `main` is not the deployed product |
| Suggested-reply and extraction review screen | Implemented in `apps/wasatch-review`. It records approve/reject for replies and accept/reject for one extraction; it does not send messages or post money |
| AI application services | Draft replies and embeddings use the fake provider by default. The placeholder OpenAI key fails before a client is constructed. CI does not call a model |
| Local Docker environment | PostgreSQL with pgvector |
| Azure deployment | Not started |
| Case study | PORT-1. Documentation only. See the link below. It does not add a running system |

The 90-day plan is in [docs/ROADMAP.md](docs/ROADMAP.md). Engineering workflow is in [docs/DEVELOPMENT_WORKFLOW.md](docs/DEVELOPMENT_WORKFLOW.md). Security principles are in [docs/SECURITY.md](docs/SECURITY.md).

Verified status, ordered work, the implementation plan, and the agent operating model:

- [PROJECT_STATUS.md](PROJECT_STATUS.md)
- [ENGINEERING_BACKLOG.md](ENGINEERING_BACKLOG.md)
- [docs/architecture/IMPLEMENTATION_PLAN.md](docs/architecture/IMPLEMENTATION_PLAN.md)
- [docs/architecture/AGENT_OPERATING_MODEL.md](docs/architecture/AGENT_OPERATING_MODEL.md)
- [docs/case-studies/wasatch-laboratory-slice.md](docs/case-studies/wasatch-laboratory-slice.md)

## License

This project is licensed under the [MIT License](LICENSE).
