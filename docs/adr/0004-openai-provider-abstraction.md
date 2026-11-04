# ADR 0004: OpenAI Provider Abstraction

- Status: Proposed
- Date: 2026-11-03

## Context

The planned solutions depend on language models and embeddings. Binding use cases directly to one vendor SDK would make later comparison, failover, or client-specific hosting expensive.

OpenAI is widely supported and sufficient for the first laboratory implementations.

## Decision

- Use the OpenAI API as the first concrete AI provider.
- Access models only through application ports: chat/tool use, embeddings, and any required safety checks.
- Keep vendor clients, model names as configuration, retries, and token accounting in infrastructure adapters.
- Do not import provider SDKs from domain code.

The OpenAI SDK is not added until a module needs it. Repository validation must not require an API key.

## Alternatives Considered

- **Calling OpenAI directly from each module.** Rejected. It would scatter prompts, credentials handling, and error mapping.
- **A different first provider.** Deferred. Another adapter can be added later without changing Wasatch use cases if the port remains stable.
- **Local-only models from the start.** Deferred. They may become useful for cost or privacy demonstrations, but they are not required for Phase 2.

## Consequences

- Use cases stay portable across providers.
- Tests can fake ports without standing up a network client.
- Prompt and model changes become configuration and adapter work.
- This decision remains Proposed until a port and OpenAI adapter are implemented.
