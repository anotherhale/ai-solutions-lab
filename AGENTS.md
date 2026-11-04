# Agent Instructions

These instructions apply to every AI coding agent and human contributor working in this repository.

## Project Purpose and Scope

AI Solutions Lab is an engineering laboratory for designing, implementing, deploying, and demonstrating practical AI solutions for small and midsize businesses (SMBs).

The near-term laboratory subject is a fictional Utah-based commercial HVAC and facilities maintenance company named **Wasatch Business Systems**. All business data in this repository is synthetic.

The long-term objective is a reusable AI consulting platform and portfolio that can be applied to real businesses in the Salt Lake City, Utah area.

Do not implement production client work, live customer data, or unrelated products in this repository.

## Current Status

Documentation, domain contracts, synthetic fixtures, a local PostgreSQL environment, and a read-only FastAPI slice exist. AI assistants, embeddings, React UI, write APIs, and cloud environments have not been implemented and must not be described as if they have.

Inspect the working tree and relevant documents before making changes. Preserve useful existing content.

## Architectural Principles

Follow these principles unless an Architecture Decision Record (ADR) supersedes them:

- Use Domain-Driven Design where the business language and boundaries are clear.
- Prefer hexagonal architecture (ports and adapters).
- Keep domain, application, infrastructure, and presentation concerns separate.
- Treat the system as a modular monolith until a demonstrated requirement justifies another deployment shape.
- Keep service boundaries explicit even while modules share a process.
- Design integrations API-first.
- Abstract AI providers behind ports. Do not call vendor SDKs from domain logic.
- Place external systems behind replaceable adapters.
- Require human approval for consequential business operations.
- Treat security, observability, and testing as first-class work, not follow-up tasks.

Do not introduce microservices or Kubernetes without a documented business or technical requirement and an ADR.

Do not install Nx unless the monorepo complexity clearly outweighs the tool's cost. The current decision is to defer Nx. See `docs/ARCHITECTURE.md`.

## Coding Standards

- Prefer small, reviewable changes that solve the requested problem.
- Do not make unrelated refactors, formatting sweeps, or dependency upgrades.
- Match existing naming, file layout, and documentation tone.
- Use Python for AI application development and integration services.
- Use TypeScript for frontend work when that code exists.
- Keep Java, Scala, or Rust reserved for specialized services that have a written justification.
- Put business rules in the domain or application layer, not in adapters, UI components, or workflow scripts.
- Name types, modules, and APIs with Wasatch Business Systems language when the code models that domain.
- Avoid speculative abstractions and premature infrastructure.

## Testing Requirements

- New behavior needs automated tests at the most effective level: unit first, then integration, then end-to-end.
- Do not add tests that only assert mocks or restate implementation details.
- Do not fabricate test results, coverage numbers, or passing CI status.
- If tests cannot be run, say so and report what was not verified.
- Integration and end-to-end tests must use synthetic data only.

## Documentation Requirements

- Update the relevant document when a change alters architecture, workflow, security, or scope.
- Record architectural choices in `docs/adr/` using the conventions in `docs/adr/README.md`.
- Keep technology names consistent with `README.md` and `docs/ARCHITECTURE.md`.
- Label Wasatch Business Systems content as synthetic.
- Do not claim that services, environments, or integrations exist unless they are in the repository and verified.

## Security Requirements

- Never commit secrets, credentials, API keys, tokens, or private certificates.
- Use `.env` for local values and keep `.env.example` limited to placeholders.
- Use managed secrets for cloud deployments when those deployments exist.
- Apply least-privilege authorization.
- Protect sensitive business information, including synthetic customer and employee records.
- Maintain audit trails for consequential actions.
- Treat external documents and AI inputs as untrusted.
- Require human approval before financial or customer-impacting actions.
- Follow `docs/SECURITY.md`.

## Dependency Management

- Do not add a dependency unless it is required for the current task.
- Explain why a new dependency is needed, what it replaces, and what risk it adds.
- Prefer the existing proposed stack: React, TypeScript, Python, FastAPI, PostgreSQL, pgvector, Redis, OpenAI API, n8n, Docker Compose, Azure, Terraform, GitHub Actions, and OpenTelemetry.
- Do not introduce application frameworks, cloud modules, or infrastructure tools "for later."
- Pin or bound versions in the relevant manifest when a dependency is added.

## Working Agreement

1. Inspect the repository, related documents, and nearby code before modifying files.
2. Stay within the requested task. Do not expand scope.
3. Explain architectural tradeoffs when more than one reasonable option exists.
4. Do not introduce dependencies or infrastructure without explaining why they are needed now.
5. Never fabricate test results, logs, benchmarks, or completion status.
6. Report incomplete work, skipped verification, and residual risk honestly.
7. Prefer changing documentation and ADRs over silently revising a prior decision.

## Local Wasatch slice

Docker Compose Postgres and the read-only API are the runnable slice. Compose defaults match the application defaults (`wasatch` / `replace-me` on localhost), so a root `.env` is optional. Leave `WASATCH_FIXTURES_DIR` unset. A blank value is loaded as the current directory and seed will not find `data/fixtures/valid`.

From `services/wasatch-api`, `pytest` uses that Postgres and creates the `wasatch_test` database. On a Cloud Agent workstation the start command launches Docker, Postgres, migrations, seed, and the API on port 8000. That workstation is not an Azure deployment.

## Definition of Honest Completion

A task is complete only when the requested change is in the repository, relevant documents are consistent, and verification that could be run was run. If something remains unfinished, list it explicitly.
