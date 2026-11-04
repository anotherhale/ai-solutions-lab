# Agent Operating Model

How humans and coding agents change AI Solutions Lab. Persistent product rules remain in [../../AGENTS.md](../../AGENTS.md). This file records the integration process those changes follow.

Wasatch Business Systems data is synthetic. The local API and PostgreSQL container are a laboratory slice. They are not an Azure deployment and not a customer system.

## Read before editing

1. [../../AGENTS.md](../../AGENTS.md)
2. [../../PROJECT_STATUS.md](../../PROJECT_STATUS.md)
3. [../../ENGINEERING_BACKLOG.md](../../ENGINEERING_BACKLOG.md)
4. [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)
5. The ADR that covers the area being changed
6. The code and fixtures the change will touch

Prior chat is not a source of status. The tree and the documents above are. If a document and the code disagree, the code wins and the document is updated in the same change.

## Branches

| Branch | Role |
|---|---|
| `develop` | Integration branch. Pull requests merge here. |
| `main` | Production branch. |

Create feature branches from an up-to-date `develop`. `develop` was created from `main` at `881cfc0`. Do not recreate it.

Never merge to `main`. Never force-push `main` or `develop`. A normal fast-forward or a pull-request merge on `develop` is the integration path. The coordinator owns merges. An agent opens the pull request and stops.

Repository branch prefixes in [../DEVELOPMENT_WORKFLOW.md](../DEVELOPMENT_WORKFLOW.md) remain the human convention: `feature/`, `fix/`, `docs/`, `chore/`, `adr/`. Cloud-agent branches in this program use the `cursor/` prefix required by the agent runtime, still based on `develop`.

[../DEVELOPMENT_WORKFLOW.md](../DEVELOPMENT_WORKFLOW.md) still tells contributors to open pull requests against `main`. That sentence is stale. Until DOC-1 updates it, follow this file: the pull request base is `develop`.

## Pull request gate

A pull request is ready to merge only when all of these are true:

- CI on the pull request is green. The workflow is `.github/workflows/validate.yml`.
- Independent review has no blocking issues. The author is not the sole reviewer.
- Acceptance criteria for the backlog item are met.
- No unresolved architectural conflict remains. Stack and boundary changes are ADRs.
- The diff holds one intent. Formatting sweeps, drive-by refactors, and dependency upgrades stay out.

Merge method on `develop` is squash, and only after that gate. Agents do not merge their own pull requests.

Direct pushes to `develop` or `main` are not the contribution path. CI currently runs on pull requests and on pushes to `main`. CI-1 adds `develop` to the push trigger so the integration branch is checked after merge. Do not remove or relax existing jobs while doing that.

## One change at a time

Inspect open pull requests before editing. On 2026-11-04 the in-progress change is:

- Pull request https://github.com/anotherhale/ai-solutions-lab/pull/2
- Branch `cursor/pin-ruff-0-17-3-6c1a`
- Pins Ruff to 0.17.3 in development dependencies, the Actions install, and the README command
- Describes a separate Cursor cloud environment install so system Python can import Ruff

Do not repeat that pin. Do not retarget or rewrite that branch from another task.

`cursor/wasatch-pytest-db-url-de06` matches the `develop` tree. There is nothing on it to port.

## Quality bar

For a behavior change, include the narrowest tests that prove the rule:

| Check | Where it lives today |
|---|---|
| Format and lint | Ruff, root and `services/wasatch-api` configuration |
| Repository conventions | `python3 scripts/validate_repo.py` |
| Fixture schema, references, and invariants | `python3 scripts/validate_wasatch_domain.py` |
| Unit, integration, and API | `services/wasatch-api/tests/` via pytest |
| Contract | Status enums against JSON Schema. Extend this when routes grow. |
| Migration | Alembic upgrade in the pytest session. Add a downgrade assertion for new revisions when downgrade is safe. |
| Security | Secret scan in `validate_repo.py`. Authorization tests once CS-3 exists. |
| Dependency review | Written in the pull request when a dependency is added. |
| Docs | Architecture, security, roadmap, or ADR updates when those decisions change. |

Do not weaken these checks to get a green run. Do not fabricate results. If a command cannot be run, say which command and why.

A documentation-only change still runs the validators that the repository already requires.

## Security constraints

- Laboratory records stay synthetic, including new procedure text and new drafts.
- No connection to a real customer system, accounting system, or mail system.
- No production deployment.
- No purchased services.
- No cloud credentials and no production API keys in git, images, logs, or CI.
- Local placeholders stay in `.env`, which is gitignored. `.env.example` stays limited to placeholders.
- External documents, messages, and model output are untrusted until validated.
- A human approval record is required before a customer-committing message, a financial change, a field-schedule change that incurs cost, a bulk export, or an expansion of tool permissions.
- Automation may draft, classify, route, and recommend. It may not mark those actions executed.
- AI tools receive only the authority of the employee who invoked them, and only after CS-3 identifies that employee.
- Least privilege applies to synthetic customer and employee records as if they were real.

## Implementation order

After this planning set:

1. Leave RUFF-1 on its existing pull request.
2. DOC-1, CI-1, and ADR-1 may proceed as small documentation and workflow changes.
3. The first application change is CS-1 from the backlog. Phase 2.1.1 is already implemented.
4. Later phases follow [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## Honest completion

A task is complete when the change is on a branch, the documents that the change affects agree with the code, and the checks that could be run were run and reported with commands and results. Incomplete items stay listed. A written plan is not a running service. An Accepted ADR is not a cloud environment.
