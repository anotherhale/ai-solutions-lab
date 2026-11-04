# ADR 0005: Docker Compose Local Development

- Status: Proposed
- Date: 2026-11-03

## Context

Later phases need PostgreSQL, Redis, and n8n on a developer's machine. Contributors should share one local topology without each installing those services natively.

Kubernetes would provide isolation, but it would also introduce cluster concepts the modular monolith does not need.

## Decision

Use Docker and Docker Compose as the local development environment for supporting services.

Application processes may run on the host during early module work. Compose files will be added when the first service actually needs a dependency.

Terraform and Azure remain the intended path for later cloud environments. They are not part of the local inner loop.

## Alternatives Considered

- **Native local installs of PostgreSQL and Redis.** Rejected as the documented default. They drift across machines.
- **Kubernetes for local development.** Rejected. There is no current requirement that justifies the complexity.
- **Cloud-hosted development databases from day one.** Rejected. They would require credentials and create cost before application code exists.

## Consequences

- Local setup stays reproducible and close to the later dependency set.
- CI for this phase can stay credential-free because Compose is not required to validate documentation and linting.
- Compose configuration must not appear until it has a consumer.
- This decision remains Proposed until a Compose environment is added and used by a service.
