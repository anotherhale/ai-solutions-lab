# Agent Instructions

These instructions apply to every AI coding agent and human contributor working in this repository.

## Project Purpose and Scope

AI Solutions Lab is an engineering laboratory for designing, implementing, deploying, and demonstrating practical AI solutions for small and midsize businesses (SMBs).

The near-term laboratory subject is a fictional Utah-based commercial HVAC and facilities maintenance company named **Wasatch Business Systems**. All business data in this repository is synthetic.

The long-term objective is a reusable AI consulting platform and portfolio that can be applied to real businesses in the Salt Lake City, Utah area.

Do not implement production client work, live customer data, or unrelated products in this repository.

## Current Status

Documentation, domain contracts, synthetic fixtures, a local PostgreSQL environment, and a FastAPI slice exist. The API can read synthetic operations, record an approval decision, and draft a suggested reply. The default model port is a fake and does not call a provider. `apps/wasatch-review` is a React and TypeScript screen for that decision. It does not send customer messages. Synthetic procedure-page embeddings are stored in PostgreSQL (`procedure_page_embeddings.embedding`). They are procedure text from the fake port, not a trusted model, and not document bytes. Outbound delivery and cloud environments have not been implemented and must not be described as if they have.

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

Docker Compose Postgres, the FastAPI service, and the review screen are the runnable slice. Compose defaults match the application defaults (`wasatch` / `replace-me` on localhost), so a root `.env` is optional. Leave `WASATCH_FIXTURES_DIR` unset. A blank value is loaded as the current directory and seed will not find `data/fixtures/valid`.

From `services/wasatch-api`, `pytest` uses that Postgres and creates the `wasatch_test` database. On a Cloud Agent workstation the start command launches Docker, Postgres, migrations, seed, and the API on port 8000. That workstation is not an Azure deployment.

## Development activity log (mandatory)

Autonomous agents and coordinators MUST record meaningful development milestones in
PostgreSQL `development_ops` using `development-ops-record` or
`scripts/coordinator_activity.sh`. Do not log chain-of-thought, hidden reasoning, or
every tool invocation.

| Milestone | When to record |
|---|---|
| `run.started` / `run.completed` / `run.failed` | Start, successful finish, or abort of an agent run |
| `task.selected` / `task.delegated` | Coordinator picks or assigns work |
| `implementation.milestone` | Coherent implementation progress (not each edit) |
| `test.started` / `test.completed` / `test.failed` | Verification attempts and outcomes |
| `review.started` / `review.completed` | Independent review requested or finished |
| `pr.opened` / `pr.updated` / `pr.merged` | GitHub PR lifecycle (use GitHub as source of truth) |
| `blocker.reported` | Blockers and failures that stop progress |

Set `DEVELOPMENT_OPS_RUN_ID` for the whole run and reuse it for every event in that
run. Set `DEVELOPMENT_OPS_TASK_ID` when working a specific backlog item. Persist
**before** Slack. Post to `#ai-development` (`C0CFJDH7PTJ`) via the authorized Slack
integration, then call `development-ops-record confirm-slack` with the returned
`channel_id` and `message_ts`. Never treat missing telemetry or unconfirmed Slack as
success. See [docs/operations/DEVELOPMENT_ACTIVITY_LOG.md](docs/operations/DEVELOPMENT_ACTIVITY_LOG.md).

Example:

```bash
export DEVELOPMENT_OPS_RUN_ID="$(uuidgen)"
export DEVELOPMENT_OPS_GITHUB_REPOSITORY="anotherhale/ai-solutions-lab"
scripts/coordinator_activity.sh run-start "Phase 2 agent instrumentation"
scripts/coordinator_activity.sh implementation "CLI for activity recording"
```

If `development-ops-record` exits `1`, persistence failed — report the failure in
Slack and do not claim the milestone was recorded.

Use `DEVELOPMENT_OPS_DATABASE_URL` (default database `wasatch_development_ops`) for
activity and coordinator state. Pytest uses `wasatch_test` and must not destroy
operational telemetry.

Pytest coordinator tests use a separate disposable database,
`wasatch_development_ops_test`, resolved by
`wasatch_api.testing.postgres.wasatch_development_ops_test_database_url()`. That
helper never returns `wasatch_development_ops`, even when
`DEVELOPMENT_OPS_DATABASE_URL` points at it, and `drop_and_recreate_test_database`
refuses operational and maintenance database names before running any SQL. See
[ADR 0011](docs/adr/0011-test-database-isolation.md). Do not add tests that
resolve a database URL by hand; request the `ops_test_engine` fixture instead.

## Coordinator continuity (mandatory)

Open pull requests must **not** block unrelated backlog work. After opening a PR:

1. Record `pr-opened` and verify CI when possible.
2. Attempt GraphQL `enablePullRequestAutoMerge` (squash) only through the coordinator
   or documented tooling; verify `autoMergeRequest` is non-null when enabling succeeds.
3. If auto-merge fails, record the exact GitHub error and continue.
4. Run `scripts/coordinator_tick.sh` (or `development-ops-record coordinator tick`) so
   the next **eligible** independent task is selected without waiting for merge.

Do not serialize the entire backlog behind one open PR. Respect `depends_on` in
`data/coordinator/backlog.yaml`. Do not hand-edit that catalog: the coordinator is its only
sanctioned writer and records merges itself, so agent edits only create merge conflicts that
block auto-merge (see [docs/adr/0014](docs/adr/0014-autonomous-integration-branch-consolidation.md)
and [docs/operations/COORDINATOR_CONTINUITY.md](docs/operations/COORDINATOR_CONTINUITY.md)).

The tick can be driven by a persistent, restart-safe runner:
`development-ops-record runner run` (loop), `runner once` (one cycle),
`runner status` (read-only health), and `runner pause`/`runner resume` (durable,
non-destructive pause). Ownership is a single-workstation `flock`; the launchd
LaunchAgent in `infrastructure/launchd/` is a template and is not activated by
CI. See [docs/operations/COORDINATOR_RUNNER.md](docs/operations/COORDINATOR_RUNNER.md)
and [ADR 0013](docs/adr/0013-persistent-coordinator-runner.md).

## Definition of Honest Completion

A task is complete only when the requested change is in the repository, relevant documents are consistent, and verification that could be run was run. If something remains unfinished, list it explicitly.

## Strict GitHub Merge Policy

Never use a direct merge operation as a fallback for failed auto-merge configuration.

Allowed:
- GraphQL enablePullRequestAutoMerge, with squash strategy.
- Read-only GitHub PR and status inspection.
- Creating and updating PRs.
- Requesting independent reviews where supported.

Prohibited:
- gh pr merge, including --auto.
- REST PUT /pulls/{pull_number}/merge.
- GraphQL mergePullRequest.
- Any operation that immediately merges a PR.

After requesting auto-merge:
1. Verify autoMergeRequest is non-null.
2. Verify the requested merge method.
3. Report the actual merge-queue status.
4. If the request fails, leave the PR open.
5. Report the exact GitHub response in #ai-development.
6. Never attempt an alternative merge operation.

A green CI status does not authorize an agent to merge.

Only the repository owner's explicitly authorized merge process may override this policy.
