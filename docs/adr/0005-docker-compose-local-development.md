# ADR 0005: Docker Compose Local Development

- Status: Accepted
- Date: 2026-11-03

## Context

Later phases need PostgreSQL, Redis, and n8n on a developer's machine. Contributors should share one local topology without each installing those services natively.

Kubernetes would provide isolation, but it would also introduce cluster concepts the modular monolith does not need.

## Decision

Use Docker and Docker Compose as the local development environment for supporting services.

`compose.yaml` lives at the repository root so `docker compose up` is the inner-loop command. Application processes may still run on the host against the Compose PostgreSQL service.

Terraform and Azure remain the intended path for later cloud environments. They are not part of the local inner loop.

## Alternatives Considered

- **Native local installs of PostgreSQL and Redis.** Rejected as the documented default. They drift across machines.
- **Kubernetes for local development.** Rejected. There is no current requirement that justifies the complexity.
- **Cloud-hosted development databases from day one.** Rejected. They would require credentials and create cost before application code exists.

## Consequences

- Local setup stays reproducible and close to the later dependency set.
- CI for this phase can stay credential-free because Compose is not required to validate documentation and linting.
- Redis and n8n are still omitted; they have no consumer in this slice.
