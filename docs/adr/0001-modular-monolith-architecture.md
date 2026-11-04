# ADR 0001: Modular Monolith Architecture

- Status: Accepted
- Date: 2026-11-03

## Context

AI Solutions Lab will eventually host several Wasatch Business Systems capabilities: customer service, document processing, workflow automation, knowledge management, sales qualification, and reporting. Those capabilities need clear boundaries, but the laboratory does not yet have independent scale, team, or failure-isolation requirements.

Choosing a distributed runtime too early would add operational work before any application exists.

## Decision

Implement the first system as a modular monolith:

- One deployable FastAPI host
- Explicit modules with separate application and domain packages
- Shared infrastructure adapters only at the edges
- Independent deployable services only after a recorded requirement appears

Hexagonal architecture still applies inside the monolith. Modules communicate through application APIs and well-defined interfaces, not through hidden shared tables when a contract would be clearer.

## Alternatives Considered

- **Microservices from day one.** Rejected. There is no demonstrated need for independent scaling or separate release trains, and the operational cost would dominate a 65-person fictional SMB laboratory.
- **Unstructured single application.** Rejected. It would make later extraction and consulting reuse harder.
- **Kubernetes-hosted services.** Rejected until an ADR records a requirement the modular monolith cannot meet.

## Consequences

- Local development, testing, and later Azure deployment stay simpler.
- Module discipline must be enforced by package layout, reviews, and tests rather than by network boundaries.
- A future split is possible if a module acquires a distinct runtime need.
- `services/wasatch-api` is the host. It is one process, and the customer and work-order modules are the first packages.
