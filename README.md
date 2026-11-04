# AI Solutions Lab

Engineering laboratory for practical AI solutions that small and midsize businesses can actually operate.

This repository began as a showcase for AI cloud solutions. It is now the home for a reusable implementation platform, a simulated Utah HVAC business, and a public consulting portfolio.

No application services or cloud environments have been deployed yet. The current work is the engineering foundation.

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

All business data in this repository is synthetic. See [docs/business/WASATCH_BUSINESS_PROFILE.md](docs/business/WASATCH_BUSINESS_PROFILE.md).

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
├── docs/                     Project charter, architecture, security, ADRs
├── apps/                     Future user-facing applications
├── services/                 Future backend modules and integration services
├── libs/                     Future shared libraries
├── infrastructure/           Docker and Terraform, added when needed
├── data/                     Synthetic seed data, fixtures, and documents
├── scripts/                  Repository maintenance and validation
└── tests/                    Integration and end-to-end tests
```

`apps/`, `services/`, and `libs/` are reserved. They do not contain application scaffolding yet.

## Local Development Prerequisites

The following tools will be required once application work starts. They are not all required to contribute documentation.

- Git
- Python 3.12 or later
- Node.js 22 LTS (for future frontend work)
- Docker and Docker Compose (for future local services)
- A GitHub account for pull requests

Optional local environment values belong in `.env`. Copy `.env.example` and replace placeholders only. Never commit `.env` or real credentials.

### Repository validation

```bash
python3 -m pip install ruff
ruff format --check .
ruff check .
python3 scripts/validate_repo.py
```

## Development Status

| Area | Status |
|---|---|
| Project documentation | In progress |
| Engineering standards | In progress |
| Repository tooling | In progress |
| Simulated business APIs | Not started |
| AI application services | Not started |
| Local Docker environment | Not started |
| Azure deployment | Not started |

The 90-day plan is in [docs/ROADMAP.md](docs/ROADMAP.md). Engineering workflow is in [docs/DEVELOPMENT_WORKFLOW.md](docs/DEVELOPMENT_WORKFLOW.md). Security principles are in [docs/SECURITY.md](docs/SECURITY.md).

## License

This project is licensed under the [MIT License](LICENSE).
