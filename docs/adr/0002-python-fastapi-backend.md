# ADR 0002: Python and FastAPI Backend

- Status: Accepted
- Date: 2026-11-03

## Context

The laboratory's first backend work is AI application development and integration services: HTTP APIs, retrieval workflows, document processing, and provider adapters. The team wants a language that is strong in that ecosystem and an HTTP framework that is explicit, typed, and easy to test.

Frontend work will use React and TypeScript. The backend choice should not force a JavaScript-only server.

## Decision

Use Python 3.12+ and FastAPI as the default backend for the modular monolith and integration services.

Java, Scala, or Rust may be introduced later for specialized services when an ADR explains why Python is insufficient.

The first host is `services/wasatch-api`. FastAPI is an application dependency of that package, not of repository-level validation tooling.

## Alternatives Considered

- **Django.** Deferred. Its batteries are useful, but the extra opinion about views, admin, and ORM is unnecessary before the first module exists.
- **Flask or raw Starlette.** Rejected as the default. They would require more structure to reach the same API documentation and validation baseline.
- **Node.js backend.** Rejected as the default. Python remains the better fit for the planned AI and data workflows.
- **Java, Scala, or Rust as the first host.** Rejected. Those languages remain available for later specialized services.

## Consequences

- Contributors can share typing, testing, and packaging conventions through `pyproject.toml`.
- AI provider SDKs and data libraries are readily available.
- The repository must avoid pulling FastAPI and related frameworks into the foundation until application code needs them.
- A read-only FastAPI service now exists and is exercised in CI.
